from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from time import time
from typing import Any

try:
    from .replies import REPLIES, get_reply
except ImportError:
    from replies import REPLIES, get_reply


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

ViolationCategory = str

WORD_LEFT = r"(?<![а-яa-z0-9_])"
WORD_RIGHT = r"(?![а-яa-z0-9_])"

EXTRA_PROFANITY_WORDS_FILE = Path(__file__).with_name("words.txt")
ADAB_BAD_WORDS_FILE = Path(__file__).with_name("adab_bad_words_ru.txt")


@dataclass(frozen=True)
class RuleSettings:
    flood_messages_limit: int = 5
    flood_time_window_seconds: int = 20
    caps_min_length: int = 15
    caps_ratio: float = 0.7


NORMAL_SHORT_MESSAGES = frozenset(
    {
        "да",
        "нет",
        "ок",
        "окей",
        "ага",
        "угу",
        "ну",
        "не",
    }
)


# Редактируемые локальные списки. Vulgar/word-specific проверяются до profanity, чтобы не писать 'без мата' на не-мат.
WORD_SPECIFIC_REPLIES = {
    "половой орган": {
        "category": "vulgar_language",
        "reply": "Брат, ради Аллаха, давай без неприличных выражений.",
    },
    "моча": {
        "category": "vulgar_language",
        "reply": "Пусть Аллах поможет нам сохранять чистоту речи.",
    },
    "кал": {
        "category": "vulgar_language",
        "reply": "Брат, ради Аллаха, давай без грубых слов.",
    },
    "калл": {
        "category": "vulgar_language",
        "reply": "Брат, ради Аллаха, давай без грубых слов.",
    },
    "говно": {
        "category": "vulgar_language",
        "reply": "Сохраним чистоту речи ради Аллаха.",
    },
    "писька": {
        "category": "vulgar_language",
        "reply": "Брат, ради Аллаха, давай без неприличных слов.",
    },
    "писка": {
        "category": "vulgar_language",
        "reply": "Брат, ради Аллаха, давай без неприличных слов.",
    },
    "дрочил": {
        "category": "vulgar_language",
        "reply": "Пусть Аллах поможет нам сохранять адаб в словах.",
    },
    "дрочить": {
        "category": "vulgar_language",
        "reply": "Пусть Аллах поможет нам сохранять адаб в словах.",
    },
    "дрочка": {
        "category": "vulgar_language",
        "reply": "Пусть Аллах поможет нам сохранять адаб в словах.",
    },
    "член": {
        "category": "vulgar_language",
        "reply": "Брат, ради Аллаха, давай без неприличных выражений.",
    },
    "пенис": {
        "category": "vulgar_language",
        "reply": "Брат, ради Аллаха, давай без неприличных выражений.",
    },
    "жопа": {
        "category": "vulgar_language",
        "reply": "Сохраним чистоту речи ради Аллаха.",
    },
    "задница": {
        "category": "vulgar_language",
        "reply": "Сохраним чистоту речи ради Аллаха.",
    },
    "тряпка": {
        "category": "personal_insult",
        "reply": "Брат, ради Аллаха, давай без унизительных слов в адрес людей.",
    },
}

PROFANITY_PATTERNS = [
    r"н\s*а\s*х\s*у\s*[ийеюя][а-я]*",
    r"п\s*о\s*х\s*у\s*[ийеюя][а-я]*",
    r"х\s*у\s*[ийеюя][а-я]*",
    r"х\s*е\s*р[а-я]*",
    r"п\s*и\s*з\s*д[а-я]*",
    r"п\s*з\s*д\s*ц",
    r"б\s*л\s*[яа](?:т[ьб]?[а-я]*|д[ьб]?[а-я]*)?",
    r"е\s*б[а-я]*",
    r"ё\s*б[а-я]*",
    r"за\s*е\s*б[а-я]*",
    r"у\s*е\s*б[а-я]*",
    r"вы\s*е\s*б[а-я]*",
    r"под\s*ъ?\s*е\s*б[а-я]*",
    r"долбо\s*е\s*б[а-я]*",
    r"ах\s*у\s*е[а-я]*",
    r"муд[ао]к[а-я]*",
    r"пош[её]л\s+ты",
    r"пошла\s+ты",
    r"пошли\s+вы",
]

VULGAR_PATTERNS = [
    r"анус[а-я]*",
    r"вагин[а-я]*",
    r"влагалищ[а-я]*",
    r"говн[а-я]*",
    r"дерьм[а-я]*",
    r"жоп[а-я]*",
    r"задниц[а-я]*",
    r"испражнен[а-я]*",
    r"испражнят[а-я]*",
    r"какаш[а-я]*",
    r"калл?",
    r"моч[а-я]*",
    r"пенис[а-я]*",
    r"пис[ь]?к[а-я]*",
    r"полов[а-я]*\s+орган[а-я]*",
    r"дроч[а-я]*",
    r"минет[а-я]*",
    r"отсос[а-я]*",
    r"сосать",
    r"соси",
    r"секс[а-я]*",
    r"трах[а-я]*",
    r"фекал[а-я]*",
    r"член[а-я]*",
]

INSULT_PATTERNS = [
    r"идиот[а-я]*",
    r"туп(?:ой|ая|ое|ые|ого|ому|ым|ыми|ых|ую|о)?",
    r"дурак[а-я]*",
    r"дур(?:а|ы|ой|у|ой|ами|ах)",
    r"дебил[а-я]*",
    r"кретин[а-я]*",
    r"болван[а-я]*",
    r"безмозгл[а-я]*",
    r"ничтожество",
    r"имбецил[а-я]*",
    r"мраз[а-я]*",
    r"конченн?[а-я]*",
    r"сук[аиуеой]*",
    r"суч[а-я]*",
    r"твар[а-я]*",
    r"урод[а-я]*",
    r"чмо",
    r"слаб(?:ый|ая|ое|ые|ого|ому|ым|ыми|ых|ую|о)",
]

RUDE_COMMAND_PATTERNS = [
    r"заткнись",
    r"закрой\s+рот",
    r"(?:ты\s+)?(?:вообще\s+)?молчи(?:\s+уже)?",
    r"лучше\s+молчи",
]

