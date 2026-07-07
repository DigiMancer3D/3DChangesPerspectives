# SWAR Script Markup Specification

SWAR Script Markup is a forgiving text markup style for show scripts. It is not strict JSON.

## Header

A typical first line:

```text
3D Changes Perspectives:: Episode Name: Details
```

Private header fields are recognized and masked in reader mode:

```text
URL: rtmp://...
key: private-key
CHAT TOKEN: https://...
META DATA: tags...
```

Reader display uses exactly `******` for hidden values.

## Arrow levels

Arrow length carries meaning:

| Shape | Meaning |
|---|---|
| `>> DATA <<` | Data |
| `>>> VERBATIM <<<` | Verbatim / cue text |
| `>>>> TITLE <<<<` | Section or sub-section title |
| `>>>>> DESCRIPTOR <<<<<` | Descriptor |
| `>>>>>> EXPLAINER <<<<<<` | Explainer |
| `>>>>>>> MAJOR <<<<<<<` | Major explainer |

`EXIT TO BACKGROUND`, `LEAVE CONTEXT`, and similar exit lines get red transition arrows. `RETURN TO SHOW`, `JUMP IN`, and similar return lines get green transition arrows.

## Important blocks

```text
>>!!
      "Hard    to read    text"
                !!         !!         !!<<
```

Important blocks are centered and use the important section color.

## Dividers

```text
--------------------------------------
--- OPENING SECTION ---
```

Text between starting and ending triple dashes becomes centered inside the divider line.

## Sources

Public sources:

```text
- https://example.com/page
    "Talk about this source."
```

Local sources:

```text
- ../demo.pdf
```

Split-source form is supported:

```text
-
https://example.com/page
```

Private bang-link sources are masked/non-exported.

## Markdown additions

SWAR recognizes common Markdown inside `.script`, `.md`, and `.txt`:

- Headings `#` through `######`.
- Bold, italic, strong bold+italic.
- Tables.
- Blockquotes and nested blockquotes.
- Custom lists: `+ item`, `- [#] item`, `- [$] item`, `- [%15] item`.
- Underline with `___underlined text___`.
