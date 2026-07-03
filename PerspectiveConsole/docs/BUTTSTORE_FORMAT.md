# `.buttstore` Format Reference

`.buttstore` files are JSON files used by 3DCP Perspective Console.

## Purpose

A `.buttstore` stores:

- app state
- output/controller geometry
- deck cards
- card fields
- layers
- runtime metadata

## High-level structure

```json
{
  "buttstore_format": "3DCP-BUTTSTORE",
  "version": "0.9.4",
  "header": {},
  "under_header": {},
  "stage": {},
  "body": {},
  "footer": {}
}
```

## Sections

### header

Quick identity and active-card metadata.

### under_header

Mutable runtime state such as:

- output visibility
- window geometry
- scan settings
- output topmost/borderless flags

### stage

Autosave / dirty state.

### body

Deck cards and card content.

### footer

Reserved for history, future counters, migration metadata, and long-lived data.

## Layer examples

Emoji layer:

```json
{
  "id": "emoji-example",
  "type": "emoji",
  "name": "Check",
  "text": "✅",
  "x": 820,
  "y": 340,
  "size": 28,
  "opacity": 1.0,
  "visible": true,
  "z": 10
}
```

Image layer:

```json
{
  "id": "image-example",
  "type": "image",
  "name": "Logo",
  "source_path": "/path/to/user_data/imported_pngs/logo.png",
  "x": 760,
  "y": 245,
  "scale": 100,
  "opacity": 1.0,
  "visible": true,
  "z": 11
}
```

Text layer:

```json
{
  "id": "text-example",
  "type": "text",
  "name": "Note",
  "text": "Discussion point",
  "x": 740,
  "y": 185,
  "size": 22,
  "opacity": 1.0,
  "color": "#e8fff5",
  "wrap_width": 260,
  "visible": true,
  "z": 12
}
```