THREAT_PATTERNS = [
    r"(?:я\s+)?(?:тебя|вас|его|ее|их)\s+(?:убью|побью|изобью|зарежу|порежу|сломаю)",
    r"(?:убью|побью|изобью|зарежу|порежу|сломаю)\s+(?:тебя|вас|его|ее|их)",
    r"найду\s+(?:тебя|вас)?\s*и\s+(?:убью|побью|изобью|зарежу|порежу|сломаю)",
    r"найду\s+и\s+разберусь",
    r"разберусь\s+с\s+(?:тобой|вами|ним|ней)",
    r"побью",
    r"сломаю\s+(?:тебе|вам|ему|ей|им)",
]

MOCKERY_PATTERNS = [
    r"(?:ты|вы|он|она|они)\s+(?:жалк[а-я]*|посмешище|смешон|смешна|смешны)",
    r"(?:смеюсь|угараю)\s+(?:с\s+тебя|над\s+тобой|над\s+вами)",
]

PROVOCATION_PATTERNS = [
    r"слабо\s+(?:сказать|повторить)\s+(?:в\s+лицо|при\s+встрече)",
    r"скажи\s+(?:это\s+)?в\s+лицо",
    r"выйди\s+(?:поговорим|разберемся)",
    r"давай\s+встретимся\s+и\s+разберемся",
]

RELIGIOUS_TERMS = (
    "кяфир",
    "муртад",
    "заблудший",
    "такфир",
    "ширк",
    "куфр",
    "ахлю сунна",
    "саляфит",
    "ашарит",
    "хариджит",
    "рафидит",
    "джахмит",
    "неверующий",
    "неверие",
    "мурджиит",
    "матуридит",
    "мазхаб",
)

SAFE_RELIGIOUS_OR_EDUCATIONAL_MARKERS = (
    "хадис",
    "книга",
    "сунан",
    "ат-тирмизи",
    "посланник аллаха",
    "мир ему и благословение аллаха",
    "да будет доволен им аллах",
    "да помилует его аллах",
    "да обрадует",
    "хвала аллаху",
    "с именем аллаха",
    "пусть аллах",
    "мы просим у аллаха",
    "поносит аллаха",
    "аллаха и его посланника",
    "ин ша аллах",
    "баракаллаху",
    "джазака ллаху хайран",
    "шейх",
    "имам",
    "шарх",
    "иснад",
    "передают со слов",
    "ученик",
    "ученики",
    "учебный модуль",
    "марказ",
    "учебная программа",
    "урок",
    "знания",
    "талабуль илм",
    "фатва",
    "дуа",
    "ду'а",
    "мазхаб",
    "мурджиит",
    "мурджиитов",
    "ашарит",
    "саляфит",
    "матуридит",
    "кяфир",
    "неверующий",
    "неверие",
    "слова неверия",
    "такфир",
    "ширк",
    "куфр",
)

MEDICAL_OR_EDUCATIONAL_WORDS = (
    "анализ",
    "медицин",
    "медицинский",
    "медицина",
    "врач",
    "учебник",
    "анатомия",
    "строение",
    "термин",
    "биология",
    "лаборатория",
    "сдача анализа",
    "сдача",
)

EXPLICIT_CHLEN_CONTEXTS = (
    "сосать член",
    "соси член",
    "покажи член",
    "мой член",
    "твой член",
    "его член",
    "ее член",
)

SAFE_SOSAT_CONTEXTS = (
    "сосет палец",
    "сосет воздух",
    "сосать палец",
    "сосать леденец",
    "сосать конфету",
    "насос сосет",
)

SAFE_TRYAPKA_PATTERNS = (
    r"тряпк[а-я]*\s+(?:лежит|для|мокр[а-я]*|сух[а-я]*)",
    r"(?:мокр[а-я]*|сух[а-я]*|грязн[а-я]*|чист[а-я]*)\s+тряпк[а-я]*",
    r"(?:возьми|протри|убери|намочи|выжми)\s+тряпк[а-я]*",
    r"протри\s+тряпк[а-я]*",
)

SAFE_TUPOY_PATTERNS = (
    r"туп(?:ой|ая|ое|ые|ого|ую|ым|ыми|ых)?\s+угол",
    r"туп(?:ой|ая|ое|ые|ого|ую|ым|ыми|ых)?\s+нож",
    r"туп(?:ой|ая|ое|ые|ого|ую|ым|ыми|ых)?\s+боль",
    r"туп(?:ой|ая|ое|ые|ого|ую|ым|ыми|ых)?\s+звук",
    r"туп(?:ой|ая|ое|ые|ого|ую|ым|ыми|ых)?\s+предмет",
    r"туп(?:ой|ая|ое|ые|ого|ую|ым|ыми|ых)?\s+сторон[а-я]*(?:\s+ножа)?",
)

SAFE_SLABY_PATTERNS = (
    r"слаб[а-я]*\s+(?:хадис|иснад|передатчик|довод|мнение)",
    r"(?:хадис|иснад|передатчик|довод|мнение)\s+(?:очень\s+)?слаб[а-я]*",
)

CAPS_PRESSURE_PATTERNS = (
    r"ты\s+что",
    r"ты(?:\s+[а-я]+){0,4}\s+не\s+понимаешь",
    r"я\s+сказал",
    r"не\s+пиши",
    r"не\s+смей",
    r"хватит",
    r"замолчи",
    r"сюда\s+больше",
)


def _compile_word_patterns(patterns: list[str]) -> list[tuple[str, re.Pattern[str]]]:
    return [
        (pattern, re.compile(f"{WORD_LEFT}(?:{pattern}){WORD_RIGHT}", re.IGNORECASE))
        for pattern in patterns
    ]


def _compile_word_pattern(patterns: list[str]) -> re.Pattern[str]:
    joined = "|".join(f"(?:{pattern})" for pattern in patterns)
    return re.compile(f"{WORD_LEFT}(?:{joined}){WORD_RIGHT}", re.IGNORECASE)


def _compile_optional_word_pattern(patterns: list[str]) -> re.Pattern[str] | None:
    if not patterns:
        return None
    return _compile_word_pattern(patterns)


def normalize_text(text: str | None) -> str:
    if not text:
        return ""

    normalized = text.lower().replace("ё", "е")
    normalized = normalized.replace("’", "'").replace("`", "'").replace("ʼ", "'")
    normalized = re.sub(r"(?<=[а-яa-z])\.(?=[а-яa-z])", "", normalized)
    normalized = normalized.translate(
        str.maketrans(
            {
                "@": "а",
                "0": "о",
                "3": "з",
                "4": "ч",
                "6": "б",
                "1": "и",
                "!": "и",
                "*": "",
                "_": "",
                "-": "",
            }
        )
    )
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def is_safe_religious_or_educational_context(text: str | None) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return False

    return any(
        normalize_text(marker) in normalized
        for marker in SAFE_RELIGIOUS_OR_EDUCATIONAL_MARKERS
    )


