from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from time import time
from typing import Any

try:
    from .replies import get_reply
except ImportError:
    from replies import get_reply


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


# Редактируемые локальные списки. Vulgar/word-specific проверяются до profanity, чтобы не писать 'без мата' на не-мат.
WORD_SPECIFIC_REPLIES = {
    "половой орган": {
        "category": "vulgar_language",
        "reply": "Брат, давай без неприличных выражений. Сохраним чистоту речи.",
    },
    "моча": {
        "category": "vulgar_language",
        "reply": "Давайте не засорять чат такими словами. Пусть речь будет приличной.",
    },
    "кал": {
        "category": "vulgar_language",
        "reply": "Брат, лучше избегать грязных слов в общем чате.",
    },
    "калл": {
        "category": "vulgar_language",
        "reply": "Брат, лучше избегать грязных слов в общем чате.",
    },
    "говно": {
        "category": "vulgar_language",
        "reply": "Брат, давай без грубых и грязных слов. Сохраним адаб.",
    },
    "писька": {
        "category": "vulgar_language",
        "reply": "Брат, давай без неприличных слов. Сохраним чистоту речи.",
    },
    "писка": {
        "category": "vulgar_language",
        "reply": "Брат, давай без неприличных слов. Сохраним чистоту речи.",
    },
    "дрочил": {
        "category": "vulgar_language",
        "reply": "Брат, давай без неприличных слов. Сохраним чистоту речи.",
    },
    "дрочить": {
        "category": "vulgar_language",
        "reply": "Брат, давай без неприличных слов. Сохраним чистоту речи.",
    },
    "дрочка": {
        "category": "vulgar_language",
        "reply": "Брат, давай без неприличных слов. Сохраним чистоту речи.",
    },
    "член": {
        "category": "vulgar_language",
        "reply": "Брат, давай без неприличных выражений. Сохраним чистоту речи.",
    },
    "пенис": {
        "category": "vulgar_language",
        "reply": "Брат, давай без неприличных выражений. Сохраним чистоту речи.",
    },
    "жопа": {
        "category": "vulgar_language",
        "reply": "Брат, лучше избегать грубых слов в общем чате.",
    },
    "задница": {
        "category": "vulgar_language",
        "reply": "Брат, лучше избегать грубых слов в общем чате.",
    },
    "тряпка": {
        "category": "personal_insult",
        "reply": "Брат, давай без унизительных слов в адрес людей. Сохраним уважение.",
    },
}

PROFANITY_PATTERNS = [
    r"н\s*а\s*х\s*у\s*[ийеюя][а-я]*",
    r"п\s*о\s*х\s*у\s*[ийеюя][а-я]*",
    r"х\s*у\s*[ийеюя][а-я]*",
    r"х\s*е\s*р[а-я]*",
    r"п\s*и\s*з\s*д[а-я]*",
    r"п\s*з\s*д\s*ц",
    r"б\s*л\s*[яа](?:т[ьб]?|д[ьб]?|[а-я]*)",
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
    r"кал[а-я]*",
    r"моч[а-я]*",
    r"пенис[а-я]*",
    r"пис[ь]?к[а-я]*",
    r"полов[а-я]*\s+орган[а-я]*",
    r"дроч[а-я]*",
    r"минет[а-я]*",
    r"отсос[а-я]*",
    r"сосать",
    r"сос[ие][а-я]*",
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
    r"разберусь\s+с\s+(?:тобой|вами|ним|ней)",
]

MOCKERY_PATTERNS = [
    r"(?:ты|вы|он|она|они)\s+(?:жалк[а-я]*|посмешище|смешон|смешна|смешны)",
    r"(?:смеюсь|угараю)\s+(?:с\s+тебя|над\s+тобой|над\s+вами)",
]

