from __future__ import annotations

from dataclasses import dataclass, field
import re

from .editor_tools import Snippet


ARC_FIELD_COUNT = 7
ARC_TIME_RE = re.compile(r"^\d{1,4}:\d{1,4}:\d{1,4}$")
ZONE_TYPES = ("Safe", "Crawl", "Fight", "Mix0", "Mix1", "Mix2", "Mix3", "Mixed")
ESTIMATED_TYPES = ("E2F", "E2S", "SHT", "LHT")
DATA_PHRASES = (
    "exit", "enter", "kill", "death", "squash", "XYZ", "pick", "acts", "touch",
    "user", "jim", "sarah", "bob", "obj", "weap", "armed", "arm", "speed",
    "faster", "slower", "slow", "glue", "hot", "cold", "froze", "flame", "drop",
    "xplode", "burp", "burpee", "slothee", "plop", "wrap", "parw", "par",
)
DATA_PHRASE_LOOKUP = {item.lower(): item for item in DATA_PHRASES}

# Story wrappers are deliberately forgiving and are only applied to the sixth
# field of an .arcs record.  Named screenplay speech is also accepted in the
# visible forms ``NAME: "speech"`` and ``"speech" :NAME``.
_SPEAKER_NAME = r"[A-Za-z][A-Za-z0-9 _.'-]{0,39}"
STORY_WRAPPER_RE = re.compile(
    rf'(?P<named_left>(?P<named_left_name>{_SPEAKER_NAME})\s*:\s*"(?P<named_left_text>[^"\n]+)")'
    rf'|(?P<named_right>"(?P<named_right_text>[^"\n]+)"\s*:\s*(?P<named_right_name>{_SPEAKER_NAME}))'
    r'|(?P<user_speech>\\(?P<user_text>[^\\\n]+)\\)'
    r'|(?P<thought>/(?P<thought_text>[^/\n]+)/)'
    r'|(?P<noticed>_(?P<noticed_text>[^_\n]+)_)'
    r'|(?P<npc>(?<![<])-(?!>)(?P<npc_text>[^-\n]+)-)'
)
POINTER_RE = re.compile(r"^\s*->\s*(?:'(?P<quoted>[^']+)'|(?P<phrase>[A-Za-z][A-Za-z0-9_-]*))")
DIRECTIVE_RE = re.compile(r"^(?P<left>.+?)\s*(?P<arrow><<|>>|<-|->)\s*(?P<right>.+)$")
ARC_DATA_TOKEN_RE = re.compile(
    r"(?P<bind_action>\[[^]\n]+\])"
    r"|(?P<bind_event>\{[^}\n]+\})"
    r"|(?P<bind_entity>\([^()\n]*\([^()\n]+\)[^()\n]*\))"
    r"|(?P<interactable>\^[^^\n]+\^)"
    r"|(?P<mandatory>\*[^*\n]+\*)"
    r"|(?P<location>@\{[^}\n]+\})"
    r"|(?P<drop>~[^~\n]+~)"
    r"|(?P<rate>(?:drop%|\+spawn_rates)\s*\d+(?:\.\d+)?)"
    r"|(?P<entity>'[^'\n]+')"
)


@dataclass
class ArcRecord:
    name: str = "New Arc"
    estimated: str = "0:0:0"
    zone_type: str = "Safe"
    start_message: str = "Starting Text"
    map_ref: str = "$imported map#"
    arc_data: str = ""
    confirm_message: str = "Completion Text"
    line_number: int = 1
    raw: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_line(self) -> str:
        start = self.start_message.strip()
        confirm = self.confirm_message.strip()
        if not (start.startswith("***") and start.endswith("***")):
            start = f"***{start.strip('*')}***"
        if not (confirm.startswith("***") and confirm.endswith("***")):
            confirm = f"***{confirm.strip('*')}***"
        return "||".join((
            self.name.strip(),
            self.estimated.strip(),
            self.zone_type.strip(),
            start,
            self.map_ref.strip(),
            self.arc_data.strip(),
            confirm,
        ))

    @property
    def start_text(self) -> str:
        return _strip_stars(self.start_message)

    @property
    def confirm_text(self) -> str:
        return _strip_stars(self.confirm_message)