def _word_or_phrase_pattern(value: str, suffix: bool = True) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return ""

    escaped = re.escape(normalized).replace(r"\ ", r"\s+")
    if suffix and re.fullmatch(r"[а-яa-z]+", normalized):
        escaped = f"{escaped}[а-яa-z]*"
    return escaped


def _compile_extra_words(
    words: set[str],
    suffix: bool = True,
) -> list[tuple[str, re.Pattern[str]]]:
    compiled: list[tuple[str, re.Pattern[str]]] = []
    for word in sorted(words):
        pattern = _word_or_phrase_pattern(word, suffix=suffix)
        if pattern:
            compiled.append(
                (word, re.compile(f"{WORD_LEFT}(?:{pattern}){WORD_RIGHT}", re.IGNORECASE))
            )
    return compiled


def _compile_raw_regexes(patterns: set[str]) -> list[tuple[str, re.Pattern[str]]]:
    compiled: list[tuple[str, re.Pattern[str]]] = []
    for pattern in sorted(patterns):
        if _is_too_broad_external_regex(pattern):
            logger.warning("Skipped too broad regex from %s: %s", ADAB_BAD_WORDS_FILE, pattern)
            continue
        try:
            compiled.append((pattern, re.compile(pattern, re.IGNORECASE)))
        except re.error:
            logger.warning("Skipped invalid regex from %s: %s", ADAB_BAD_WORDS_FILE, pattern)
    return compiled


def _is_too_broad_external_regex(pattern: str) -> bool:
    # This pattern from the imported list matches many ordinary Russian words
    # beginning with "об", "заб", etc. Keep explicit roots instead.
    return "[знпрво]?[ао]?е?б" in pattern


def _is_vulgar_external_regex(pattern: str) -> bool:
    vulgar_roots = (
        "анус",
        "вагин",
        "говн",
        "дроч",
        "жоп",
        "кал",
        "минет",
        "моч",
        "отсос",
        "пенис",
        "сос",
        "трах",
        "фекал",
        "член",
    )
    return any(root in pattern for root in vulgar_roots)


def _is_vulgar_source_word(word: str) -> bool:
    normalized = normalize_text(word)
    vulgar_roots = (
        "анус",
        "вагин",
        "влагалищ",
        "говн",
        "дерьм",
        "дроч",
        "жоп",
        "задниц",
        "испраж",
        "какаш",
        "кал",
        "минет",
        "моч",
        "отсос",
        "пенис",
        "письк",
        "писк",
        "сосать",
        "трах",
        "фекал",
        "член",
    )
    return any(root in normalized for root in vulgar_roots)


def _load_extra_profanity_words() -> frozenset[str]:
    if not EXTRA_PROFANITY_WORDS_FILE.exists():
        return frozenset()

    words: set[str] = set()
    try:
        for line in EXTRA_PROFANITY_WORDS_FILE.read_text(encoding="utf-8").splitlines():
            word = normalize_text(line)
            if word and not word.startswith("#"):
                words.add(word)
    except OSError:
        logger.exception("Failed to load extra profanity words from %s", EXTRA_PROFANITY_WORDS_FILE)
        return frozenset()

    logger.info("Loaded %s extra profanity words from %s", len(words), EXTRA_PROFANITY_WORDS_FILE)
    return frozenset(words)


def _empty_sections() -> dict[str, set[str]]:
    return {
        "profanity_words": set(),
        "profanity_regexes": set(),
        "vulgar_words": set(),
        "insult_words": set(),
        "insult_regexes": set(),
        "rude_commands": set(),
        "threat_words": set(),
    }


def _load_adab_bad_words() -> dict[str, set[str]]:
    sections = _empty_sections()
    if not ADAB_BAD_WORDS_FILE.exists():
        return sections

    current_section = ""
    try:
        lines = ADAB_BAD_WORDS_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        logger.exception("Failed to load bad words from %s", ADAB_BAD_WORDS_FILE)
        return sections

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current_section = line.strip("[]").upper()
            continue

        if current_section == "PROFANITY_ROOTS":
            sections["profanity_words"].add(line)
        elif current_section == "VULGAR_SEXUAL_WORDS":
            sections["vulgar_words"].add(line)
        elif current_section == "PERSONAL_INSULTS":
            sections["insult_words"].add(line)
        elif current_section == "RUDE_COMMANDS":
            sections["rude_commands"].add(line)
        elif current_section == "THREATS":
            sections["threat_words"].add(line)
        elif current_section == "REGEX_PROFANITY_PATTERNS":
            sections["profanity_regexes"].add(line)
        elif current_section == "REGEX_PERSONAL_INSULT_PATTERNS":
            sections["insult_regexes"].add(line)

    logger.info(
        "Loaded adab bad words from %s: profanity=%s vulgar=%s insults=%s threats=%s",
        ADAB_BAD_WORDS_FILE,
        len(sections["profanity_words"]) + len(sections["profanity_regexes"]),
        len(sections["vulgar_words"]),
        len(sections["insult_words"]) + len(sections["insult_regexes"]),
        len(sections["threat_words"]),
    )
    return sections


