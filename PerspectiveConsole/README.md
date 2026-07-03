# 3DCP Perspective Console

**Version:** 1.0.0

## Overview

The **3DCP Perspective Console** is a specialized analytical interface designed for the 3D Changes Perspectives webshow. This interactive console enables systematic source analysis, evidence evaluation, and claim verification through an intuitive card-based visual system.

The console provides content creators with a structured environment to examine information sources, assess confidence levels, and track verification status in real-time, with comprehensive visual overlay capabilities and customizable emoji-based annotation systems.

## Purpose

The 3DCP Perspective Console serves as a central tool for:

- **Source Analysis**: Evaluate and categorize information sources with confidence assessments
- **Evidence Tracking**: Document cited sources and supporting evidence visually
- **Claim Verification**: Monitor verification status of claims and identify outstanding questions
- **Interactive Visualization**: Display analysis through resizable, borderless output windows with customizable UI elements
- **Educational Content Generation**: Facilitate production of explainer materials for the YouTube webshow

## Project Structure

```
PerspectiveConsole/
├── 3dcp_perspective_console.py           # Core application entry point
├── VERSION.txt                            # Version information
├── requirements.txt                       # Python package dependencies
├── README.md                              # This file
│
├── templates/                             # Console configuration templates
│   └── default_episode_template.buttstore # Default episode configuration
│
├── emoji_presets/                         # Emoji annotation presets
│   └── default_presets.emoji              # Standard emoji library
│
├── docs/                                  # Additional documentation
│
├── Launch Scripts:
│   ├── launch_3dcp_console.sh            # Basic console launcher
│   └── launch_3dcp_console_venv.sh       # Virtual environment launcher
│
├── Setup Scripts:
│   ├── setup_venv_3dcp_console.sh        # Virtual environment configuration
│   └── install_parent_launcher.sh        # Parent directory launcher installation
│
├── Maintenance Scripts:
│   ├── doctor_3dcp_console.sh            # System diagnostics and troubleshooting
│   ├── health_report_3dcp_console.sh     # Health status reporting
│   ├── acceptance_3dcp_console.sh        # Acceptance testing suite
│   ├── reset_window_positions.sh         # Window geometry reset utility
│   ├── cleanup_stale_root_files.sh       # Stale file cleanup
│   ├── archive_duplicate_buttstores.sh   # Buttstore archive management
│   ├── migrate_legacy_buttstores.sh      # Legacy data migration
│   └── release_package_3dcp_console.sh   # Release packaging utility
│
└── prepare_github_upload.sh               # GitHub upload preparation
```

## System Architecture

### Core Components

**Application** (`3dcp_perspective_console.py`)
- Main GUI controller managing the analysis interface
- Supports multiple card-based views for different analysis modes
- Real-time output rendering at 960×500px (default)
- Implements ABI: `3dcp.perspective_console.buttstore.v0`

### Data Format

**Buttstore Format** (`.buttstore` files)
- JSON-based persistent storage format for console sessions
- Maintains complete state including:
  - Card definitions and field values
  - Visual layer configurations (position, opacity, z-index)
  - Window geometry and UI state
  - Session history and serial tracking
- Version: `1.0.0-rc1`

**Emoji Presets** (`.emoji` files)
- Pipe-delimited preset library for visual annotations
- Categories: Status, Lab, People, Arrows, Shapes, Numbers, Objects, Crypto, Places, Animals, Food, and Symbols
- Format: `EMOJI|Name|Category /`

### Output Configuration

- **Default Resolution**: 960×500 pixels
- **Background Color**: `#121418` (dark theme)
- **Scanner Color**: `#00ff99` (neon green accent)
- **Theme**: "The Perspective Lab"

## Installation

### Prerequisites

- **Python**: 3.7 or later
- **Operating System**: macOS, Linux, or Windows (with appropriate shell compatibility)
- **Disk Space**: Minimal (< 50 MB)

### Quick Start

1. **Clone or Download** the repository:
   ```bash
   git clone https://github.com/DigiMancer3D/3DChangesPerspectives.git
   cd 3DChangesPerspectives/PerspectiveConsole
   ```

