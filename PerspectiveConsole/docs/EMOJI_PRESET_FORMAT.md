# `.emoji` Preset Format

Emoji preset files use a simple text format.

## Default user file

The app auto-loads this file when present:

```text
user_data/current.emoji
```

If it is missing, the packaged default is used:

```text
data/emoji_presets/default_presets.emoji
```

## Record separator

Each record ends with:

```text
/,
```

## Basic format

```text
emoji|name|category /,
```

## Examples

```text
✅|Check|Status /,
🧪|Test Tube|Lab /,
🔗|Link|Objects /,
```

## Minimal format

The parser also supports emoji-only records:

```text
✅ /,
🔥 /,
👀 /,
```

Names/categories will be filled with defaults.