ADAB_BAD_WORDS = _load_adab_bad_words()
PROFANITY_RES = _compile_word_patterns(PROFANITY_PATTERNS)
VULGAR_RES = _compile_word_patterns(VULGAR_PATTERNS)
EXTRA_PROFANITY_WORDS = _load_extra_profanity_words()
ADAB_INSULT_PATTERNS = [_word_or_phrase_pattern(word) for word in ADAB_BAD_WORDS["insult_words"]]
ALL_INSULT_PATTERNS = [pattern for pattern in INSULT_PATTERNS + ADAB_INSULT_PATTERNS if pattern]
INSULT_PATTERN_GROUP = "|".join(f"(?:{pattern})" for pattern in ALL_INSULT_PATTERNS)
QUOTE_CHARS = "\"'«»“”„"
EXTRA_PROFANITY_RES = _compile_extra_words(
    {
        word
        for word in ADAB_BAD_WORDS["profanity_words"]
        if not _is_vulgar_source_word(word)
    },
    suffix=True,
)
EXTRA_PROFANITY_RAW_RES = _compile_raw_regexes(
    {
        pattern
        for pattern in ADAB_BAD_WORDS["profanity_regexes"]
        if not _is_vulgar_external_regex(pattern)
    }
)
EXTRA_VULGAR_RES = _compile_extra_words(
    ADAB_BAD_WORDS["vulgar_words"]
    | {
        word
        for word in ADAB_BAD_WORDS["profanity_words"]
        if _is_vulgar_source_word(word)
    },
    suffix=True,
)
EXTRA_VULGAR_RAW_RES = _compile_raw_regexes(
    {
        pattern
        for pattern in ADAB_BAD_WORDS["profanity_regexes"]
        if _is_vulgar_external_regex(pattern)
    }
)
EXTRA_INSULT_RE = _compile_optional_word_pattern(ALL_INSULT_PATTERNS)
EXTRA_INSULT_RAW_RES = _compile_raw_regexes(ADAB_BAD_WORDS["insult_regexes"])
RUDE_COMMAND_RE = _compile_word_pattern(
    RUDE_COMMAND_PATTERNS + [_word_or_phrase_pattern(word, suffix=False) for word in ADAB_BAD_WORDS["rude_commands"]]
)
THREAT_RE = _compile_word_pattern(
    THREAT_PATTERNS + [_word_or_phrase_pattern(word, suffix=False) for word in ADAB_BAD_WORDS["threat_words"]]
)
MOCKERY_RE = _compile_word_pattern(MOCKERY_PATTERNS)
PROVOCATION_RE = _compile_word_pattern(PROVOCATION_PATTERNS)
NEGATED_INSULT_RE = re.compile(
    rf"{WORD_LEFT}не\s+[{QUOTE_CHARS}]*(?:{INSULT_PATTERN_GROUP})[{QUOTE_CHARS}]*{WORD_RIGHT}",
    re.IGNORECASE,
)
PERSONAL_INSULT_RE = re.compile(
    rf"{WORD_LEFT}(?:ты|вы|тебя|тебе|тобой|вас|вам|вами|твой|твоя|твои|ваш|ваша|ваши)"
    rf"(?:\s+[а-яa-z0-9_]+){{0,4}}\s+[{QUOTE_CHARS}]*"
    rf"(?:{INSULT_PATTERN_GROUP})[{QUOTE_CHARS}]*{WORD_RIGHT}",
    re.IGNORECASE,
)
REVERSE_PERSONAL_INSULT_RE = re.compile(
    rf"{WORD_LEFT}[{QUOTE_CHARS}]*(?:{INSULT_PATTERN_GROUP})[{QUOTE_CHARS}]*"
    rf"(?:\s+[а-яa-z0-9_]+){{0,2}}\s+"
    rf"(?:ты|вы|тебя|вас){WORD_RIGHT}",
    re.IGNORECASE,
)
SELF_PERSONAL_INSULT_RE = re.compile(
    rf"{WORD_LEFT}сам(?:а|и)?\s+[{QUOTE_CHARS}]*(?:{INSULT_PATTERN_GROUP})[{QUOTE_CHARS}]*{WORD_RIGHT}",
    re.IGNORECASE,
)
SAFE_INSULT_REFERENCE_RES = [
    re.compile(
        rf"{WORD_LEFT}(?:слово|термин|выражение)\s+[{QUOTE_CHARS}]*(?:{INSULT_PATTERN_GROUP})[{QUOTE_CHARS}]*{WORD_RIGHT}",
        re.IGNORECASE,
    ),
    re.compile(
        rf"{WORD_LEFT}(?:не\s+говори|не\s+пиши|не\s+используй)\s+(?:слово\s+)?[{QUOTE_CHARS}]*(?:{INSULT_PATTERN_GROUP})[{QUOTE_CHARS}]*{WORD_RIGHT}",
        re.IGNORECASE,
    ),
    re.compile(
        rf"{WORD_LEFT}нельзя\s+(?:говорить|писать|употреблять)\s+(?:слово\s+)?[{QUOTE_CHARS}]*(?:{INSULT_PATTERN_GROUP})[{QUOTE_CHARS}]*{WORD_RIGHT}",
        re.IGNORECASE,
    ),
]


def check_word_specific(normalized: str) -> dict[str, Any] | None:
    for word, data in WORD_SPECIFIC_REPLIES.items():
        pattern = _word_or_phrase_pattern(word, suffix=False)
        if pattern and re.search(f"{WORD_LEFT}(?:{pattern}){WORD_RIGHT}", normalized, re.IGNORECASE):
            if data["category"] == "vulgar_language" and _is_safe_vulgar_context(word, normalized):
                continue
            if word == "тряпка" and not (
                _is_personal_context(normalized) or _is_isolated_word(normalized, word)
            ):
                continue
            return {
                "word": word,
                "category": data["category"],
                "reply": data["reply"],
            }
    return None


def check_profanity(normalized: str) -> str | None:
    # Защита от ложного "profanity":
    # если слово/фраза явно отнесены к vulgar_language, check_profanity не должен срабатывать.
    specific = check_word_specific(normalized)
    if specific is not None and specific.get("category") == "vulgar_language":
        return None

    # Если vulgar-паттерн уже нашёл не безопасное слово, это не мат, а category="vulgar_language".
    for pattern, regex in VULGAR_RES:
        match = regex.search(normalized)
        if match and not _is_safe_vulgar_context(match.group(0), normalized):
            return None
    for pattern, regex in EXTRA_VULGAR_RES:
        match = regex.search(normalized)
        if match and not _is_safe_vulgar_context(match.group(0), normalized):
            return None
    for pattern, regex in EXTRA_VULGAR_RAW_RES:
        match = regex.search(normalized)
        if match and not _is_safe_vulgar_context(match.group(0), normalized):
            return None

    for pattern, regex in PROFANITY_RES:
        if regex.search(normalized):
            return pattern
    for pattern, regex in EXTRA_PROFANITY_RES:
        if regex.search(normalized):
            return f"{ADAB_BAD_WORDS_FILE.name}:{pattern}"
    for pattern, regex in EXTRA_PROFANITY_RAW_RES:
        if regex.search(normalized):
            return f"{ADAB_BAD_WORDS_FILE.name}:{pattern}"

    for word in re.findall(r"[а-яa-z]+", normalized):
        if word in EXTRA_PROFANITY_WORDS and not _is_vulgar_word(word):
            return f"words.txt:{word}"

    return None