2. **Set Up Virtual Environment** (recommended):
   ```bash
   bash setup_venv_3dcp_console.sh
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Launch the Console**:
   ```bash
   bash launch_3dcp_console_venv.sh
   ```

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `qrcode` | ≥7.4.2 | QR code generation for source linking |
| `Pillow` | ≥10.0.0 | Image processing and rendering |

See `requirements.txt` for the complete dependency list.

## Usage

### Starting the Application

#### Standard Launch
```bash
bash launch_3dcp_console.sh
```

#### With Virtual Environment
```bash
bash launch_3dcp_console_venv.sh
```

### Basic Workflow

1. **Open a Buttstore Template**: Load a default or custom episode configuration
2. **Activate Analysis Card**: Select the "Source Analyzer" card to begin source evaluation
3. **Enter Source Information**:
   - Source Type (Primary/Secondary/Tertiary)
   - Confidence Level (Low/Medium/High)
   - Source Link (URL reference)
4. **Document Evidence**: Add cited sources and supporting evidence
5. **Define Questions**: List outstanding verification needs
6. **Update Verdict**: Set claim status (Still Checking/Verified/Contested)
7. **Export**: Prepare and upload finalized analysis

### Configuration

#### Custom Emoji Presets

Edit or create new emoji preset files in `emoji_presets/`:

```
📚|Book|Objects /,
🎓|Graduation|Objects /,
```

Each entry: `EMOJI|Label|Category /`

#### Template Customization

Modify `.buttstore` files in `templates/` to customize default layouts, field values, and visual layers.

## Maintenance & Troubleshooting

### Diagnostic Commands

**Check System Health**:
```bash
bash health_report_3dcp_console.sh
```

**Run Full Diagnostics**:
```bash
bash doctor_3dcp_console.sh
```

**Execute Acceptance Tests**:
```bash
bash acceptance_3dcp_console.sh
```

### Common Tasks

| Task | Command |
|------|---------|
| Reset window positions | `bash reset_window_positions.sh` |
| Clean temporary files | `bash cleanup_stale_root_files.sh` |
| Migrate legacy data | `bash migrate_legacy_buttstores.sh` |
| Archive duplicates | `bash archive_duplicate_buttstores.sh` |

### Troubleshooting

**Issue: Import errors or missing dependencies**
- Run: `bash doctor_3dcp_console.sh`
- Reinstall dependencies: `pip install --upgrade -r requirements.txt`

**Issue: Window geometry issues**
- Reset positions: `bash reset_window_positions.sh`

**Issue: Legacy data incompatibility**
- Run migration: `bash migrate_legacy_buttstores.sh`

## File Format Reference

### Buttstore Structure

```json
{
  "buttstore_format": "3DCP-BUTTSTORE",
  "version": "1.0.0-rc1",
  "header": { /* configuration and metadata */ },
  "under_header": { /* UI state and geometry */ },
  "stage": { /* draft/staging data */ },
  "body": { /* active cards and content */ },
  "footer": { /* history and serial tracking */ }
}
```

### Card Definition

```json
{
  "id": "source-analyzer",
  "label": "Source Analyzer",
  "type": "source_analyzer",
  "fields": {
    "sourceType": "Primary",
    "confidence": "Medium",
    "sourceLink": "",
    "claim": "Current claim goes here.",
    "evidence": "Evidence shown on browser or cited source.",
    "openQuestion": "What still needs checking?",
    "verdict": "Still Checking"
  },
  "layers": [ /* visual overlay definitions */ ]
}
```

## Release & Deployment

### Prepare for Release

```bash
bash prepare_github_upload.sh
```

### Generate Release Package

```bash
bash release_package_3dcp_console.sh
```

### Installation for Parent Directory

```bash
bash install_parent_launcher.sh
```

This creates launcher shortcuts at the parent directory level for convenient access.

## Documentation

Additional documentation is available in the `docs/` directory. Refer to individual script files for detailed usage information.

---


