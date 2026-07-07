from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable


_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]{2,}")


@dataclass(frozen=True)
class SearchMatch:
    start: int
    end: int
    line: int
    column: int
    text: str


def find_matches(text: str, query: str, *, case_sensitive: bool = False) -> list[SearchMatch]:
    """Return all simple text matches with 1-based line/column metadata."""
    if not query:
        return []
    haystack = text if case_sensitive else text.lower()
    needle = query if case_sensitive else query.lower()
    matches: list[SearchMatch] = []
    pos = 0
    while True:
        idx = haystack.find(needle, pos)
        if idx < 0:
            break
        line = text.count("\n", 0, idx) + 1
        line_start = text.rfind("\n", 0, idx) + 1
        column = idx - line_start + 1
        matches.append(SearchMatch(idx, idx + len(query), line, column, text[idx:idx + len(query)]))
        pos = idx + max(1, len(query))
    return matches


class SimpleSpellChecker:
    """Tiny optional local spell checker.

    It prefers a local system dictionary, usually /usr/share/dict/words on Linux,
    and falls back to a compact built-in word set so the feature never requires
    network access or paid APIs. It intentionally skips all-uppercase stage cues,
    words with digits, URLs, and very short tokens.
    """

    FALLBACK_WORDS = {
        "about", "after", "again", "all", "allow", "also", "and", "are", "ask", "back",
        "because", "before", "being", "bitcoin", "block", "but", "can", "catch", "change",
        "changes", "check", "click", "code", "computer", "context", "copy", "crypto",
        "data", "details", "digital", "display", "editor", "episode", "every", "example",
        "exit", "file", "first", "for", "from", "going", "have", "header", "here",
        "important", "into", "just", "key", "line", "link", "local", "look", "machine",
        "metadata", "mode", "network", "not", "now", "online", "opening", "output",
        "page", "perspective", "perspectives", "play", "preview", "reader", "read", "return",
        "script", "section", "show", "source", "spoken", "sponsor", "system", "text",
        "that", "the", "their", "them", "there", "this", "through", "today", "token",
        "tool", "url", "use", "user", "verbatim", "we", "what", "when", "where", "with",
        "words", "write", "writing", "you", "your",
    }

    def __init__(self, words: Iterable[str] | None = None):
        self.words = {w.lower() for w in (words or self.FALLBACK_WORDS) if w and len(w) > 1}

    @classmethod
    def from_system(cls) -> "SimpleSpellChecker":
        candidates = [
            Path("/usr/share/dict/words"),
            Path("/usr/dict/words"),
        ]
        for path in candidates:
            if path.exists():
                try:
                    words = []
                    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                        word = raw.strip().lower()
                        if word and word.isascii() and word.replace("'", "").replace("-", "").isalpha():
                            words.append(word)
                    if words:
                        return cls(words)
                except Exception:
                    pass
        return cls()

    def is_known(self, word: str) -> bool:
        clean = word.strip("'\"").lower()
        if len(clean) < 3:
            return True
        if any(ch.isdigit() for ch in clean):
            return True
        if clean.isupper():
            return True
        if clean in self.words:
            return True
        # Accept common possessives/plurals when the root exists.
        for suffix in ("'s", "s", "es", "ed", "ing"):
            if clean.endswith(suffix) and clean[: -len(suffix)] in self.words:
                return True
        return False

    def iter_unknown(self, text: str) -> Iterable[tuple[int, int, str]]:
        if "http://" in text or "https://" in text or text.strip().startswith(("URL:", "key:", "CHAT TOKEN:")):
            return []
        unknown: list[tuple[int, int, str]] = []
        for match in _WORD_RE.finditer(text):
            word = match.group(0)
            if not self.is_known(word):
                unknown.append((match.start(), match.end() - match.start(), word))
        return unknown