def check_vulgar_language(normalized: str) -> str | None:
    for pattern, regex in VULGAR_RES:
        match = regex.search(normalized)
        if match and not _is_safe_vulgar_context(match.group(0), normalized):
            return pattern
    for pattern, regex in EXTRA_VULGAR_RES:
        match = regex.search(normalized)
        if match and not _is_safe_vulgar_context(match.group(0), normalized):
            return f"{ADAB_BAD_WORDS_FILE.name}:{pattern}"
    for pattern, regex in EXTRA_VULGAR_RAW_RES:
        match = regex.search(normalized)
        if match and not _is_safe_vulgar_context(match.group(0), normalized):
            return f"{ADAB_BAD_WORDS_FILE.name}:{pattern}"

    for word in re.findall(r"[а-яa-z]+", normalized):
        if (
            word in EXTRA_PROFANITY_WORDS
            and _is_vulgar_word(word)
            and not _is_safe_vulgar_context(word, normalized)
        ):
            return f"words.txt:{word}"

    return None


def check_personal_insult(normalized: str) -> str | None:
    checked_text = _clean_insult_text(normalized)
    if not checked_text:
        return None

    if _word_or_phrase_matches("тряпка", checked_text):
        if _is_personal_context(checked_text) or _is_isolated_word(checked_text, "тряпка"):
            return "тряпка"

    match = SELF_PERSONAL_INSULT_RE.search(checked_text)
    if match:
        return _find_insult(match.group(0)) or match.group(0)

    match = PERSONAL_INSULT_RE.search(checked_text)
    if match:
        return _find_insult(match.group(0)) or match.group(0)

    match = REVERSE_PERSONAL_INSULT_RE.search(checked_text)
    if match:
        return _find_insult(match.group(0)) or match.group(0)

    match = RUDE_COMMAND_RE.search(checked_text)
    if match:
        return match.group(0)

    for pattern, regex in EXTRA_INSULT_RAW_RES:
        if regex.search(checked_text):
            return pattern

    words = re.findall(r"[а-яa-z0-9_]+", checked_text)
    if len(words) == 1:
        return _find_insult(checked_text)

    return None


def check_insulting_language(normalized: str) -> str | None:
    checked_text = _clean_insult_text(normalized)
    if not checked_text:
        return None

    if _word_or_phrase_matches("тряпка", checked_text) and not _is_safe_tryapka_context(checked_text):
        return "тряпка"

    return _find_insult(checked_text)


def check_message(
    text: str | None,
    user_id: int,
    chat_id: int,
    recent_messages: list[dict[str, Any]] | None = None,
    settings: Any | None = None,
) -> dict[str, Any]:
    original_text = text or ""
    normalized = normalize_text(original_text)

    def finish(result: dict[str, Any], matched: str | None) -> dict[str, Any]:
        if result["category"] != "none" and not matched:
            logger.warning(
                "[FALSE_POSITIVE_GUARD] category=%s reason=%s",
                result["category"],
                result["reason"],
            )
            result = _no_violation()
        return _debug_result(result, matched, original_text, normalized)

    logger.debug("Moderation input: has_text=%s length=%s", bool(original_text), len(original_text))
    if not normalized:
        return finish(_no_violation(), None)

    threat_match = THREAT_RE.search(normalized)
    if threat_match:
        return finish(
            _violation("threat", "найдена прямая угроза", user_id, chat_id),
            threat_match.group(0),
        )

    provocation_match = PROVOCATION_RE.search(normalized)
    if provocation_match:
        return finish(
            _violation("provocation", "найдена агрессивная провокация", user_id, chat_id),
            provocation_match.group(0),
        )

    if is_meta_discussion(normalized):
        return finish(_no_violation(), None)

    # Личные оскорбления идут выше общих унизительных слов.
    personal_insult = check_personal_insult(normalized)
    if personal_insult:
        return finish(
            _violation(
                "personal_insult",
                "найдено прямое личное оскорбление",
                user_id,
                chat_id,
            ),
            personal_insult,
        )

    # Оскорбительное слово без прямого обращения к участнику чата.
    insulting_pattern = check_insulting_language(normalized)
    if insulting_pattern:
        return finish(
            _violation(
                "insulting_language",
                "найдено унизительное слово без прямого личного обращения",
                user_id,
                chat_id,
            ),
            insulting_pattern,
        )

    mockery_match = MOCKERY_RE.search(normalized)
    if mockery_match:
        return finish(
            _violation("mockery", "найдена грубая насмешка", user_id, chat_id),
            mockery_match.group(0),
        )

    # Точечные слова/фразы проверяем перед общими vulgar/profanity.
    # Это нужно, чтобы "писька", "дрочил", "говно", "моча", "кал" не уходили в profanity.
    specific_result = check_word_specific(normalized)
    if specific_result is not None:
        result = _specific_violation(specific_result, user_id, chat_id)
        return finish(result, str(specific_result["word"]))

    # Неприличные/грязные слова, но не мат.
    # Должно идти ДО profanity, чтобы бот не писал "без мата" на vulgar_language.
    vulgar_pattern = check_vulgar_language(normalized)
    if vulgar_pattern:
        logger.debug("Moderation vulgar pattern: %s", vulgar_pattern)
        return finish(
            _violation(
                "vulgar_language",
                "грубая или неуместная лексика, но не мат",
                user_id,
                chat_id,
            ),
            vulgar_pattern,
        )

    # Настоящий мат.
    profanity_pattern = check_profanity(normalized)
    if profanity_pattern:
        logger.debug("Moderation profanity pattern: %s", profanity_pattern)
        return finish(_profanity_violation(user_id, chat_id), profanity_pattern)

    rule_settings = _settings_from_config(settings)
    safe_context = is_safe_religious_or_educational_context(original_text)
    if _is_caps_aggression(original_text, rule_settings, safe_context=safe_context):
        return finish(
            _violation(
                "spam_caps",
                "слишком много букв в верхнем регистре",
                user_id,
                chat_id,
            ),
            "агрессивный капс",
        )

    history_result = _check_history(recent_messages or [], rule_settings, user_id, chat_id)
    if history_result:
        result, matched_rule = history_result
        return finish(result, matched_rule)

    return finish(_no_violation(), None)


def _has_personal_insult(normalized: str) -> bool:
    return check_personal_insult(normalized) is not None


def _clean_insult_text(normalized: str) -> str:
    if is_meta_discussion(normalized):
        return ""

    checked_text = normalized
    for regex in SAFE_INSULT_REFERENCE_RES:
        checked_text = regex.sub(" ", checked_text)
    checked_text = NEGATED_INSULT_RE.sub(" ", checked_text)
    return re.sub(r"\s+", " ", checked_text).strip()


