import shutil
from pathlib import Path

import pytest

from app.core.config import BASE_DIR
from app.core.locale import Locale
from app.schemas.chat import QUICK_QUESTION_IDS
from app.services.knowledge import ENGLISH_FILE, SPANISH_FILE, KnowledgeError, load_knowledge

REAL_DIR = BASE_DIR / "knowledge"


@pytest.fixture
def knowledge_dir(tmp_path: Path) -> Path:
    """A copy of the real files that a test can break without touching the originals."""
    for name in (ENGLISH_FILE, SPANISH_FILE):
        shutil.copy(REAL_DIR / name, tmp_path / name)
    return tmp_path


def test_every_quick_question_has_an_answer_in_both_languages() -> None:
    knowledge = load_knowledge(REAL_DIR)

    for locale in Locale:
        for question_id in QUICK_QUESTION_IDS:
            assert len(knowledge.quick_answer(question_id, locale)) > 40


def test_quick_answers_are_in_the_requested_language() -> None:
    knowledge = load_knowledge(REAL_DIR)

    assert "Johan" in knowledge.quick_answer("availability", Locale.EN)
    assert "disponible" in knowledge.quick_answer("availability", Locale.ES)
    assert "available" in knowledge.quick_answer("availability", Locale.EN)


def test_prompt_text_holds_the_facts_but_not_the_rules_or_the_quick_answers() -> None:
    text = load_knowledge(REAL_DIR).prompt_text

    assert text.startswith("## 1. Profile Summary")
    assert "## 8. How Johan Works" in text
    assert "Assistant Instructions" not in text
    assert "## 9." not in text
    assert "Quick Questions" not in text


def test_version_changes_when_a_file_changes(knowledge_dir: Path) -> None:
    before = load_knowledge(knowledge_dir).version

    spanish = knowledge_dir / SPANISH_FILE
    spanish.write_text(spanish.read_text(encoding="utf-8") + "\nNueva línea.\n", encoding="utf-8")

    assert load_knowledge(knowledge_dir).version != before


def test_missing_file_stops_the_start(tmp_path: Path) -> None:
    with pytest.raises(KnowledgeError, match="Cannot read"):
        load_knowledge(tmp_path)


def test_empty_file_stops_the_start(knowledge_dir: Path) -> None:
    (knowledge_dir / ENGLISH_FILE).write_text("  \n", encoding="utf-8")

    with pytest.raises(KnowledgeError, match="empty"):
        load_knowledge(knowledge_dir)


def test_reworded_quick_question_stops_the_start(knowledge_dir: Path) -> None:
    english = knowledge_dir / ENGLISH_FILE
    text = english.read_text(encoding="utf-8")
    english.write_text(
        text.replace("What was your hardest technical challenge?", "Hardest challenge?"),
        encoding="utf-8",
    )

    with pytest.raises(KnowledgeError, match="challenge"):
        load_knowledge(knowledge_dir)


def test_missing_section_stops_the_start(knowledge_dir: Path) -> None:
    english = knowledge_dir / ENGLISH_FILE
    text = english.read_text(encoding="utf-8")
    english.write_text(text.replace("## 4. Tech Stack", "## Tech Stack"), encoding="utf-8")

    with pytest.raises(KnowledgeError, match="sections 1 to 8"):
        load_knowledge(knowledge_dir)


def test_each_button_has_its_own_question_text_in_both_languages() -> None:
    knowledge = load_knowledge(REAL_DIR)

    assert knowledge.quick_question("challenge", Locale.EN) == (
        "What was your hardest technical challenge?"
    )
    assert knowledge.quick_question("ai", Locale.ES) == "\u00bfUsas IA al programar?"
