# SWAR User Guide

## Modes

- **Reader**: local-only reading preview. Editor dropdown tools are disabled.
- **Editor**: edit the script text directly.
- **Split**: editor on the left, reader preview on the right.

Reader mode intentionally does not open web links. Public source links copy to clipboard when clicked.

## Toolbar groups

- Left: program actions — Open, +TAB, Reload, Refresh, Save, Outline.
- Center: editor tools — Sections, Sub-Sect, End-Sect, Source, Emoji, MD, Template.
- Right: important settings — Theme, Mode, Network.

Editor tool dropdowns only work in Editor or Split mode.

## Save dropdown

- **SAVE NOW**: save the current tab to its current path when possible.
- **SAVE AS**: choose a new path/format.
- **SAVE SCRIPT**: save as `.script`.
- **SAVE MARKED**: save as `.md`.
- **SAVE TEXT**: save as `.txt`.

## Outline export

The Outline button exports a simple `.txt` file containing:

1. The first header line.
2. Public source links, one per line.

Local paths, `rtmp://` URLs, stream keys, chat tokens, and private bang links are excluded.

Shownote-style endings are replaced with `outline`, for example:

```text
Episode - shownotes.txt -> Episode - outline.txt
Episode_shownotes.script -> Episode_outline.txt
Episode-note.md -> Episode-outline.txt
```

## Emoji file

SWAR loads `current.emoji` from these locations, first match wins:

1. Active/open file folder.
2. Current working folder.
3. SWAR application folder.
4. Parent of SWAR application folder.
5. `~/SWAR/current.emoji`.

Pipe format:

```text
✅|Check|Status /,
```

JSON list format is also accepted:

```json
[
  {"emoji": "✅", "name": "Check", "category": "Status", "tags": ["done", "pass"]}
]
```

## UData persistence

`SWAR.udata` stores theme, window, snippet, and runtime preferences in an ABI-style variable file. Unknown variables are skipped safely.

Custom snippets use one-line values with `\n` for line breaks:

```text
snippet.Template.My Roll:>>>> MY CUSTOM ROLL <<<<.
snippet_desc.Template.My Roll:Custom roll cue.
snippet_cursor_back.Template.My Roll:8.
```


## Find/Search and local spellcheck

Use `Tools -> Find / Search` or `Ctrl+F` to open the local search panel. Search works on the active tab and shows match counts. Use `Next` and `Prev` to move through matches.

Use `Tools -> Spell Check` to toggle local spellcheck. SWAR uses a local system dictionary if one exists and falls back to a small built-in word list. Spellcheck stays local and is optional.


## Phase 5-R2 Corrective Note

This package fixes a Phase 5 GUI-load regression where opened files could appear blank after the local search/spellcheck tools were added. The fix suppresses setup-only Qt text-change signals and prevents syntax-highlighter refreshes from marking opened tabs dirty. The release verifier also now tolerates a local `venv/` created by `install_kubuntu.sh` during normal local testing.