def _find_insult(normalized: str) -> str | None:
    if EXTRA_INSULT_RE is None:
        return None
    for match in EXTRA_INSULT_RE.finditer(normalized):
        insult = match.group(0).strip(QUOTE_CHARS)
        if _is_safe_insult_context(insult, normalized):
            continue
        return insult
    return None


def is_meta_discussion(normalized: str) -> bool:
    if not _contains_discussed_term(normalized):
        return False

    meta_patterns = (
        r"(?:слово|термин|выражение)",
        r"(?:сказал|сказала|сказали|написал|написала|написали|говорил|говорила|говорили|пишет|говорит)\s+(?:слово\s+)?",
        r"(?:что\s+значит|что\s+означает|почему\s+слово|можно\s+ли\s+говорить|можно\s+ли\s+писать)",
        r"(?:означает|переводится)",
        r"(?:нельзя\s+говорить|нельзя\s+писать|не\s+используй|не\s+говори|не\s+пиши)",
        r"(?:назвал\s+меня|меня\s+назвали|я\s+не\s+называл|я\s+не\s+говорил|не\s+надо\s+называть)",
        r"есть\s+выражение",
    )
    return any(re.search(pattern, normalized, re.IGNORECASE) for pattern in meta_patterns)


def _contains_discussed_term(normalized: str) -> bool:
    if EXTRA_INSULT_RE is not None and EXTRA_INSULT_RE.search(normalized):
        return True
    if any(_word_or_phrase_matches(term, normalized) for term in RELIGIOUS_TERMS):
        return True
    return any(regex.search(normalized) for _, regex in VULGAR_RES)


def _is_safe_insult_context(insult: str, normalized: str) -> bool:
    if insult.startswith("туп"):
        return any(re.search(pattern, normalized, re.IGNORECASE) for pattern in SAFE_TUPOY_PATTERNS)
    if insult.startswith("тряпк"):
        return _is_safe_tryapka_context(normalized)
    if insult.startswith("слаб"):
        return any(re.search(pattern, normalized, re.IGNORECASE) for pattern in SAFE_SLABY_PATTERNS)
    return False


def _is_safe_tryapka_context(normalized: str) -> bool:
    return any(re.search(pattern, normalized, re.IGNORECASE) for pattern in SAFE_TRYAPKA_PATTERNS)


def _is_safe_vulgar_context(word: str, normalized: str) -> bool:
    checked_word = normalize_text(word).strip(QUOTE_CHARS)

    if checked_word.startswith("член"):
        if any(context in normalized for context in EXPLICIT_CHLEN_CONTEXTS):
            return False
        return True

    if checked_word.startswith("сос"):
        if any(context in normalized for context in SAFE_SOSAT_CONTEXTS):
            return True
        return False

    if checked_word.startswith(("моч", "кал", "калл", "пенис", "полов")):
        return _is_medical_or_educational_context(normalized)

    return False


def _is_medical_or_educational_context(normalized: str) -> bool:
    return any(marker in normalized for marker in MEDICAL_OR_EDUCATIONAL_WORDS)


def _is_personal_context(normalized: str) -> bool:
    return re.search(
        rf"{WORD_LEFT}(?:ты|вы|тебя|тебе|тобой|вас|вам|вами|твой|твоя|твои|ваш|ваша|ваши){WORD_RIGHT}",
        normalized,
    ) is not None


def _is_isolated_word(normalized: str, word: str) -> bool:
    return re.findall(r"[а-яa-z0-9_]+", normalized) == [normalize_text(word)]


def _word_or_phrase_matches(word: str, normalized: str) -> bool:
    pattern = _word_or_phrase_pattern(word, suffix=False)
    return bool(pattern and re.search(f"{WORD_LEFT}(?:{pattern}){WORD_RIGHT}", normalized, re.IGNORECASE))


def _is_vulgar_word(word: str) -> bool:
    return any(regex.search(word) for _, regex in VULGAR_RES) or word in {
        "анус",
        "вагина",
        "влагалище",
        "говно",
        "говнецо",
        "дерьмо",
        "жопа",
        "задница",
        "испражнение",
        "кал",
        "моча",
        "пенис",
        "фекал",
        "фекалий",
        "фекалии",
        "член",
    }


def _is_caps_aggression(
    text: str,
    settings: RuleSettings,
    safe_context: bool = False,
) -> bool:
    stripped = text.strip()
    if len(stripped) <= settings.caps_min_length:
        return False

    letters = [char for char in stripped if char.isalpha()]
    if len(letters) < 8:
        return False

    uppercase = sum(1 for char in letters if char.isupper())
    if uppercase / len(letters) < settings.caps_ratio:
        return False

    if not safe_context:
        return True

    normalized = normalize_text(text)
    return any(re.search(pattern, normalized) for pattern in CAPS_PRESSURE_PATTERNS)


def _history_normalized_text(message: dict[str, Any]) -> str:
    return str(
        message.get("normalized_text") or normalize_text(message.get("message_text", ""))
    ).strip()


def _is_flood_fragment(normalized: str) -> bool:
    words = re.findall(r"[а-яa-z0-9]+", normalized)
    if len(words) != 1:
        return False

    word = words[0]
    if word in NORMAL_SHORT_MESSAGES:
        return False

    return len(word) <= 3