def _strip_stars(value: str) -> str:
    text = (value or "").strip()
    if text.startswith("***") and text.endswith("***") and len(text) >= 6:
        return text[3:-3].strip()
    return text.strip("*").strip()


def _split_arc_line(line: str) -> list[str]:
    parts = line.split("||")
    if len(parts) <= ARC_FIELD_COUNT:
        return parts
    # ARC DATA is the only field that reasonably contains free-form relay text.
    # Preserve first five and final confirmation, then join the middle back.
    return parts[:5] + ["||".join(parts[5:-1])] + [parts[-1]]


def parse_arc_line(line: str, line_number: int = 1) -> ArcRecord:
    raw = line.rstrip("\n")
    parts = [part.strip() for part in _split_arc_line(raw)]
    while len(parts) < ARC_FIELD_COUNT:
        parts.append("")
    record = ArcRecord(
        name=parts[0] or "Untitled Arc",
        estimated=parts[1] or "0:0:0",
        zone_type=parts[2] or "Safe",
        start_message=parts[3] or "***Starting Text***",
        map_ref=parts[4] or "$imported map#",
        arc_data=parts[5],
        confirm_message=parts[6] or "***Completion Text***",
        line_number=line_number,
        raw=raw,
    )
    if len(_split_arc_line(raw)) != ARC_FIELD_COUNT:
        record.warnings.append(f"Line {line_number}: expected 7 || fields.")
    if len(record.name) > 18:
        record.warnings.append(f"Line {line_number}: arc name is longer than 18 characters.")
    if not ARC_TIME_RE.match(record.estimated):
        record.warnings.append(f"Line {line_number}: estimated value should use M:S:m numeric form.")
    if record.zone_type not in ZONE_TYPES:
        record.warnings.append(f"Line {line_number}: unknown zone type {record.zone_type!r}.")
    if not (record.map_ref.startswith("$") or record.map_ref.startswith("#")):
        record.warnings.append(f"Line {line_number}: map field normally starts with $ or #.")
    if len(record.start_text) > 150:
        record.warnings.append(f"Line {line_number}: start message is longer than 150 characters.")
    if len(record.confirm_text) > 150:
        record.warnings.append(f"Line {line_number}: confirmation message is longer than 150 characters.")
    return record


def parse_arcs_text(text: str) -> tuple[list[ArcRecord], list[str]]:
    records: list[ArcRecord] = []
    warnings: list[str] = []
    for line_number, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        record = parse_arc_line(raw, line_number)
        records.append(record)
        warnings.extend(record.warnings)
    if not records and text.strip():
        warnings.append("No valid non-comment .arcs record lines were found.")
    return records, warnings


def _story_element(kind: str, text: str, **attrs: str) -> dict[str, str]:
    item = {"kind": kind, "text": (text or "").strip()}
    item.update({key: value for key, value in attrs.items() if value is not None})
    return item


SCRIPT_MARKUP_LINE_RE = re.compile(
    r'^\s*(?:>{2,}|#{1,6}\s+|`{3,}|".*"\s*$|---|\*{3,}\s*$|'
    r'->\s+|#{6,}\s|!!(?:\s|$)|(?:!!\s*)+<?<?\s*$)',
    re.MULTILINE,
)


def _looks_like_story_markup(value: str) -> bool:
    text = (value or "").strip()
    if not text:
        return False
    if SCRIPT_MARKUP_LINE_RE.search(text):
        return True
    # Color-profiled and fenced objects can begin with otherwise ordinary text.
    return bool(re.search(r'(?:\[#[0-9A-Fa-f]{3,8}\]|\((?:rgba?)\([^()\n]*\)\))\s*$', text))


