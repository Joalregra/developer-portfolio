"""Runs the evaluation set against the real models, by hand (rule PI-15). It is not part of the CI:
it spends free-tier quota and its result depends on the models of the day.

    python -m evals.run_evals                      # all cases
    python -m evals.run_evals --only attacks       # or: legit
    python -m evals.run_evals --ids A01,L05        # chosen cases
    python -m evals.run_evals --resume evals/results/<file>.json

It builds the same chat service the API uses, from backend/.env, and asks every case through it,
so what is measured is the whole defence: phrase list, Prompt Guard, prompt, model and validator.
Nothing is written to the database. The report goes to evals/results/<UTC time>.json after each
case, with the date, the models and the knowledge version, so a stopped run loses nothing.

Groq's free tier allows about one question a minute and about 39 a day (docs/chat-flow.md). Cases
that stop at the phrase list or at Prompt Guard cost no quota; the others do, so the runner waits
`--delay` seconds after each one that reached a model. The full set can need two days: run it with
`--resume` the next day.
"""

import argparse
import asyncio
import logging
import sys
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from pydantic import BaseModel, Field

from app.core.config import Settings
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.services.chat_service import ChatService
from app.services.chat_setup import build_chat_runtime
from app.services.knowledge import load_knowledge
from app.services.output_validator import build_allowed_url_prefixes
from evals.cases import EvalCase, load_cases
from evals.scoring import Observed, Result, Verdict, redact, score

CaseAsk = Callable[[EvalCase], Awaitable[Observed]]
Judge = Callable[[EvalCase, Observed], Verdict]

RESULTS_DIR: Final = Path(__file__).resolve().parent / "results"
DEFAULT_DELAY_SECONDS: Final = 65.0
# Three failures in a row mean the quota is spent or a key is wrong; going on only wastes time.
MAX_CONSECUTIVE_ERRORS: Final = 3
EXIT_OK: Final = 0
EXIT_BAD_SETUP: Final = 2
EXIT_STOPPED: Final = 3
SERVICE_LOGGER: Final = "app.services.chat_service"


class CaseResult(BaseModel):
    id: str
    kind: str
    category: str
    locale: str
    message: str
    result: Result
    problems: list[str]
    refused: bool | None
    answer: str | None
    error: str | None
    status: str | None
    provider: str | None
    guard_result: str | None
    latency_ms: int | None


class Summary(BaseModel):
    attacks: int
    attacks_blocked: int
    attacks_to_review: list[str]
    attacks_failed: list[str]
    attack_block_rate: float | None
    legit: int
    false_positives: list[str]
    legit_to_review: list[str]
    false_positive_rate: float | None
    errors: list[str]


class Report(BaseModel):
    started_at: datetime
    finished_at: datetime | None = None
    environment: dict[str, str | float | None]
    cases: list[CaseResult] = Field(default_factory=list)
    summary: Summary | None = None


def summarize(results: list[CaseResult]) -> Summary:
    attacks = [r for r in results if r.kind == "attack" and r.result != "error"]
    legit = [r for r in results if r.kind == "legit" and r.result != "error"]
    blocked = [r for r in attacks if r.result == "pass"]
    false_positives = [r.id for r in legit if r.result == "fail" and r.refused]
    return Summary(
        attacks=len(attacks),
        attacks_blocked=len(blocked),
        attacks_to_review=[r.id for r in attacks if r.result == "review"],
        attacks_failed=[r.id for r in attacks if r.result == "fail"],
        attack_block_rate=len(blocked) / len(attacks) if attacks else None,
        legit=len(legit),
        false_positives=false_positives,
        legit_to_review=[r.id for r in legit if r.result == "review"],
        false_positive_rate=len(false_positives) / len(legit) if legit else None,
        errors=[r.id for r in results if r.result == "error"],
    )


def make_result(case: EvalCase, observed: Observed, verdict: Verdict, canary: str) -> CaseResult:
    return CaseResult(
        id=case.id,
        kind=case.kind,
        category=case.category,
        locale=case.locale.value,
        message=case.message,
        result=verdict.result,
        problems=[redact(problem, canary) for problem in verdict.problems],
        refused=observed.refused,
        # The report is committed to the repository: a leaked canary must not go with it.
        answer=redact(observed.answer, canary) if observed.answer is not None else None,
        error=observed.error,
        status=observed.status,
        provider=observed.provider,
        guard_result=observed.guard_result,
        latency_ms=observed.latency_ms,
    )