def _has_fragment_flood(
    normalized_messages: list[str],
    settings: RuleSettings,
) -> bool:
    required_messages = max(settings.flood_messages_limit, 1)
    if len(normalized_messages) < required_messages:
        return False

    recent = normalized_messages[-required_messages:]
    fragment_count = sum(1 for message in recent if _is_flood_fragment(message))
    minimum_fragments = min(required_messages, max(4, (required_messages * 4 + 4) // 5))
    return fragment_count >= minimum_fragments


def _check_history(
    recent_messages: list[dict[str, Any]],
    settings: RuleSettings,
    user_id: int,
    chat_id: int,
) -> tuple[dict[str, Any], str] | None:
    if not recent_messages:
        return None

    now = int(max(message.get("created_at", int(time())) for message in recent_messages))
    window_start = now - settings.flood_time_window_seconds
    in_window = [
        message for message in recent_messages if int(message.get("created_at", 0)) >= window_start
    ]

    normalized_messages = [
        _history_normalized_text(message)
        for message in recent_messages
    ]
    normalized_messages = [message for message in normalized_messages if message]
    if len(normalized_messages) >= 3 and len(set(normalized_messages[-3:])) == 1:
        return (
            _violation(
                "repeated_message",
                "три одинаковых сообщения подряд",
                user_id,
                chat_id,
            ),
            "повтор сообщения",
        )

    in_window_normalized = [
        _history_normalized_text(message)
        for message in in_window
    ]
    in_window_normalized = [message for message in in_window_normalized if message]
    if _has_fragment_flood(in_window_normalized, settings):
        return (
            _violation(
                "flood",
                "много очень коротких сообщений за короткое время",
                user_id,
                chat_id,
            ),
            "серия коротких сообщений",
        )

    return None


def _settings_from_config(settings: Any | None) -> RuleSettings:
    if settings is None:
        return RuleSettings()
    return RuleSettings(
        flood_messages_limit=int(getattr(settings, "flood_messages_limit", 5)),
        flood_time_window_seconds=int(getattr(settings, "flood_time_window_seconds", 20)),
        caps_min_length=int(getattr(settings, "caps_min_length", 15)),
        caps_ratio=float(getattr(settings, "caps_ratio", 0.7)),
    )


def _profanity_violation(user_id: int, chat_id: int) -> dict[str, Any]:
    return {
        "violation": True,
        "category": "profanity",
        "reason": "Мат или грубая обсценная лексика.",
        "reply": get_reply("profanity", user_id=user_id, chat_id=chat_id),
    }


def _specific_violation(
    specific_result: dict[str, Any],
    user_id: int,
    chat_id: int,
) -> dict[str, Any]:
    del user_id, chat_id
    return {
        "violation": True,
        "category": str(specific_result["category"]),
        "reason": f"Найдено точечное слово или фраза: {specific_result['word']}.",
        "reply": str(specific_result["reply"]),
    }


def _violation(
    category: ViolationCategory,
    reason: str,
    user_id: int,
    chat_id: int,
) -> dict[str, Any]:
    return {
        "violation": True,
        "category": category,
        "reason": reason,
        "reply": get_reply(category, user_id=user_id, chat_id=chat_id),
    }


def _no_violation() -> dict[str, Any]:
    return {
        "violation": False,
        "category": "none",
        "reason": "",
        "reply": "",
    }


def _debug_result(
    result: dict[str, Any],
    matched: str | None,
    original_text: str = "",
    normalized: str = "",
) -> dict[str, Any]:
    logger.debug(
        "Moderation result: category=%s violation=%s matched=%r reply=%r",
        result["category"],
        result["violation"],
        matched,
        result["reply"],
    )
    if _env_flag("DEBUG_MODERATION"):
        payload = {
            "category": result["category"],
            "matched_word": matched if matched and not any(char in matched for char in r"\[]()*+?") else None,
            "matched_pattern": matched if matched and any(char in matched for char in r"\[]()*+?") else None,
            "reason": result["reason"],
        }
        if _env_flag("DEBUG_MODERATION_FULL"):
            payload["original"] = original_text
            payload["normalized"] = normalized
        print("[MODERATION]", payload)
    return result


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _run_manual_check() -> None:
    samples = [
        (
            "И есть сейчас люди, которые говорят: человек не становится неверующим, "
            "даже если он произносит слова неверия. Если он поносит Аллаха и Его "
            "Посланника, то он не объявляется неверующим. И это мазхаб крайних "
            "мурджиитов. Мы просим у Аллаха благополучия и сохранности. "
            "Шарх шейха Фаузана.",
            "none",
        ),
        (
            "Прямые ученики Шейх уль-Исляма. 1 - Шейх уль-Ислям Абу Ибрахим. "
            "2 - Имам аль-Муджадид Абу Мухаммад. Да обрадует их Аллах фирдаусом, "
            "мир им и благословения Аллаха.",
            "none",
        ),
        (
            "Время для нового хадиса! Книга: Сунан ат-Тирмизи. Номер хадиса: 3401. "
            "Передают со слов Абу Хурайры, что Посланник Аллаха сказал. "
            "Хвала Аллаху, Который исцелил моё тело.",
            "none",
        ),
        (
            "ВТОРОЙ УЧЕБНЫЙ МОДУЛЬ\nС именем Аллаха, Милостивого, Дарующего "
            "милость. Рады объявить о начале приема заявок на учебный модуль марказа. "
            "Учебная программа делится на модули. Цена за 1 модуль: 1000 руб. "
            "Подпишись на канал марказа.",
            "none",
        ),
        ("Ин Ша Аллах благом будет для тебя", "none"),
        ("И Хвала Аллаху Господу миров!", "none"),
        ("Мы просим у Аллаха благополучия и сохранности", "none"),
        ("человек не становится неверующим", "none"),
        ("слова неверия", "none"),
        ("поносит Аллаха и Его Посланника", "none"),
        ("мазхаб крайних мурджиитов", "none"),
        ("Прямые ученики Шейх уль-Исляма", "none"),
        ("Да обрадует их Аллах фирдаусом", "none"),
        ("Время для нового хадиса", "none"),
        ("Книга: Сунан ат-Тирмизи", "none"),
        ("Передают со слов Абу Хурайры", "none"),
        ("Хвала Аллаху, Который исцелил моё тело", "none"),
        ("ВТОРОЙ УЧЕБНЫЙ МОДУЛЬ", "none"),
        ("С именем Аллаха, Милостивого, Дарующего милость", "none"),
        ("Рады объявить о начале приема заявок", "none"),
        ("Учебная программа", "none"),
        ("Цена за 1 модуль: 1000 руб", "none"),
        ("Подпишись на канал марказа", "none"),
        ("ОЧЕНЬ СЛАБЫЙ хадис", "none"),
        ("данный хадис слабый", "none"),
        ("иснад слабый", "none"),
        ("передатчик слабый", "none"),
        ("этот довод слабый", "none"),
        ("это мнение слабое", "none"),
        ("ты слабый", "personal_insult"),
        ("я тебя убью ин ша Аллах", "threat"),
        ("ТЫ ЧТО НЕ ПОНИМАЕШЬ Я СКАЗАЛ НЕ ПИШИ", "spam_caps"),
        ("Слово идиот нельзя говорить", "none"),
        ("Он сказал слово идиот", "none"),
        ("Она написала слово тупой", "none"),
        ("Не используй слово идиот", "none"),
        ("Что значит идиот?", "none"),
        ("Почему слово идиот оскорбление?", "none"),
        ("Он назвал меня идиотом", "none"),
        ("Меня назвали идиотом", "none"),
        ("Я не называл тебя идиотом", "none"),
        ("Не надо называть людей идиотами", "none"),
        ("Что означает слово кяфир?", "none"),
        ("Слово кяфир означает...", "none"),
        ("Можно ли говорить слово заблудший?", "none"),
        ('Слово "идиот" нельзя писать', "none"),
        ('Он написал "тупой"', "none"),
        ('Что означает "кяфир"?', "none"),
        ('Можно ли говорить "заблудший"?', "none"),
        ('Есть выражение "сам дурак"', "none"),
        ('ты "идиот"', "personal_insult"),
        ('вы "тупые"', "personal_insult"),
        ("Ты не идиот", "none"),
        ("Он не тупой", "none"),
        ("Я не говорил, что ты тупой", "none"),
        ("Не будь идиотом", "insulting_language"),
        ("член команды", "none"),
        ("член семьи", "none"),
        ("член предложения", "none"),
        ("член комиссии", "none"),
        ("член организации", "none"),
        ("член жюри", "none"),
        ("он член нашей группы", "none"),
        ("сосать член", "vulgar_language"),
        ("покажи член", "vulgar_language"),
        ("мой член", "vulgar_language"),
        ("тупой угол", "none"),
        ("тупой нож", "none"),
        ("тупая боль", "none"),
        ("тупой звук", "none"),
        ("тупой предмет", "none"),
        ("тупая сторона ножа", "none"),
        ("тупой", "personal_insult"),
        ("ты тупой", "personal_insult"),
        ("вы тупые", "personal_insult"),
        ("он тупой", "insulting_language"),
        ("этот человек тупой", "insulting_language"),
        ("тряпка лежит на полу", "none"),
        ("тряпка для уборки", "none"),
        ("возьми тряпку", "none"),
        ("протри тряпкой", "none"),
        ("мокрая тряпка", "none"),
        ("тряпка", "personal_insult"),
        ("ты тряпка", "personal_insult"),
        ("он тряпка", "insulting_language"),
        ("анализ мочи", "none"),
        ("моча нужна для анализа", "none"),
        ("кал на анализ", "none"),
        ("сдача кала", "none"),
        ("половой орган в учебнике", "none"),
        ("строение полового органа", "none"),
        ("пенис медицинский термин", "none"),
        ("анатомия полового органа", "none"),
        ("моча", "vulgar_language"),
        ("кал", "vulgar_language"),
        ("половой орган", "vulgar_language"),
        ("пенис", "vulgar_language"),
        ("ребенок сосет палец", "none"),
        ("сосать леденец", "none"),
        ("сосать конфету", "none"),
        ("насос сосет воздух", "none"),
        ("соси", "vulgar_language"),
        ("отсос", "vulgar_language"),
        ("иди соси", "vulgar_language"),
        ("кяфир", "none"),
        ("муртад", "none"),
        ("заблудший", "none"),
        ("такфир", "none"),
        ("ширк", "none"),
        ("куфр", "none"),
        ("ахлю сунна", "none"),
        ("саляфит", "none"),
        ("ашарит", "none"),
        ("хариджит", "none"),
        ("рафидит", "none"),
        ("джахмит", "none"),
        ("ты кяфир", "none"),
        ("ты муртад", "none"),
        ("ты заблудший", "none"),
        ("кяфир идиот", "insulting_language"),
        ("заблудший тупой", "insulting_language"),
        ("ты кяфир идиот", "personal_insult"),
        ("ты заблудший мразь", "personal_insult"),
        ("ты идиот", "personal_insult"),
        ("он идиот", "insulting_language"),
        ("идиот", "personal_insult"),
        ("сам дурак", "personal_insult"),
        ("Писька", "vulgar_language"),
        ("Дрочил", "vulgar_language"),
        ("Говно", "vulgar_language"),
        ("Моча", "vulgar_language"),
        ("Кал", "vulgar_language"),
        ("Калл", "vulgar_language"),
        ("Половой орган", "vulgar_language"),
        ("Нахрен", "profanity"),
        ("я тебя убью идиот", "threat"),
        ("выйди поговорим", "provocation"),
        ("выйди поговорим, идиот", "provocation"),
        ("календарь", "none"),
        ("калькулятор", "none"),
        ("калий", "none"),
        ("каллиграфия", "none"),
        ("локализация", "none"),
        ("накал", "none"),
    ]
    failures: list[str] = []
    for index, (sample, expected_category) in enumerate(samples, start=1):
        result = check_message(sample, user_id=1, chat_id=10_000 + index)
        actual_category = str(result["category"])
        ok = actual_category == expected_category
        if expected_category == "vulgar_language" and "мат" in str(result["reply"]).lower():
            ok = False
            failures.append(f"{sample!r}: vulgar_language reply mentions мат")
        if expected_category != "none" and "аллах" not in str(result["reply"]).lower():
            ok = False
            failures.append(f"{sample!r}: reminder does not mention Аллаха")
        if not ok:
            failures.append(f"{sample!r}: expected {expected_category}, got {actual_category}")
        print(
            {
                "text": sample,
                "expected": expected_category,
                "category": actual_category,
                "violation": result["violation"],
                "ok": ok,
                "reply": result["reply"],
            }
        )
    if failures:
        raise AssertionError("Manual moderation checks failed:\n" + "\n".join(failures))

    for category, replies in REPLIES.items():
        for reply in replies:
            if "аллах" not in reply.lower():
                raise AssertionError(
                    f"Reply for {category!r} does not mention Аллаха: {reply!r}"
                )

    now = int(time())

    def history(*texts: str) -> list[dict[str, Any]]:
        return [
            {
                "message_text": text,
                "normalized_text": normalize_text(text),
                "created_at": now - len(texts) + index,
            }
            for index, text in enumerate(texts, start=1)
        ]

    history_samples = [
        (("а", "м", "о", "н", "и", "е"), "flood"),
        (("Да", "Понял", "Сейчас посмотрю", "Я думаю так", "Может быть"), "none"),
        (("Понял", "Понял", "Понял"), "repeated_message"),
    ]
    for index, (messages, expected_category) in enumerate(history_samples, start=1):
        result = check_message(
            messages[-1],
            user_id=2,
            chat_id=20_000 + index,
            recent_messages=history(*messages),
            settings=RuleSettings(),
        )
        actual_category = str(result["category"])
        ok = actual_category == expected_category
        if expected_category != "none" and "аллах" not in str(result["reply"]).lower():
            ok = False
        if not ok:
            raise AssertionError(
                f"{messages!r}: expected {expected_category}, got {actual_category}"
            )
        print(
            {
                "history": messages,
                "expected": expected_category,
                "category": actual_category,
                "violation": result["violation"],
                "ok": ok,
                "reply": result["reply"],
            }
        )


if __name__ == "__main__":
    _run_manual_check()