PROVOCATION_PATTERNS = [
    r"слабо\s+(?:сказать|повторить)\s+(?:в\s+лицо|при\s+встрече)",
    r"выйди\s+(?:поговорим|разберемся)",
    r"давай\s+встретимся\s+и\s+разберемся",
]


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
EXTRA_INSULT_RE = _compile_optional_word_pattern(
    INSULT_PATTERNS
    + [_word_or_phrase_pattern(word) for word in ADAB_BAD_WORDS["insult_words"]]
)
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
    rf"{WORD_LEFT}не\s+(?:{'|'.join(f'(?:{pattern})' for pattern in INSULT_PATTERNS)}){WORD_RIGHT}",
    re.IGNORECASE,
)
PERSONAL_INSULT_RE = re.compile(
    rf"{WORD_LEFT}(?:ты|вы|он|она|они|этот|эта|эти)"
    rf"(?:\s+[а-яa-z0-9_]+){{0,4}}\s+"
    rf"(?:{'|'.join(f'(?:{pattern})' for pattern in INSULT_PATTERNS)}){WORD_RIGHT}",
    re.IGNORECASE,
)


def check_word_specific(normalized: str) -> dict[str, Any] | None:
    for word, data in WORD_SPECIFIC_REPLIES.items():
        pattern = _word_or_phrase_pattern(word, suffix=False)
        if pattern and re.search(f"{WORD_LEFT}(?:{pattern}){WORD_RIGHT}", normalized, re.IGNORECASE):
            if word == "тряпка" and not _is_personal_context(normalized):
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

    # Если vulgar-паттерн уже нашёл слово, это не мат, а category="vulgar_language".
    for pattern, regex in VULGAR_RES:
        if regex.search(normalized):
            return None
    for pattern, regex in EXTRA_VULGAR_RES:
        if regex.search(normalized):
            return None
    for pattern, regex in EXTRA_VULGAR_RAW_RES:
        if regex.search(normalized):
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
        if regex.search(normalized):
            return pattern
    for pattern, regex in EXTRA_VULGAR_RES:
        if regex.search(normalized):
            return f"{ADAB_BAD_WORDS_FILE.name}:{pattern}"
    for pattern, regex in EXTRA_VULGAR_RAW_RES:
        if regex.search(normalized):
            return f"{ADAB_BAD_WORDS_FILE.name}:{pattern}"

    for word in re.findall(r"[а-яa-z]+", normalized):
        if word in EXTRA_PROFANITY_WORDS and _is_vulgar_word(word):
            return f"words.txt:{word}"

    return None


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
        return _debug_result(result, matched, original_text, normalized)

    logger.debug("Moderation input: original=%r normalized=%r", original_text, normalized)
    if not normalized:
        return finish(_no_violation(), None)

    # 1) Точечные слова/фразы проверяем первыми.
    # Это нужно, чтобы "писька", "дрочил", "говно", "моча", "кал" не уходили в profanity.
    specific_result = check_word_specific(normalized)
    if specific_result is not None:
        result = _specific_violation(specific_result, user_id, chat_id)
        return finish(result, str(specific_result["word"]))

    # 2) Личные оскорбления отдельно.
    if _has_personal_insult(normalized):
        return finish(
            _violation(
                "personal_insult",
                "найдено прямое личное оскорбление",
                user_id,
                chat_id,
            ),
            None,
        )

    # 3) Неприличные/грязные слова, но не мат.
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

    # 4) Настоящий мат.
    profanity_pattern = check_profanity(normalized)
    if profanity_pattern:
        logger.debug("Moderation profanity pattern: %s", profanity_pattern)
        return finish(_profanity_violation(user_id, chat_id), profanity_pattern)

    if THREAT_RE.search(normalized):
        return finish(_violation("threat", "найдена прямая угроза", user_id, chat_id), None)

    rule_settings = _settings_from_config(settings)
    if _is_caps_aggression(original_text, rule_settings):
        return finish(
            _violation(
                "spam_caps",
                "слишком много букв в верхнем регистре",
                user_id,
                chat_id,
            ),
            None,
        )

    history_result = _check_history(recent_messages or [], rule_settings, user_id, chat_id)
    if history_result:
        return finish(history_result, None)

    if MOCKERY_RE.search(normalized):
        return finish(
            _violation("mockery", "найдена грубая насмешка", user_id, chat_id),
            None,
        )

    if PROVOCATION_RE.search(normalized):
        return finish(
            _violation("provocation", "найдена агрессивная провокация", user_id, chat_id),
            None,
        )

    return finish(_no_violation(), None)