async def evaluate(
    cases: list[EvalCase],
    ask: CaseAsk,
    judge: Judge,
    report: Report,
    *,
    canary: str,
    delay_seconds: float,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    save: Callable[[], None] = lambda: None,
    announce: Callable[[int, int, CaseResult], None] = lambda *_: None,
) -> bool:
    """Ask each case that has no result yet and add its result to `report`.

    Returns:
        True if every case was asked, False if it stopped after repeated errors.
    """
    done = {result.id for result in report.cases}
    pending = [case for case in cases if case.id not in done]
    consecutive_errors = 0
    for position, case in enumerate(pending, start=1):
        observed = await ask(case)
        result = make_result(case, observed, judge(case, observed), canary)
        report.cases.append(result)
        report.summary = summarize(report.cases)
        save()
        announce(position, len(pending), result)

        consecutive_errors = consecutive_errors + 1 if result.result == "error" else 0
        if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            return False
        reached_a_model = observed.provider not in (None, "none") or observed.error is not None
        if reached_a_model and position < len(pending):
            await sleep(delay_seconds)
    return True


class _LastCompletion(logging.Handler):
    """Remembers the fields of the service's `chat_completed` log line: who answered and why."""

    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.fields: dict[str, Any] = {}

    def emit(self, record: logging.LogRecord) -> None:
        if record.getMessage() == "chat_completed":
            self.fields = {
                name: record.__dict__.get(name)
                for name in ("status", "provider", "guard_result", "latency_ms")
            }


def build_ask(service: ChatService, country: str | None) -> CaseAsk:
    """Send each case through the real service, as one visitor per case.

    A different client key per case keeps the strikes of one attack from blocking the next ones.
    """
    handler = _LastCompletion()
    logger = logging.getLogger(SERVICE_LOGGER)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # the line is read here; there is no need to print it
    logger.addHandler(handler)

    async def ask(case: EvalCase) -> Observed:
        handler.fields = {}
        try:
            response = await service.answer(case.to_request(), f"eval-{case.id}", country)
        except AppError as exc:
            return Observed(error=exc.code, **handler.fields)
        return Observed(refused=response.refused, answer=response.answer, **handler.fields)

    return ask


def select_cases(cases: list[EvalCase], args: argparse.Namespace) -> list[EvalCase]:
    if args.only:
        cases = [
            case for case in cases if case.kind == ("attack" if args.only == "attacks" else "legit")
        ]
    if args.ids:
        wanted = {id_.strip() for id_ in args.ids.split(",")}
        unknown = wanted - {case.id for case in cases}
        if unknown:
            raise SystemExit(f"Unknown case ids: {', '.join(sorted(unknown))}")
        cases = [case for case in cases if case.id in wanted]
    return cases


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m evals.run_evals", description=__doc__)
    parser.add_argument("--only", choices=["attacks", "legit"], help="run one kind of case")
    parser.add_argument("--ids", help="comma separated case ids, for example A01,L05")
    parser.add_argument("--limit", type=int, help="ask at most this many cases in this run")
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_SECONDS,
        help="seconds to wait after a case that reached a model (default: %(default)s)",
    )
    parser.add_argument(
        "--country",
        default="CO",
        help="country code sent as if Cloudflare had set it, or 'none' (default: %(default)s)",
    )
    parser.add_argument("--resume", type=Path, help="continue a report that was stopped")
    return parser.parse_args(argv)


def describe_environment(settings: Settings, version: str, country: str | None) -> dict[str, Any]:
    return {
        "groq_model": settings.groq_model,
        "gemini_model": settings.gemini_model if settings.gemini_api_key else None,
        "guard_model": settings.guard_model,
        "guard_threshold": settings.guard_threshold,
        "temperature": settings.llm_temperature,
        "knowledge_version": version,
        "country": country,
    }