def _classify_story_unit(out: list[dict[str, str]], unit: str) -> None:
    unit = unit.strip(" \t,")
    if not unit:
        return

    directive = DIRECTIVE_RE.match(unit)
    if directive and directive.group("left").strip() and directive.group("right").strip():
        out.append(_story_element(
            "directive",
            unit,
            left=directive.group("left").strip(),
            right=directive.group("right").strip(),
            arrow=directive.group("arrow"),
        ))
        return

    cursor = 0
    matched_data = False
    for match in ARC_DATA_TOKEN_RE.finditer(unit):
        before = unit[cursor:match.start()].strip(" \t,")
        if before:
            _classify_story_unit(out, before)
        token = match.group(0).strip()
        group = match.lastgroup or "data"
        if group == "interactable":
            out.append(_story_element("option", token.strip("^"), option_type="interactable", raw=token))
        elif group == "mandatory":
            out.append(_story_element("option", token.strip("*"), option_type="mandatory", raw=token))
        else:
            category_map = {
                "bind_action": ("Binding", "Bind to action"),
                "bind_event": ("Binding", "Bind to event"),
                "bind_entity": ("Binding", "Bind to entity"),
                "location": ("Location", "Location selector"),
                "drop": ("Object", "Expected drop"),
                "rate": ("Rate", "Spawn / drop rate"),
                "entity": ("Entity", "Entity / character"),
            }
            category, label = category_map.get(group, ("Arc Data", group.replace("_", " ").title()))
            display_token = token
            if group == "drop":
                display_token = token.strip("~").strip()
            elif group == "entity":
                display_token = token.strip("'").strip()
            out.append(_story_element("data", display_token, category=category, label=label, raw=token))
        cursor = match.end()
        matched_data = True
    tail = unit[cursor:].strip(" \t,")
    if tail:
        words = [word for word in re.split(r"\s+", tail) if word]
        normalized = [DATA_PHRASE_LOOKUP.get(word.lower()) for word in words]
        if words and all(item is not None for item in normalized):
            out.append(_story_element(
                "data",
                " ".join(str(item) for item in normalized),
                category="Relay",
                label="Data phrase" if len(words) == 1 else "Data phrases",
            ))
        elif not matched_data or tail:
            out.append(_story_element("plot", tail))


def _append_plain_story_piece(out: list[dict[str, str]], raw: str) -> None:
    """Classify non-wrapper Arc Data while preserving source order.

    Literal ``\\n`` creates real story lines.  A segment containing normal SWAR
    block marks is retained as a Script Markup element and rendered through the
    same parser as a .script file.
    """
    decoded = (raw or "").replace("\\n", "\n")
    for segment in re.split(r";", decoded):
        segment = segment.strip(" \t,")
        if not segment:
            continue
        if _looks_like_story_markup(segment):
            out.append(_story_element("markup", segment))
            continue
        for unit in segment.splitlines():
            _classify_story_unit(out, unit)


def _split_speaker_text(value: str, default_speaker: str) -> tuple[str, str]:
    text = (value or "").strip()
    match = re.match(rf"^\s*(?P<name>{_SPEAKER_NAME})\s*:\s*(?P<speech>.+)$", text)
    if match:
        return match.group("name").strip(), match.group("speech").strip()
    return default_speaker, text


