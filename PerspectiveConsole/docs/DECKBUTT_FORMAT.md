# `.deckbutt` Format Reference

`.deckbutt` files are JSON files that store one reusable deck card.

## Purpose

Use `.deckbutt` files to save individual cards for reuse across streams, episodes, or future `.buttstore` databases.

## Location

Default folder:

```text
user_data/deckbutts/
```

## Structure

```json
{
  "deckbutt_format": "3DCP-DECKBUTT",
  "version": "0.9.4",
  "created_at": "UTC timestamp",
  "source_app": "3DCP Perspective Console",
  "card": {}
}
```

## Behavior on load

When loaded into the deck:

- card ID is regenerated
- layer IDs are regenerated
- label is made unique if needed
- card content and layers are preserved
