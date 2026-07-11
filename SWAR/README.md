# SWAR - Script Writer and Reader

**Version: 0.6.0-rc1-r2**

SWAR is a lightweight local desktop tool for writing and reading 3DChangesPerspectives-style show scripts. It supports SWAR Script Markup (`.script`), Markdown (`.md`), and plain text (`.txt`) with a forgiving parser that intelligently combines multiple markup styles into a unified reading and editing experience.

## Features

### 🎨 Multiple Display Modes
- **Reader Mode**: Immersive, read-only viewing with rich formatting (local-only)
- **Editor Mode**: Full editing capabilities with live preview and syntax highlighting
- **Split Mode**: Side-by-side editor and preview for real-time feedback

### 🌈 Built-in Themes
- **Dark Mode** (default) - High contrast for reduced eye strain
- **Light Mode** - Bright, clean interface
- **Paper Mode** - Print-friendly aesthetic
- **Terminal Mode** - Retro green-on-black styling
- **Blue Mode** - Cool, professional blue palette
- Theme switching available in GUI with user customization via `SWAR.udata`

### 📝 Rich Markup Support
SWAR intelligently parses and renders:
- **Custom Arrow Syntax** - Visual hierarchy markers (>> >>> >>>> >>>>> >>>>>> >>>>>>>)
- **Important Blocks** - Highlighted attention-grabbing content with !! markers
- **Source/Link Management** - URL tracking, local path references, and private link masking
- **Markdown Elements** - Headings, blockquotes, lists, tables, check items, percent lists
- **Inline Formatting** - Bold, italic, code, underline, emphasis
- **Dividers & Sections** - Visual content organization with centered text support
- **Special Markers** - Bang notices, spoken dialogue, legacy labels

### 🔍 Editing Features
- **Line Number Gutter** - Easy navigation and reference
- **Syntax Highlighting** - Context-aware color coding for all markup types
- **Spell Check** - Optional spell checking with local dictionary support
- **Find & Search** - Full-text search with case sensitivity options
- **Snippet Insertion** - Pre-built content templates for common structures
- **Emoji Picker** - Quick emoji insertion with customizable emoji list
- **Multi-Tab Interface** - Manage multiple documents simultaneously

### 🎯 Export Capabilities
- **Standalone HTML Generation** - Self-contained, no external dependencies
- **Theme-Aware Rendering** - Applies current theme to exported HTML
- **Responsive Design** - Mobile-friendly output
- **Outline Export** - Extract document structure as outline text (public links only)
- **Parser Summary** - Debug information and document statistics

### 🛡️ Privacy Features
- **Private Link Masking** - URLs wrapped with `!!...!!` display as `PRIVATE LINK: ******` in reader mode
- **Meta Secret Redaction** - Sensitive keys (URL, KEY, CHAT TOKEN, META) are masked
- **Reader-Only Mode** - Disabled editor features prevent accidental modifications
- **Public-Only Export** - Outline export includes only public source links

## Installation

### Requirements
- **Python**: 3.9+
- **PyQt6**: For GUI application
- **Standard Library Only**: Core parsing requires no external dependencies

### Quick Start (Kubuntu 24+)

```bash
chmod +x install_kubuntu.sh launch_reader.sh launch_standard.sh run_selftests.sh install_desktop_entries.sh
./install_kubuntu.sh
./run_selftests.sh
./launch_standard.sh examples/example.script
```

### Manual Setup
```bash
pip install PyQt6
python -m swar.swar --help
```

### Desktop Integration
```bash
./install_desktop_entries.sh    # Install reader and editor launchers
./launch_reader.sh              # Launch reader-only mode
./launch_standard.sh            # Launch editor mode
```

## Usage

### Command Line

#### Launch Interactive Shell
```bash
python -m swar.swar                          # New document
python -m swar.swar path/to/script.script    # Open existing file
```

#### Mode Options
```bash
python -m swar.swar --reader path/to/file     # Reader-only mode (local files only)
python -m swar.swar --standard path/to/file   # Standard reader/editor mode
```

#### Export Operations
```bash
python -m swar.swar --render-html output.html path/to/script.script    # Export to HTML
python -m swar.swar --outline path/to/script.script                    # Generate outline
python -m swar.swar --parse-summary path/to/script.script              # Show parser summary
```

#### Theme Selection
```bash
python -m swar.swar --theme "Dark Mode" path/to/file
```

#### Custom Data Directory
```bash
python -m swar.swar --udata custom/path/to/SWAR.udata path/to/file
```

