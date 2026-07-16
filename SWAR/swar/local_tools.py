from __future__ import annotations

from dataclasses import dataclass
from difflib import get_close_matches
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
    """Small, local-only spell checker with right-click suggestions.

    A system dictionary is preferred. The fallback keeps spell checking usable
    without a network service, background worker, or extra dependency.
    """

    FALLBACK_WORDS = {
        "about", "after", "again", "all", "allow", "also", "and", "are", "ask", "back",
        "because", "before", "being", "bitcoin", "block", "but", "can", "catch", "change",
        "changes", "check", "click", "code", "computer", "context", "copy", "correct",
        "crypto", "data", "details", "digital", "display", "editor", "episode", "every",
        "example", "exit", "file", "first", "for", "from", "going", "have", "header",
        "help", "here", "important", "into", "just", "key", "line", "link", "linked",
        "local", "look", "machine", "markdown", "metadata", "mode", "network", "not", "now",
        "online", "opening", "output", "page", "pause", "perspective", "perspectives", "play",
        "preview", "reader", "read", "reload", "restore", "return", "save", "script", "scroll",
        "section", "show", "source", "speed", "spell", "spoken", "sponsor", "story", "system",
        "teleprompter", "text", "that", "the", "their", "them", "there", "this", "through",
        "today", "token", "tool", "url", "use", "user", "verbatim", "we", "what", "when",
        "where", "with", "words", "write", "writing", "you", "your",
    }

    def __init__(self, words: Iterable[str] | None = None):
        self.words = {w.lower() for w in (words or self.FALLBACK_WORDS) if w and len(w) > 1}
        self._sorted_words = sorted(self.words)
        self._by_initial: dict[str, list[str]] = {}
        for item in self._sorted_words:
            self._by_initial.setdefault(item[:1], []).append(item)

    @classmethod
    def from_system(cls) -> "SimpleSpellChecker":
        candidates = [Path("/usr/share/dict/words"), Path("/usr/dict/words")]
        for path in candidates:
            if not path.exists():
                continue
            try:
                words: list[str] = []
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
        raw = word.strip("'\"")
        clean = raw.lower()
        if len(clean) < 3:
            return True
        if any(ch.isdigit() for ch in clean):
            return True
        if raw.isupper():
            return True
        if clean in self.words:
            return True
        for suffix in ("'s", "s", "es", "ed", "ing"):
            if clean.endswith(suffix) and clean[: -len(suffix)] in self.words:
                return True
        return False

    def suggestions(self, word: str, *, limit: int = 7) -> list[str]:
        """Return stable, local close matches while preserving typed case."""
        raw = word.strip("'\"")
        clean = raw.lower()
        if not clean or self.is_known(raw):
            return []
        cutoff = 0.72 if len(clean) <= 5 else 0.67
        initial_pool = self._by_initial.get(clean[:1], self._sorted_words)
        candidates = [item for item in initial_pool if abs(len(item) - len(clean)) <= 4]
        if not candidates:
            candidates = initial_pool
        matches = get_close_matches(clean, candidates, n=max(1, limit), cutoff=cutoff)
        out: list[str] = []
        for match in matches:
            if raw.isupper():
                candidate = match.upper()
            elif raw[:1].isupper():
                candidate = match.capitalize()
            else:
                candidate = match
            if candidate not in out:
                out.append(candidate)
        return out[:limit]

    def iter_unknown(self, text: str) -> Iterable[tuple[int, int, str]]:
        if "http://" in text or "https://" in text or text.strip().startswith(("URL:", "key:", "CHAT TOKEN:")):
            return []
        unknown: list[tuple[int, int, str]] = []
        for match in _WORD_RE.finditer(text):
            word = match.group(0)
            if not self.is_known(word):
                unknown.append((match.start(), match.end() - match.start(), word))
        return unknown


def word_bounds_at(text: str, position: int) -> tuple[int, int, str] | None:
    """Return the alphabetic word touching *position* in plain text."""
    position = max(0, min(len(text), int(position)))
    for match in _WORD_RE.finditer(text):
        if match.start() <= position <= match.end():
            return match.start(), match.end(), match.group(0)
    return None
