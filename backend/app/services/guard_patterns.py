"""Data for the input guard: phrases and words used to spot prompt injection (PI-03).

Kept apart from the logic so the lists can grow without touching the code, and so the tests
can show which phrases are caught and which normal questions are not. Everything is matched
on folded text: lowercase, accents removed.
"""

import re
from typing import Final

# Verb followed, within a short distance, by the thing being attacked.
OVERRIDE_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    "ignore_instructions": re.compile(
        r"\b(ignor\w*|olvid\w*|omit\w*|desestim\w*|salt\w*|disregard|forget|override|bypass|skip)\b"
        r".{0,50}\b(instruc\w*|regla\w*|indicacion\w*|restriccion\w*|instruction\w*|rule\w*|"
        r"prompt|guideline\w*|directive\w*|restriction\w*|polic\w*|politica\w*)\b"
    ),
    "ignore_previous": re.compile(
        r"\b(ignor\w*|olvid\w*|forget|disregard)\b.{0,20}\b(previous|prior|above|earlier|"
        r"anterior\w*|previa\w*|arriba)\b"
    ),
    "new_instructions": re.compile(
        r"\b(nuevas?|new)\s+(instrucc\w*|reglas?|rules?|instructions?)\b.{0,20}\b(son|are|:)"
    ),
}

EXTRACTION_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    "system_prompt": re.compile(
        r"\b(system|developer|hidden|initial|original|internal)\s+"
        r"(prompt|message|instructions?|rules)\b|\bprompt\s+(del\s+)?(sistema|system)\b"
    ),
    "reveal_instructions": re.compile(
        r"\b(revela\w*|muestra\w*|repite\w*|imprime\w*|escribe\w*|dime|reveal|show|print|repeat|"
        r"display|tell me|output|leak|dump)\b.{0,40}"
        r"\b(tus?\s+instrucc\w*|tus?\s+reglas|tu\s+prompt|your\s+(instructions|rules|prompt)|"
        r"configuracion\s+inicial|initial\s+configuration|texto\s+de\s+arriba|text\s+above)\b"
    ),
    # Asking what the rules are needs no "reveal" verb: "what are your instructions?". Only
    # "your" or "tus", so "give me the instructions to contact him" stays a normal question.
    "ask_for_instructions": re.compile(
        r"\b(what\s+(are|is)|give\s+me|list|summari[sz]e|translate|print|output|"
        r"cuales\s+son|cual\s+es|enumera\w*|traduce\w*|resume\w*|dame|muestrame)\b.{0,30}"
        r"\b(your|tus?)\s+(system\s+|internal\s+|hidden\s+|initial\s+)?"
        r"(instructions|prompt|instrucciones|instrucc\w*\s+internas)\b"
    ),
    # "Rules" alone is a normal word ("what are your rules about relocation?"), so it needs a
    # verb that only makes sense for extracting text.
    "extract_rules": re.compile(
        r"\b(translate|summari[sz]e|print|repeat|list|traduce\w*|resume\w*|imprime\w*|"
        r"enumera\w*)\b.{0,30}\b(your|tus?)\s+(rules|reglas)\b"
    ),
    "repeat_above": re.compile(
        r"\b(repite|repeat)\b.{0,20}\b(texto|palabras|text|words)\b.{0,20}\b(arriba|above|anterior)\b"
    ),
}

JAILBREAK_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    # Only commands to switch a mode on, so "experience with a developer mode in Laravel" and
    # "has no restrictions to relocate" are left alone.
    "jailbreak_name": re.compile(
        r"\b(do anything now|jailbreak)\b|"
        r"\b(enable|activate|enter|switch to|turn on|activa\w*|entra en|pasa a)\s+(the\s+|el\s+)?"
        r"(developer|god|dan|desarrollador|dios)\s+mode\b|"
        r"\b(activa\w*|habilita\w*|entra en|pasa a)\s+(el\s+)?modo\s+(desarrollador|dios)\b"
    ),
    # Imperatives at the start of a sentence, so "Johan acts as team lead" is not a hit.
    "role_switch": re.compile(
        r"(?:^|[.!?]\s*)(?:ahora\s+)?(?:actua\s+como|finge\s+(?:ser|que)|haz\s+de|comportate\s+como|"
        r"act\s+as|pretend\s+(?:to\s+be|you)|roleplay|you\s+are\s+now|from\s+now\s+on\s+you|"
        r"a\s+partir\s+de\s+ahora\s+eres|ahora\s+eres)\b"
    ),
}

# A long unbroken run of letters or digits is almost always an encoded payload (PI-03).
ENCODED_BLOCK: Final = re.compile(r"[A-Za-z0-9+/=]{48,}|(?:[0-9a-fA-F]{2}[\s:]?){24,}")

# Long attack phrases, checked with every space and symbol removed, so a filler character inside a
# word ("ig<blank>nore") or letters spread out ("i g n o r e") do not hide them. Long on purpose:
# a short one could appear by chance across the words of a normal question.
SQUASHED_PHRASES: Final = (
    "ignorepreviousinstructions",
    "ignoreallpreviousinstructions",
    "disregardpreviousinstructions",
    "ignoreyourinstructions",
    "revealyoursystemprompt",
    "revealthesystemprompt",
    "ignoratusinstrucciones",
    "ignoralasinstrucciones",
    "ignoraslasinstrucciones",
    "olvidatusinstrucciones",
    "olvidalasinstrucciones",
)

# Typoglycemia: a word with the same first and last letter and the same letters in between,
# in any order ("ignroe", "revael"). Only flagged when a verb and a target both show up and at
# least one is scrambled, so exact words are left to the patterns above.
SCRAMBLE_VERBS: Final = ("ignore", "forget", "disregard", "reveal", "override", "bypass")
SCRAMBLE_TARGETS: Final = ("instructions", "previous", "prompt", "system", "rules", "guidelines")
SCRAMBLE_MIN_LENGTH: Final = 5
