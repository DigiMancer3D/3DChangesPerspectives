#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from swar.parser import Block, ScriptDoc, SwarParser
from swar.renderer_html import render_doc_html

failures: list[str] = []


def check(ok: bool, label: str) -> None:
    print(("PASS" if ok else "FAIL") + ": " + label)
    if not ok:
        failures.append(label)


sample = r'''SWAR Extended Markdown:: v0.7.0-rc1-r4 Acceptance Example
URL: rtmp://private-example
KEY: private-example

# Heading One
## Heading Two
### Heading Three
#### Heading Four
##### Heading Five
###### Heading Six



Extended paragraph after three blank lines.

"Spoken **bold**, *italic*, ___underlined___, ~~struck~~, and `*literal*` text."

>> Arrow with **rich text** and [copy link](https://example.com/arrow) <<

>>!!
"Important **bold** and ~~struck~~ text with `literal *markers*`."
!! !! !!<<

```text
[Data3]
**Fancy title**
Some *rich* ___underlined___ and ~~struck~~ content.
- [x] completed task
- nested-looking line
```

```json
[Payload]
`{"safe": true}` and [copy docs](https://example.com/docs)
```

- ordinary no-link list text
- Review the README.md before launch
  - nested no-link list text
  -# first automatic numbered item
  -# second automatic numbered item
    -# 12 explicit nested number
1. standard ordered item
- [ ] open task
- [x] finished task

***

\# literal heading marker
\- literal dash marker
\> literal quote marker
Escaped \*star\*, \_underscore\_, \~strike\~, \`code\`, \[label\]\(url\), and \\ backslash.
| A | B |
|---|---|
| x \| y | z |

- https://example.com/source
- ../local-demo.pdf
'''
doc = SwarParser().parse(sample, path="extended_markdown.script")
kinds = [b.kind for b in doc.blocks]
html = render_doc_html(doc, "Dark Mode", allow_online_links=False)

check(kinds.count("markdown_heading") == 6, "H1 through H6 headings parsed")
for level in range(1, 7):
    check(f'class="md-heading md-h{level}"' in html, f"H{level} receives distinct reader style")
check(kinds.count("markdown_paragraph_gap") == 1, "three blank lines collapse into one extended paragraph break")
check('data-blank-lines="3"' in html and "•&nbsp;&nbsp;•&nbsp;&nbsp;•" in html, "extended paragraph break renders visibly")
check(kinds.count("markdown_fenced_box") == 2, "two fenced fancy boxes parsed")
check(sum(1 for b in doc.blocks if b.kind == "markdown_dash_item") >= 3, "ordinary dash prose, including README.md prose, stays a list")
check("markdown_numbered_tab" in kinds, "-# numbered tab list parsed")
check("markdown_ordered_item" in kinds, "standard ordered list parsed")
check("markdown_hr" in kinds, "standalone *** horizontal rule parsed")
check(sum(1 for b in doc.blocks if b.kind == "source") == 2, "URL and local path remain sources")
check("fancy-box" in html and "[Data3]" not in html and "Data3" in html, "fancy box rendered with extracted label")
check("Fancy title" in html, "fancy box body rendered")
check("<del>struck</del>" in html, "strikethrough rendered")
check('class="inline-copy-link"' in html and "copy:https%3A%2F%2Fexample.com%2Farrow" in html, "inline link is copy-only")
check("<code>*literal*</code>" in html, "inline code protects Markdown markers")
check("☑" in html and "☐" in html, "checked and unchecked tasks render distinctly")
check("(0)" in html and "(1)" in html and "(12)" in html, "automatic and explicit numbered tabs render")
check("PRIVATE" not in html or "******" in html, "private header values remain masked")