def parse_story_arc_data(value: str) -> list[dict[str, str]]:
    """Turn Arc Data into screenplay-friendly semantic elements.

    The source remains canonical.  Named speakers, normal .script markup,
    directives, choices, and engine data are all display-only interpretations.
    """
    text = (value or "").replace("\\n", "\n")
    out: list[dict[str, str]] = []
    cursor = 0
    for match in STORY_WRAPPER_RE.finditer(text):
        _append_plain_story_piece(out, text[cursor:match.start()])
        target = ""
        pointer_match = POINTER_RE.match(text[match.end():])
        consumed_to = match.end()
        if pointer_match:
            target = (pointer_match.group("quoted") or pointer_match.group("phrase") or "").strip()
            consumed_to += pointer_match.end()

        if match.group("named_left") is not None:
            out.append(_story_element(
                "talk", match.group("named_left_text") or "",
                side="left", side_hint="left", speaker=(match.group("named_left_name") or "TALKER").strip(),
                target=target, talk_type="speech",
            ))
        elif match.group("named_right") is not None:
            out.append(_story_element(
                "talk", match.group("named_right_text") or "",
                side="right", side_hint="right", speaker=(match.group("named_right_name") or "TALKER").strip(),
                target=target, talk_type="speech",
            ))
        elif match.group("user_speech") is not None:
            speaker, speech = _split_speaker_text(match.group("user_text") or "", "USER")
            out.append(_story_element(
                "talk", speech, side="left", side_hint="left", speaker=speaker,
                target=target, talk_type="speech",
            ))
        elif match.group("npc") is not None:
            speaker, speech = _split_speaker_text(match.group("npc_text") or "", "NPC")
            out.append(_story_element(
                "talk", speech, side="right", side_hint="right", speaker=speaker,
                target=target, talk_type="speech",
            ))
        elif match.group("thought") is not None:
            speaker, speech = _split_speaker_text(match.group("thought_text") or "", "USER THOUGHT")
            out.append(_story_element(
                "talk", speech, side="left", side_hint="left", speaker=speaker,
                target=target, talk_type="thought",
            ))
        else:
            out.append(_story_element("notice", match.group("noticed_text") or "", target=target))
        cursor = consumed_to
    _append_plain_story_piece(out, text[cursor:])
    return out

def new_arc_template() -> str:
    return ArcRecord().to_line()


ARC_SNIPPET_GROUPS: dict[str, list[Snippet]] = {
    "Arc": [
        Snippet("New Arc", new_arc_template(), 0, "Complete seven-field .arcs record."),
        Snippet("Start Text", "***Starting Text***", 3, "Arc opening lore wrapper."),
        Snippet("Completion Text", "***Completion Text***", 3, "Arc completion wrapper."),
        Snippet("Import Map", "$imported map#", 1, "Reference an imported map."),
        Snippet("Generate Map", "$generate map!", 1, "Generate a map on demand."),
    ],
    "Story": [
        Snippet("Named Talker", 'ALICE: "Speech text"', 12, "Named speaker; new speakers rotate left, right, then center."),
        Snippet("Named Talker Right", '"Speech text" :BOB', 17, "Named right-hinted speaker form."),
        Snippet("Thought", "/User's Thoughts/", 1, "Left-side active-character thought box."),
        Snippet("User Speech", "\\User's Speech\\", 1, "Left-side active-character talk box."),
        Snippet("Noticed", "_Noticed actions_", 1, "Centered screenplay notice / plot action."),
        Snippet("NPC Speech", "-NPC Speech-", 1, "Right-side NPC talk box."),
        Snippet("Character Pointer", "->'CHARACTER_NAME'", 1, "Address a named character after speech/thought/action."),
        Snippet("Phrase Pointer", "->data_phrase", 0, "Address an Arc Data phrase."),
    ],
    "Arc Data": [
        Snippet("Bind Action", "[event/entity/object {action}]", 1, "Bind special behavior to an action."),
        Snippet("Bind Event", "{action/entity/object [event]}", 1, "Bind special behavior to an event."),
        Snippet("Bind Entity", "(event/action/object (entity))", 1, "Bind special behavior to an entity."),
        Snippet("Interactable", "^interactable event^", 1, "Reader choice / allowed interactable event."),
        Snippet("Mandatory", "*mandatory event*", 1, "Required story event."),
        Snippet("Location", "@{LOCATION}", 1, "Map coordinate/location selector."),
        Snippet("Dynamic Location", "@{__RANDOM__}", 2, "Dynamic location selector."),
        Snippet("Symbol Location", '@{"X"}', 2, "Resolve a location by map symbol."),
        Snippet("Instant Forward", "ACTION -> RESULT", 6, "Twin-box forward action/result directive."),
        Snippet("Instant Back", "RESULT <- ACTION", 6, "Twin-box backward action/result directive."),
        Snippet("Lingering Back", "RESULT << ACTION", 6, "Twin-box lingering backward effect."),
        Snippet("Lingering Forward", "ACTION >> RESULT", 6, "Twin-box lingering forward effect."),
    ],
    "Phrases": [Snippet(phrase, phrase, 0, f"Insert the {phrase!r} data phrase.") for phrase in DATA_PHRASES],
}
