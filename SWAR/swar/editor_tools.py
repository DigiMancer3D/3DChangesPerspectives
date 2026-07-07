from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Snippet:
    label: str
    text: str
    cursor_back: int = 0
    description: str = ""


SNIPPET_GROUPS: dict[str, list[Snippet]] = {
    "Sections": [
        Snippet("DATA", ">> DATA <<", 7, "Two-arrow data object."),
        Snippet("VERBATIM", ">>> VERBATIM TEXT <<<", 15, "Three-arrow verbatim object."),
        Snippet("TITLE", ">>>> SECTION TITLE <<<<", 17, "Four-arrow centered title."),
        Snippet("DESCRIPTOR", ">>>>> DESCRIPTOR <<<<<", 16, "Five-arrow descriptor."),
        Snippet("EXPLAINER", ">>>>>> EXPLAINER <<<<<<", 17, "Six-arrow explainer."),
        Snippet("MAJOR", ">>>>>>>> MAJOR EXPLAINER <<<<<<<<", 24, "Seven-plus-arrow major explainer."),
        Snippet("EXIT", ">>>>>>>>>>>>>>>>>>>>>>>>>>>>>EXIT TO BACKGROUND<<<<<<<<<<<<<<<<<<<<<<<<<<<<<", 0, "Red-arrow transition in reader."),
        Snippet("RETURN", ">>>>>>>>>>>>>RETURN TO SHOW<<<<<<<<<<<<<<<", 0, "Green-arrow transition in reader."),
    ],
    "Sub-Sections": [
        Snippet("Spoken Quote", '"Spoken script text."', 2, "Normal spoken script line."),
        Snippet("Important", '>>!!\n      "Important    hard    to read    text"\n                !!          !!          !!<<', 43, "Important hard-to-read block."),
        Snippet("Important Verbatim", '>>>!!\n      "Important    verbatim    text"\n                !!          !!          !!<<<', 39, "Important verbatim block."),
        Snippet("Cue", ">>> READ / SHOW / CLICK <<<", 18, "Short stage cue."),
        Snippet("Descriptor Cue", ">>>>> DESCRIBE VISUAL <<<<<", 21, "Descriptor sub-section."),
        Snippet("Down Arrow Warning", ">>>> !!! DO NOT RESPOND TO THIS YET !!! <<<<\n                  || || || || || || || || ||\n                  \\/ \\/ \\/ \\/ \\/ \\/ \\/ \\/ \\/", 81, "Warning plus down-arrow art."),
    ],
    "End-Sect": [
        Snippet("Divider", "--------------------------------------", 0, "Plain divider."),
        Snippet("Named Divider", "--- SECTION NAME ---", 13, "Divider with centered text."),
        Snippet("Soft Gap", "\n\n\n", 0, "Large silent spacing gap."),
    ],
    "Source": [
        Snippet("Web Source", '- https://example.com/page\n\n    "What I will say about this source."', 39, "Public link source card."),
        Snippet("Local Source", '- ../local-file.pdf\n\n    "Local source note."', 21, "Local path source card."),
        Snippet("Split Source", '-\nhttps://example.com/page\n\n    "Split source form."', 24, "Dash line plus source line."),
        Snippet("Private Link", '! https://example.invalid/private !', 0, "Masked/private non-outline link."),
    ],
    "Markdown": [
        Snippet("Heading", "## Heading", 7, "Markdown heading."),
        Snippet("Caption", "###### Caption", 7, "Small right-aligned heading/caption."),
        Snippet("Bold", "**bold text**", 6, "Markdown bold."),
        Snippet("Italic", "not italic *but this is italicized* text", 26, "Italic inline text."),
        Snippet("Strong", "***strong text which is bold & italic at the same time!***", 57, "Bold and italic text."),
        Snippet("Underline", "___underlined words___", 3, "Underline between triple-underscore wrappers."),
        Snippet("Blocks", "> Words are here and get a special colored bar before this inside a centered padded box.", 0, "Markdown blockquote."),
        Snippet("Nests", ">> nested blockquote if used alone gets +4 from previous indention level", 0, "Nested markdown blockquote."),
        Snippet("Table", "| Segment | Purpose |\n| --- | --- |\n| Reader | Fancy local preview |\n| Editor | Syntax tools |", 0, "Markdown table."),
        Snippet("Checklist", "- [ ] item one\n- [ ] item two", 0, "Markdown checklist."),
        Snippet("Num-List", "- [#] item one\n- [#] item two", 0, "Number-symbol list."),
        Snippet("$-List", "- [$] item one\n- [€] item two", 0, "Money-symbol list."),
        Snippet("%-List", "- [%15] Topic A\n- [%50] Topic B\n- [%15] Topic C\n- [%10] Topic D", 0, "Percentage list."),
        Snippet("Bulleted", "+ item one\n+ item two", 0, "Plus-symbol bullet list."),
    ],
    "Template": [
        Snippet("3DCP Header", "3D Changes Perspectives:: EPISODE NAME: Details\n\nURL: \nkey: \nCHAT TOKEN: \nMETA DATA: tags=abc,xyz\n", 76, "Full header skeleton."),
        Snippet("Opening Roll", '!!!!!!!!!!!!!!!!!   REPO at ending song     !!!!!!!!!!!!!!!!!\n\n"Opening spoken text."\n\n--------------------------------------\n\n>>>>PLAY SHOW INTRO<<<<\n', 125, "Opening structure."),
        Snippet("Sponsor Block", '>>>> THANK NETWORK PARTNERSHIPS <<<<\n\n    >>>"Sponsor / partnership spoken text."<<<\n\n>>>> THANK SPONSOR <<<<\n\n    >>>"Sponsor spoken text."<<<\n', 111, "Sponsor layout."),
        Snippet("Exit/Return Segment", '>>>>>>>>>>>>>>>>>>>>>>>>>>>>>EXIT TO BACKGROUND<<<<<<<<<<<<<<<<<<<<<<<<<<<<<\n\n>>> CATCH UP DEETS <<<\n\n"Catch-up spoken text."\n\n>>>>>>>>>>>>>RETURN TO SHOW<<<<<<<<<<<<<<<\n', 102, "Exit and return structure."),
        Snippet("Full Mini Script", '3D Changes Perspectives:: New Episode: Draft\n\nURL: \nkey: \nCHAT TOKEN: \nMETA DATA: tags=abc,xyz\n\n!!!!!!!!!!!!!!!!!   REPO at ending song     !!!!!!!!!!!!!!!!!\n\n"Opening spoken text."\n\n--------------------------------------\n\n>>>>PLAY SHOW INTRO<<<<\n\n- https://example.com/page\n\n    "Source spoken text."\n\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>EXIT TO BACKGROUND<<<<<<<<<<<<<<<<<<<<<<<<<<<<<\n\n>>> CATCH UP DEETS <<<\n\n"Catch-up spoken text."\n\n>>>>>>>>>>>>>RETURN TO SHOW<<<<<<<<<<<<<<<\n', 0, "Complete starter script."),
    ],
}


def all_group_names() -> list[str]:
    return list(SNIPPET_GROUPS.keys())


def get_snippet(group: str, label: str) -> Snippet:
    for snippet in SNIPPET_GROUPS[group]:
        if snippet.label == label:
            return snippet
    raise KeyError(f"Unknown snippet {group!r}/{label!r}")
