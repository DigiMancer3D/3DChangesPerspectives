# Markdown in SWAR

SWAR accepts common Markdown in `*.md`, `*.script`, and `*.txt`. The parser is forgiving: malformed or unknown text should remain visible instead of disappearing.

## Headings

```text
# H1
## H2
### H3
#### H4
##### H5
###### H6
```

All six levels have distinct Reader styling.

## Inline formatting

```text
**bold**
*italic*
***bold and italic***
___underline___
~~strike~~
`literal syntax breakout`
[copyable label](https://example.com)
```

Backtick spans protect the contained marks from recursive styling. Rendered links are local-first and copy-oriented.

## Quotes and lists

```text
> blockquote
>> nested blockquote

- ordinary no-marker item
- [ ] task
- [x] completed task
- [#] number marker
- [$] money marker
- [%50] percent item
-# automatically numbered tab
-# 12 explicit numbered tab
1. ordinary ordered item
+ plus bullet
```

Indent list lines to create nesting.

## Tables

```text
| Column A | Column B |
| --- | --- |
| One | Two |
```

Use `\|` for a literal pipe inside a cell.

## Horizontal and paragraph rules

A standalone `***` creates a horizontal rule. One or two blank rows keep legacy spacing. Three or more consecutive blank rows become one extended paragraph separator.

## Fancy fenced boxes

````text
```text
[Optional Label]
**Rich content** inside the presentation box.
```
````

The fence language appears on the rail. An unclosed fence remains visible with a warning style.

## SWAR additions inside Markdown

SWAR inline arrows, super/subscript, color profiles, and presentation marks are available in Markdown files. A line-start `-> ` is the SWAR four-space indent mark, so escape it as `\-> ` when literal source is required.

## Escaping

Use a backslash before punctuation that should stay literal:

```text
\# \- \> \* \_ \~ \` \[ \] \( \) \|
```

Use `\\` to show one backslash.