escaped_blocks = [b for b in doc.blocks if b.text in {r"\# literal heading marker", r"\- literal dash marker", r"\> literal quote marker"}]
check(len(escaped_blocks) == 3 and all(b.kind == "plain" for b in escaped_blocks), "leading backslashes prevent block syntax activation")
check("# literal heading marker" in html and "- literal dash marker" in html and "&gt; literal quote marker" in html, "escaped block markers pass through without backslashes")
check("Escaped *star*, _underscore_, ~strike~, `code`, [label](url), and \\ backslash." in html, "inline punctuation escapes pass through literally")
check("<em>star</em>" not in html and "<del>strike</del>" not in html, "escaped inline markers are not styled")
check("x | y" in html and html.count("<td>") == 2, "escaped table pipe remains inside one cell")

legacy = '''SWAR Legacy:: Test
- https://example.com
- ../demo.pdf
>>>> TITLE <<<<
"spoken"
>>!!
legacy important
!! !! !!<<
| A | B |
|---|---|
| 1 | 2 |
'''
legacy_doc = SwarParser().parse(legacy)
legacy_kinds = [b.kind for b in legacy_doc.blocks]
check(legacy_kinds.count("source") == 2, "legacy URL/path source behavior preserved")
check("arrow_title" in legacy_kinds, "legacy arrow title preserved")
check("important" in legacy_kinds, "legacy important block preserved")
check("markdown_table" in legacy_kinds, "legacy Markdown table preserved")

short_gap = SwarParser().parse("A\n\n\nB")
check("markdown_paragraph_gap" not in [b.kind for b in short_gap.blocks], "one or two blank rows retain legacy spacing")

unclosed = SwarParser().parse("```text\nhello **world**")
check(unclosed.blocks[-1].kind == "markdown_fenced_box", "unclosed fence remains visible")
check(bool(unclosed.warnings), "unclosed fence emits warning")

# Byte-for-byte compatibility gate against the last visually working r2 path.
uncolored_regression = r'''SWAR Regression:: Uncolored
URL: secret

# Heading

"Spoken **bold** text"
  - nested one
    - nested two
-# first
  -# second

>> DATA <<
>>>> TITLE <<<<

>>!!
"Important    words"
Second *line*
!! !! !!<<

```text
[Data3]
**Fancy** line
- list inside
```

| A | B |
|---|---|
| x \| y | z |

- https://example.com/page
  "source child"



After gap
'''
uncolored_doc = SwarParser().parse(uncolored_regression)
uncolored_data = [
    {
        "kind": b.kind,
        "text": b.text,
        "line_start": b.line_start,
        "line_end": b.line_end,
        "raw": b.raw,
        "indent": b.indent,
        "level": b.level,
        "attrs": b.attrs,
    }
    for b in uncolored_doc.blocks
]
uncolored_json = json.dumps(uncolored_data, sort_keys=True, ensure_ascii=False)
uncolored_html = render_doc_html(uncolored_doc, "Dark Mode", allow_online_links=False)
check(hashlib.sha256(uncolored_json.encode()).hexdigest() == "3f56b772310c1fbee3c085b5d0bf0d323ccbaac9272ad38c92f05b2e64120a4c", "uncolored parser output exactly matches working r2")
check(hashlib.sha256(uncolored_html.encode()).hexdigest() == "558cbfebd8e837e93fca52d78a67b324ef3c5a664f892ce3aed175910a4f0b81", "uncolored reader HTML exactly matches working r2")

color_sample = r'''SWAR Color Profiles:: Test
# Colored heading [#12ABEF]
"Spoken RGB" (rgb(10, 20, 30))
  - parent item
    - nested item [#abc]
>> COLORED ARROW << (rgba(255, 0, 0, 0.5))

>>!! [#556677]
inherited important line
local important line (rgb(5, 200, 7))
!! !! !!<<

```text [#102030]
[Colored Box]
inherited box line
local box line [#00ff00]
```

| A | B |
|---|---|
| x | y | [#aa00aa]

- https://example.com/colored [#1234]
Literal hex \`! [#ff00ff]
Literal rgba \`!(rgba(1, 2, 3, 0.4))
Invalid stays visible [#12345]
Eight digit [#11223344]
'''
color_doc = SwarParser().parse(color_sample)
color_html = render_doc_html(color_doc, "Dark Mode", allow_online_links=False)
color_blocks = [b for b in color_doc.blocks if b.kind != "blank"]
heading = next(b for b in color_blocks if b.kind == "markdown_heading")
nested = next(b for b in color_blocks if b.kind == "markdown_dash_item" and b.text == "nested item")
arrow = next(b for b in color_blocks if b.kind == "arrow_data")
important = next(b for b in color_blocks if b.kind == "important")
fence = next(b for b in color_blocks if b.kind == "markdown_fenced_box")
table = next(b for b in color_blocks if b.kind == "markdown_table")
source = next(b for b in color_blocks if b.kind == "source")
literal_hex = next(b for b in color_blocks if b.kind == "plain" and b.text.startswith("Literal hex"))
literal_rgba = next(b for b in color_blocks if b.kind == "plain" and b.text.startswith("Literal rgba"))
invalid = next(b for b in color_blocks if b.kind == "plain" and b.text.startswith("Invalid"))
eight = next(b for b in color_blocks if b.kind == "plain" and b.text.startswith("Eight"))

