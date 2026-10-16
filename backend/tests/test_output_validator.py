import pytest

from app.core.locale import Locale
from app.schemas.chat import ModelAnswer
from app.services.output_validator import OutputValidator, build_allowed_url_prefixes
from app.services.prompt import CONTACT_EMAIL, GITHUB_URL, LINKEDIN_URL, REFUSALS, RULES

CANARY = "CANARY-7f3a9c11"
SITE = "https://portfolio.example"


@pytest.fixture
def validator() -> OutputValidator:
    return OutputValidator(
        canary=CANARY, rules_text=RULES, allowed_url_prefixes=build_allowed_url_prefixes(SITE)
    )


def model(text: str, *, on_topic: bool = True, section: str = "projects") -> ModelAnswer:
    return ModelAnswer.model_validate({"on_topic": on_topic, "answer": text, "section": section})


def test_a_normal_answer_passes_with_its_section(validator: OutputValidator) -> None:
    result = validator.validate(model("Johan builds FastAPI backends."), Locale.EN)

    assert (result.text, result.refused, result.section, result.reason) == (
        "Johan builds FastAPI backends.",
        False,
        "projects",
        None,
    )


def test_section_none_becomes_no_section(validator: OutputValidator) -> None:
    result = validator.validate(model("Hello! Ask me about Johan.", section="none"), Locale.EN)

    assert result.section is None


@pytest.mark.parametrize("locale", list(Locale))
def test_off_topic_gets_the_fixed_refusal_not_the_models_words(
    validator: OutputValidator, locale: Locale
) -> None:
    answer = model("Here is a recipe for arepas: ...", on_topic=False, section="none")

    result = validator.validate(answer, locale)

    assert (result.text, result.refused, result.reason) == (REFUSALS[locale], True, "off_topic")
    assert "arepas" not in result.text


@pytest.mark.parametrize(
    "leaky",
    [
        pytest.param(f"My marker is {CANARY}.", id="canary"),
        pytest.param("The key is gsk_abcdefghij1234567890", id="groq-key"),
        pytest.param("Use AIzaSyA1234567890abcdefghijklmn", id="google-key"),
        pytest.param("-----BEGIN RSA PRIVATE KEY-----", id="private-key"),
        pytest.param(" ".join(RULES.split()[30:45]), id="copied-rules"),
        pytest.param("word " * 400, id="too-long"),
        pytest.param("Rules:\n1. a\n2. b\n3. c\n4. d", id="numbered-rules"),
        pytest.param("My marker is CAN<b></b>ARY-7f3a9c11.", id="canary-split-by-markup"),
        pytest.param("My marker is canary-7F3A9C11.", id="canary-other-case"),
        pytest.param("My marker is C A N A R Y - 7 f 3 a 9 c 1 1.", id="canary-spaced-out"),
        pytest.param("My marker is CANARY\u200b-7f3a9c11.", id="canary-with-invisible-character"),
        pytest.param("The key is gsk_<i></i>abcdefghij1234567890", id="key-split-by-markup"),
        pytest.param(
            # A tag after every fifth word breaks the 12-word window in the raw text only.
            " ".join(
                word + ("<b></b>" if number % 5 == 4 else "")
                for number, word in enumerate(RULES.split()[30:45])
            ),
            id="copied-rules-split-by-markup",
        ),
    ],
)
def test_leaks_are_replaced_by_the_refusal(validator: OutputValidator, leaky: str) -> None:
    result = validator.validate(model(leaky), Locale.ES)

    assert (result.text, result.refused, result.reason) == (REFUSALS[Locale.ES], True, "leak")


def test_a_short_quote_of_the_rules_is_not_a_leak(validator: OutputValidator) -> None:
    quote = " ".join(RULES.split()[30:36])

    assert not validator.validate(model(f"Johan is {quote}."), Locale.EN).refused


def test_two_numbered_lines_are_fine(validator: OutputValidator) -> None:
    answer = "He used:\n1. FastAPI\n2. React"

    assert not validator.validate(model(answer), Locale.EN).refused


def test_links_to_johans_own_pages_are_kept(validator: OutputValidator) -> None:
    text = f"See {LINKEDIN_URL}, {GITHUB_URL}/portfolio, {SITE}/es/ or email {CONTACT_EMAIL}."

    result = validator.validate(model(text), Locale.EN)

    assert result.text == text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Visit https://evil.example/login now", "Visit now"),
        (f"See {GITHUB_URL}-evil for more", "See for more"),
        (f"Go to {SITE}.evil.com now", "Go to now"),
        ("Open https://evil.example/https://github.com/Joalregra", "Open"),
        ("Write to someone.else@example.com please", "Write to please"),
        ("Write to mailto:attacker@evil.example please", "Write to please"),
        ("Look: ![x](https://evil.example/p.png?q=secret) done", "Look: done"),
        ("Hello <b>world</b> and <script>x</script>", "Hello world and x"),
    ],
)
def test_other_links_images_emails_and_html_are_removed(
    validator: OutputValidator, text: str, expected: str
) -> None:
    result = validator.validate(model(text), Locale.EN)

    assert result.text == expected


def test_a_trailing_full_stop_does_not_break_an_allowed_link(validator: OutputValidator) -> None:
    result = validator.validate(model(f"Find him at {GITHUB_URL}."), Locale.EN)

    assert result.text == f"Find him at {GITHUB_URL}."


def test_odd_hyphens_and_spaces_become_plain_ones(validator: OutputValidator) -> None:
    result = validator.validate(model("back‑ends and front‐ends"), Locale.EN)

    assert result.text == "back-ends and front-ends"


def test_an_answer_that_is_only_a_removed_link_is_empty(validator: OutputValidator) -> None:
    result = validator.validate(model("https://evil.example/x"), Locale.EN)

    assert (result.refused, result.reason) == (True, "empty")


def test_the_quick_answer_about_contact_is_not_mistaken_for_a_leak(
    validator: OutputValidator,
) -> None:
    # Listing the same links the rules mention is exactly what a contact answer must do.
    text = f"Email: {CONTACT_EMAIL}. LinkedIn: {LINKEDIN_URL}. GitHub: {GITHUB_URL}."

    result = validator.validate(model(text, section="contact"), Locale.EN)

    assert not result.refused
    assert result.text == text