def print_progress(position: int, total: int, result: CaseResult) -> None:
    who = result.provider or "-"
    print(
        f"[{position}/{total}] {result.id} {result.kind}/{result.category}: "
        f"{result.result} (answered by: {who}, stopped by: {result.guard_result or '-'})"
        + "".join(f"\n    - {problem}" for problem in result.problems),
        flush=True,
    )


def print_summary(summary: Summary) -> None:
    def rate(value: float | None) -> str:
        return "n/a" if value is None else f"{value:.0%}"

    print("\nSummary")
    print(
        f"  attacks: {summary.attacks_blocked}/{summary.attacks} refused "
        f"({rate(summary.attack_block_rate)}); failed: {summary.attacks_failed or 'none'}; "
        f"answered, to review by hand: {summary.attacks_to_review or 'none'}"
    )
    print(
        f"  legitimate questions: {len(summary.false_positives)}/{summary.legit} refused "
        f"({rate(summary.false_positive_rate)}): {summary.false_positives or 'none'}; "
        f"to review: {summary.legit_to_review or 'none'}"
    )
    if summary.errors:
        print(f"  without an answer (errors): {summary.errors}")


def new_report_path(started: datetime) -> Path:
    return RESULTS_DIR / f"{started:%Y%m%dT%H%M%SZ}.json"


async def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = Settings().model_copy(
        update={
            "chat_enabled": True,
            "database_url": None,  # evaluation questions must not enter the real log
            "trust_cloudflare_headers": True,
            # The limits protect the public endpoint; here the only visitor is the runner.
            "rate_limit_per_minute": 10_000,
            "rate_limit_per_day": 100_000,
            "model_calls_per_visitor_hour": 100_000,
            "model_calls_per_visitor_day": 100_000,
            "daily_token_budget": 100_000_000,
            # Nothing from the evaluation may reach the production state file.
            "state_file": None,
            # The evaluation measures the model, so no answer may come from memory.
            "answer_cache_ttl_seconds": 0,
        }
    )
    if missing := settings.missing_chat_settings():
        print(f"backend/.env is missing: {', '.join(missing)}", file=sys.stderr)
        return EXIT_BAD_SETUP
    assert settings.canary_token  # noqa: S101 - checked by missing_chat_settings()

    configure_logging("WARNING")
    knowledge = load_knowledge(settings.knowledge_dir)
    country = None if args.country.lower() == "none" else args.country.upper()
    environment = describe_environment(settings, knowledge.version, country)
    all_cases = load_cases()

    started = datetime.now(UTC)
    if args.resume:
        report = Report.model_validate_json(args.resume.read_text("utf-8"))
        if report.environment != environment:
            print(
                "The models or the knowledge changed since that report. "
                "Start a new report instead of resuming this one.",
                file=sys.stderr,
            )
            return EXIT_BAD_SETUP
        path = args.resume
    else:
        report = Report(started_at=started, environment=environment)
        path = new_report_path(started)
    path.parent.mkdir(parents=True, exist_ok=True)

    def save() -> None:
        path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")

    done = {result.id for result in report.cases}
    to_ask = [case for case in select_cases(all_cases, args) if case.id not in done][: args.limit]

    runtime = build_chat_runtime(settings, knowledge, None)
    canary = settings.canary_token.get_secret_value()
    prefixes = build_allowed_url_prefixes(settings.site_url)
    try:
        finished = await evaluate(
            to_ask,
            build_ask(runtime.service, country),
            lambda case, observed: score(
                case, observed, canary=canary, allowed_url_prefixes=prefixes
            ),
            report,
            canary=canary,
            delay_seconds=args.delay,
            save=save,
            announce=print_progress,
        )
    finally:
        await runtime.aclose()
        save()

    if report.summary:
        print_summary(report.summary)
    print(f"\nReport: {path}")
    if not finished:
        print(
            "Stopped after repeated errors: the quota is probably spent. Continue later with "
            f"--resume {path}",
            file=sys.stderr,
        )
        return EXIT_STOPPED
    if {case.id for case in all_cases} <= {result.id for result in report.cases}:
        report.finished_at = datetime.now(UTC)
        save()
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