### Keyboard Shortcuts (GUI)

| Action | Shortcut |
|--------|----------|
| New Tab | Ctrl+N |
| Open File | Ctrl+O |
| Save | Ctrl+S |
| Close Tab | Ctrl+W |
| Find/Search | Ctrl+F |
| Toggle Spell Check | Ctrl+Shift+S |
| Refresh Preview | Ctrl+R |

## File Formats

### Supported Input Formats
- `.script` - SWAR Script Markup (primary format)
- `.md` - Markdown
- `.txt` - Plain text

### Output Formats
- `.html` - Standalone HTML preview
- `.txt` - Outline export

## Markup Reference

### Arrow Syntax (Visual Hierarchy)
```
>> DATA                              # 2 arrows - data marker
>>> VERBATIM CODE BLOCK             # 3 arrows - verbatim/code
>>>> SECTION TITLE <<<<             # 4 arrows - section title (centered)
>>>>> DESCRIPTOR <<<<<              # 5 arrows - descriptor (centered, dashed)
>>>>>> EXPLANATION <<<<<<           # 6 arrows - explanation block
>>>>>>> MAJOR SECTION <<<<<<<       # 7+ arrows - major section (centered with side arrows)
```

### Important Blocks
```
>> IMPORTANT !!
Content goes here
Multiple lines supported
!! <<

>>> VERBATIM IMPORTANT !!!
Code block content
!!! <<<
```

### Source/Link References
```
- https://example.com              # URL source
- /path/to/local/file              # Local file reference
-                                   # Empty source slot

!! https://private-link.com !!     # Private link (masked as PRIVATE LINK: ****** in reader)
```

### Markdown Elements
```
# Heading 1
## Heading 2
...
###### Heading 6

> Blockquote
>> Nested blockquote

- [ ] Unchecked item
- [x] Checked item
- [#] Numbered item
- [$] Money item
- [%50] Percent item (50%)
+ Bullet point

| Column 1 | Column 2 |
|----------|----------|
| Cell     | Cell     |

"Spoken dialogue or quotation"

--- Center Text ---
-----------
```

### Special Markers
```
!! NOTICE !!                         # Bang notice (warning marker)
"Quoted dialogue"                    # Spoken text
label:                               # Legacy section label

--------                             # Divider
--- Titled Divider ---             # Divider with center text

|| \/ || \/                         # Down arrows (visual continuation)
```

### Meta Information
```
URL: https://example.com            # Public URL metadata (masked if no URL marker)
KEY: secret_key_value               # Private key (masked)
CHAT TOKEN: bot_token_123           # Chat token (masked)
META: metadata_value                # Generic metadata
META DATA: data_value               # Multi-word metadata
```

## Architecture

### Core Modules

**`parser.py`** - Document parsing engine
- `SwarParser` - Main parsing engine with forgiving error handling
- `ScriptDoc` - Document structure container with metadata
- `Block` - Individual content block with attributes and line tracking
- Regex-based pattern matching for all markup types
- Stateful parsing for multi-line blocks (important, tables, down arrows)

**`renderer_html.py`** - HTML export and rendering
- `render_doc_html()` - Convert parsed documents to standalone HTML with CSS
- `render_block()` - Individual block rendering with theme application
- Theme-aware CSS generation with responsive layout
- Support for all block types with semantic HTML

**`themes.py`** - Theme and color management
- `Theme` - Color palette definition (frozen dataclass with defaults)
- 5 built-in themes with customizable fallback colors
- Dynamic theme switching and persistence
- Color scheme includes: base colors, highlights, semantic colors, fade variants

**`gui_shell.py`** - GUI application and interface
- `SwarShellWindow` - Main application window with multi-tab support
- `SwarTab` - Document tab with editor/preview panels and sync
- `ScriptSyntaxHighlighter` - Real-time syntax highlighting for editor
- `LineNumberArea` - Low-resource line number gutter
- Emoji picker, snippet manager, find/search panel
- Responsive toolbar with dynamic layout
- User data persistence integration

**`udata.py`** - User data persistence
- User settings and preferences storage
- Theme overrides management
- Snippet configuration
- Emoji list customization
- Application statistics (startup count, etc.)

## Development