check(heading.text == "Colored heading" and heading.attrs.get("color_profile") == "#12abef", "hex suffix colors and cleans heading")
check(nested.level == 2 and nested.attrs.get("color_profile") == "#abc", "nested-list level survives color profiling")
check(arrow.attrs.get("color_profile") == "rgba(255, 0, 0, 0.5)", "rgba suffix attaches to arrow")
check(important.attrs.get("color_profile") == "#556677" and important.attrs.get("line_colors") == [None, "rgb(5, 200, 7)"], "Important object and local line profiles coexist")
check(fence.attrs.get("color_profile") == "#102030" and fence.attrs.get("line_colors") == [None, "#00ff00"], "fancy box and local line profiles coexist")
check(table.attrs.get("color_profile") == "#aa00aa" and table.attrs.get("row_colors", [])[-1] == "#aa00aa", "trailing table-row profile colors table and row")
check(source.attrs.get("color_profile") == "#1234", "source card accepts trailing profile")
check(literal_hex.text.endswith("[#ff00ff]") and "color_profile" not in literal_hex.attrs, r"\`! keeps hex token literal")
check(literal_rgba.text.endswith("(rgba(1, 2, 3, 0.4))") and "color_profile" not in literal_rgba.attrs, r"\`! keeps rgba token literal")
check(invalid.text.endswith("[#12345]") and "color_profile" not in invalid.attrs, "invalid profile remains visible and inactive")
check(eight.attrs.get("color_profile") == "#11223344", "eight-digit alpha hex accepted")

check("--swar-profile-color" not in color_html and "var(--" not in color_html, "reader uses no unsupported CSS variables")
check("swar-color-profile" not in color_html, "reader creates no generic color wrapper nodes")
check('<table class="important-table"' in color_html, "Important table structure remains intact")
check('<table class="fancy-box' in color_html, "fancy-box table structure remains intact")
check('color:#12abef !important' in color_html, "direct Qt-safe heading color emitted")
check('data-swar-local-color="rgb(5, 200, 7)"' in color_html, "Important local override emitted directly")
check('data-swar-local-color="#00ff00"' in color_html, "fancy local override emitted directly")
check('data-swar-color="rgba(255, 0, 0, 0.5)"' in color_html and 'color:#800000 !important' in color_html, "RGBA is composited against dark theme for Qt")
check("Literal hex [#ff00ff]" in color_html and "Literal rgba (rgba(1, 2, 3, 0.4))" in color_html, "escaped profile tokens remain visible")

unsafe_doc = ScriptDoc(blocks=[Block("plain", "safe text", 1, 1, attrs={"color_profile": "red; background:url(file:///private)"})])
unsafe_html = render_doc_html(unsafe_doc)
check("data-swar-color" not in unsafe_html and "background:url" not in unsafe_html, "renderer rejects injected unsafe color values")

if failures:
    print(f"\n{len(failures)} SWAR v0.7.0-rc1-r4 selftest failure(s).")
    raise SystemExit(1)
print("\nALL SWAR v0.7.0-rc1-r4 EXTENDED MARKDOWN SELFTESTS PASSED")
