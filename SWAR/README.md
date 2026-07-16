# SWAR - Script Writer and Reader

**Version: 0.7.1-rc1-r3**

SWAR is a lightweight local desktop tool for writing, viewing, and authoring 3DChangesPerspectives-style show scripts and Story Arc records. It supports SWAR Script Markup (`.script`), Markdown (`.md`), plain text (`.txt`) — and, as of v0.7.x, Story Arc record files (`.arcs`).

## Features

### 🎨 Multiple Display Modes
- **Reader Mode**: Immersive, read-only viewing with rich formatting (local-only)
- **Editor Mode**: Full editing capabilities with live preview and syntax highlighting
- **Split Mode**: Side-by-side editor and preview for real-time feedback
- **Story / Arcs Mode**: Author and save Story Arc records (`*.arcs`) and preview them as cards in the UI

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
- **Story Arc Records** (`.arcs`) — Seven-field records parsed into structured story cards and screenplay-style elements (see Architecture / arc_tools.py)

### 🔍 Editing Features
- **Line Number Gutter** - Easy navigation and reference
- **Syntax Highlighting** - Context-aware color coding for all markup types
- **Spell Check** - Optional spell checking with local dictionary support
- **Find & Search** - Full-text search with case sensitivity options
- **Snippet Insertion** - Pre-built content templates for common structures (including Arc snippets)
- **Emoji Picker** - Quick emoji insertion with customizable emoji list
- **Multi-Tab Interface** - Manage multiple documents simultaneously

### 🎯 Export Capabilities
- **Standalone HTML Generation** - Self-contained, no external dependencies
- **Theme-Aware Rendering** - Applies current theme to exported HTML
- **Responsive Design** - Mobile-friendly output
- **Outline Export** - Extract document structure as outline text (public links only). Works for `.script`, `.md`, `.txt`, and for `.arcs` produces a compact card list
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
- **Standard Library Only**: Core parsing requires no external dependencies (runtime GUI needs PyQt6)

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
python -m swar.swar path/to/script.script    # Open existing file (.script/.md/.txt/.arcs)
python -m swar.swar path/to/story.arcs       # Open and parse Story Arc records
```

#### Mode Options
```bash
python -m swar.swar --reader path/to/file     # Reader-only mode (local files only)
python -m swar.swar --standard path/to/file   # Standard reader/editor mode
```

#### Export Operations
```bash
python -m swar.swar --render-html output.html path/to/script.script    # Export to HTML
python -m swar.swar --outline path/to/script.script                    # Generate outline (also works for .arcs)
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
- `.arcs` - Story Arc record files (structured seven-field records; parsed into `arc_record` blocks and story elements)

### Output Formats
- `.html` - Standalone HTML preview
- `.txt` - Outline export

## Markup Reference

(unchanged — supports Arrow Syntax, Important Blocks, Markdown elements, Special markers, Meta information)

## Architecture

### Core Modules

**`parser.py`** - Document parsing engine
- `SwarParser` - Main parsing engine with forgiving error handling
- Recognizes `.arcs` files: `parse()` dispatches to a dedicated arcs document parser when the path suffix is `.arcs` and produces `arc_record` blocks
- `ScriptDoc` - Document structure container with metadata
- `Block` - Individual content block with attributes and line tracking
- Regex-based pattern matching for all markup types
- Stateful parsing for multi-line blocks (important, tables, down arrows)

**`arc_tools.py`** - Story Arc parsing and utilities
- `ArcRecord` dataclass: name, estimated, zone_type, start_message, map_ref, arc_data, confirm_message
- `parse_arcs_text()` / `parse_arc_line()` - Converts .arcs text rows into ArcRecord instances and collects warnings
- `parse_story_arc_data()` - Tokenizes Arc Data into screenplay-friendly elements (talk, data, directives, options)
- Snippets and templates for Arc authoring

**`renderer_html.py`** - HTML export and rendering
- `render_doc_html()` - Convert parsed documents (including `.arcs` arc_record blocks) to standalone HTML with CSS
- Theme-aware CSS generation with responsive layout

**`gui_shell.py`** - GUI application and interface
- `SwarShellWindow` - Main application window with multi-tab support and modes (reader, editor, split, story)
- Save dialog and file filters include Story Arcs (`*.arcs`) so the editor can author and persist arc records

**`udata.py`** - User data persistence
- User settings and preferences storage (SWAR.udata)

## Notable additions in v0.7.x
- First-class `.arcs` support: parsing, story-element extraction, snippets and save/load support in GUI
- Story Mode in the editor for authoring/storyboard workflows
- Improved parser handling for presentation marks (page gaps, golden highlights, attention banners)
- CLI and GUI consistency: save/open filters and outline export updated to include arcs where appropriate

## Development

### Parser Block Types (high-level)
The parser recognizes these block types (abridged):
- Content: header, blank, plain, spoken
- Arrows: arrow_data, arrow_verbatim, arrow_title, arrow_descriptor, arrow_explainer, arrow_major_explainer
- Special: important, bang_notice, divider, down_arrows, source
- Markdown: markdown_heading, markdown_blockquote, markdown_table
- Arc: arc_record (one per .arcs record, with structured attrs and story_elements)

### Extending Themes
Add a new theme to `themes.py` (example in `themes.py` remains valid).

## Configuration

### `SWAR.udata` (User Data File)
Persistent JSON file storing:
- **Theme**: Current theme selection
- **Editor Preferences**: Font, tab size, line wrapping
- **Spell Checker**: Enabled state and dictionary path
- **Snippets**: Custom snippet definitions (includes Arc snippets)
- **Emoji List**: User's current emoji selections
- **Statistics**: Application usage counts

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
- `.arcs` parsing performs conservative validation and will emit warnings for malformed records (see arc_tools.parse_arc_line warnings)

## Privacy & Security

⚠️ **Important**: Do not upload show scripts containing stream keys, chat tokens, or private URLs to public repositories. While SWAR masks these in reader mode, the source files retain the original content.

## Contributing

Contributions welcome! Areas for improvement:
- Additional theme designs
- Expanded Markdown support
- Performance optimizations
- Platform-specific improvements
- Documentation and examples (including more .arcs examples)
- Bug reports and feature requests

## Project Structure

```
SWAR/
├── swar.py                  # Main CLI entry point
├── swar/                    # Python package
│   ├── parser.py           # Document parser (now handles .arcs dispatch)
│   ├── arc_tools.py        # .arcs parsing and story-arc helpers
│   ├── renderer_html.py    # HTML rendering
│   ├── themes.py           # Theme definitions
│   ├── gui_shell.py        # GUI application
│   └── udata.py            # User data persistence
├── examples/               # Starter example scripts (include example.arcs)
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