### Parser Block Types
The parser recognizes these block types:
```
Content:        header, blank, plain, spoken
Arrows:         arrow_data, arrow_verbatim, arrow_title, 
                arrow_descriptor, arrow_explainer, arrow_major_explainer
Special:        important, bang_notice, divider, down_arrows, source
Markdown:       markdown_heading, markdown_blockquote, markdown_table
Lists:          markdown_check_item, markdown_num_item, 
                markdown_money_item, markdown_bullet_item, markdown_percent_list
Metadata:       meta_secret, legacy_label
```

### Extending Themes
Add a new theme to `themes.py`:
```python
THEMES["My Theme"] = Theme(
    name="My Theme",
    bg="#ffffff",           # Background
    text="#000000",         # Main text
    link="#0000ff",         # Link color
    highlight="#ff0000",    # Primary highlight
    panel="#f0f0f0",        # Panel/block background
    muted="#808080",        # Muted/secondary text
    border="#cccccc",       # Border color
    important="#ff6600",    # Important block color
    cue="#0099cc",          # Cue/hint color
    title="#000000",        # Title color
    source="#009900",       # Source/link color
    table_border="#999999", # Table border
    # Optional semantic colors with defaults:
    data="#6aa4ff",
    verbatim="#dddddd",
    section_title="#ffffff",
    descriptor="#cc99ff",
    explainer="#ffaa44",
    major_explainer="#b476ff",
    markdown_heading="#000000",
    markdown_table="#999999",
)
```

## Configuration

### `SWAR.udata` (User Data File)
Persistent JSON file storing:
- **Theme**: Current theme selection
- **Editor Preferences**: Font, tab size, line wrapping
- **Spell Checker**: Enabled state and dictionary path
- **Snippets**: Custom snippet definitions
- **Emoji List**: User's current emoji selections
- **Statistics**: Application usage counts

### Customization
- **Themes**: Modify color values in `themes.py`
- **Emoji List**: Edit `current.emoji` or use GUI picker to save
- **Snippets**: Configure via `SWAR.udata`
- **Spell Checking**: Toggle via GUI and configure dictionary

## Performance Notes

- **Parser**: O(n) single-pass linear scan, efficient even for large documents
- **Rendering**: Buffered HTML generation with CSS precomputation
- **Memory**: Lightweight, suitable for resource-constrained environments
- **Highlighting**: Asynchronous syntax highlighting runs without blocking UI
- **Theme Switching**: Instant with no document reload required

## Testing

Run the test suite:
```bash
./run_selftests.sh
# or
pytest SWAR/tests/
```

Verify release package:
```bash
./tools/verify_release_package.sh
./tools/desktop_launcher_doctor.sh
```

## Limitations & Known Issues

- Maximum heading level: 6 (as per Markdown spec)
- Arrow syntax requires balanced pairs for "balanced" classification
- Private links cannot be copied in reader mode (security feature)
- Spell checker requires `enchant` library for non-English languages
- Some regex patterns may timeout on extremely malformed input

## Privacy & Security

⚠️ **Important**: Do not upload show scripts containing stream keys, chat tokens, or private URLs to public repositories. While SWAR masks these in reader mode, the source files retain the original sensitive text.

Features for sensitive data:
- Private URL masking: `!! URL !!` → displays as `PRIVATE LINK: ******`
- Meta secret redaction: `KEY: value` → displayed with masked value
- Reader-only mode: Disables editing to prevent accidental changes

## Contributing

Contributions welcome! Areas for improvement:
- Additional theme designs
- Expanded Markdown support
- Performance optimizations
- Platform-specific improvements
- Documentation and examples
- Bug reports and feature requests

## Project Structure

```
SWAR/
├── swar.py                  # Main CLI entry point
├── swar/                    # Python package
│   ├── parser.py           # Document parser
│   ├── renderer_html.py    # HTML rendering
│   ├── themes.py           # Theme definitions
│   ├── gui_shell.py        # GUI application
│   └── udata.py            # User data persistence
├── examples/               # Starter example scripts
├── tests/                  # Parser/render/GUI tests
├── desktop/                # Desktop entry templates
├── tools/                  # Release and verification scripts
├── docs/                   # User and developer documentation
├── current.emoji           # Emoji list configuration
├── SWAR.udata             # User settings template
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

## License

See parent repository: [3DChangesPerspectives](https://github.com/DigiMancer3D/3DChangesPerspectives)

## Related

Part of the **3D Changes Perspectives** project - educational visual content for YouTube.

---

**Questions or Issues?**
- Open an issue on the [main repository](https://github.com/DigiMancer3D/3DChangesPerspectives/issues)
- Check the documentation in `docs/` folder
- Run `./run_selftests.sh` to verify installation