def _has_personal_insult(normalized: str) -> bool:
    checked_text = NEGATED_INSULT_RE.sub(" ", normalized)
    if _word_or_phrase_matches("тряпка", checked_text):
        return _is_personal_context(checked_text)
    if PERSONAL_INSULT_RE.search(checked_text) or RUDE_COMMAND_RE.search(checked_text):
        return True
    if EXTRA_INSULT_RE is not None:
        words = re.findall(r"[а-яa-z0-9_]+", checked_text)
        if len(words) <= 4 and EXTRA_INSULT_RE.search(checked_text):
            return True
        if re.search(rf"{WORD_LEFT}(?:ты|вы|он|она|они|этот|эта|эти){WORD_RIGHT}", checked_text):
            if EXTRA_INSULT_RE.search(checked_text):
                return True
    if any(regex.search(checked_text) for _, regex in EXTRA_INSULT_RAW_RES):
        return True

    # Одно короткое сообщение вроде "Идиот!" обычно является прямым обращением.
    words = re.findall(r"[а-яa-z0-9_]+", checked_text)
    return len(words) <= 4 and EXTRA_INSULT_RE is not None and EXTRA_INSULT_RE.search(checked_text) is not None


def _is_personal_context(normalized: str) -> bool:
    return re.search(
        rf"{WORD_LEFT}(?:ты|вы|он|она|они|этот|эта|эти|твой|твоя|твои){WORD_RIGHT}",
        normalized,
    ) is not None


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


def _is_caps_aggression(text: str, settings: RuleSettings) -> bool:
    stripped = text.strip()
    if len(stripped) <= settings.caps_min_length:
        return False

    letters = [char for char in stripped if char.isalpha()]
    if len(letters) < 8:
        return False

    uppercase = sum(1 for char in letters if char.isupper())
    return uppercase / len(letters) >= settings.caps_ratio


def _check_history(
    recent_messages: list[dict[str, Any]],
    settings: RuleSettings,
    user_id: int,
    chat_id: int,
) -> dict[str, Any] | None:
    if not recent_messages:
        return None

    now = int(max(message.get("created_at", int(time())) for message in recent_messages))
    window_start = now - settings.flood_time_window_seconds
    in_window = [
        message for message in recent_messages if int(message.get("created_at", 0)) >= window_start
    ]
    if len(in_window) >= settings.flood_messages_limit:
        return _violation("flood", "слишком много сообщений за короткое время", user_id, chat_id)

    normalized_messages = [
        str(message.get("normalized_text") or normalize_text(message.get("message_text", "")))
        for message in recent_messages
        if str(message.get("normalized_text") or normalize_text(message.get("message_text", "")))
    ]
    if len(normalized_messages) >= 3 and len(set(normalized_messages[-3:])) == 1:
        return _violation(
            "repeated_message",
            "три одинаковых сообщения подряд",
            user_id,
            chat_id,
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
    print(
        "[MODERATION]",
        {
            "original": original_text,
            "normalized": normalized,
            "matched_word": matched if matched and not any(char in matched for char in r"\[]()*+?") else None,
            "matched_pattern": matched if matched and any(char in matched for char in r"\[]()*+?") else None,
            "category": result["category"],
            "reply": result["reply"],
        },
    )
    return result


def _run_manual_check() -> None:
    samples = [
        "Писька",
        "Дрочил",
        "Половой орган",
        "Моча",
        "Говно",
        "Калл",
        "Тупой",
        "Идиот",
    ]
    for index, sample in enumerate(samples, start=1):
        result = check_message(sample, user_id=1, chat_id=10_000 + index)
        print(
            {
                "text": sample,
                "category": result["category"],
                "violation": result["violation"],
                "reply": result["reply"],
            }
        )


if __name__ == "__main__":
    _run_manual_check()
