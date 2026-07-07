# SWAR — Script Writer and Reader

SWAR is a lightweight local desktop tool for writing and reading 3DChangesPerspectives-style show scripts. It supports SWAR Script Markup (`*.script`), Markdown (`*.md`), and plain text (`*.txt`) with a local-first reader and a low-resource editor/shell.

## Current package

This is **SWAR v0.6.0-rc1-r2**, a release-candidate package built from the approved Phase 5-R2 baseline.

Included features:

- Reader, Editor, and Split modes.
- Reader-only local mode with editor tools disabled.
- Private header masking for `URL`, `KEY`, `CHAT TOKEN`, and metadata.
- Multi-tab shell with responsive toolbar layout.
- Save dropdown for `.script`, `.md`, and `.txt`.
- Outline export for public source links only.
- Script Markup parser for arrows, dividers, sources, important blocks, markdown additions, lists, and tables.
- Editor dropdowns for sections, sub-sections, sources, markdown, templates, and custom emoji.
- Local `Tools` dropdown with Find/Search and optional local spellcheck.
- User-customizable `SWAR.udata` persistence file.
- User-customizable `current.emoji` list.
- Optional desktop launchers for Reader and Standard mode.

## Quick start on Kubuntu 24+

```bash
chmod +x install_kubuntu.sh launch_reader.sh launch_standard.sh run_selftests.sh install_desktop_entries.sh tools/*.sh
./install_kubuntu.sh
./run_selftests.sh
./launch_standard.sh examples/example.script
```

Reader-only mode:

```bash
./launch_reader.sh examples/example.script
```

Optional desktop entries:

```bash
./install_desktop_entries.sh
```

## Release-candidate checks

```bash
./tools/desktop_launcher_doctor.sh
./tools/verify_release_package.sh
./tools/build_github_upload.sh
```

`tools/build_github_upload.sh` creates a clean `GITHUB_UPLOAD/` folder. Upload the contents of that folder as the repository root.

## Folder map

```text
swar.py                    Main CLI/launcher
swar/                      Python application package
examples/                  Safe starter examples
tests/                     Parser/render/save/GUI-smoke tests
desktop/                   Desktop-entry templates
tools/                     Verification and release helpers
current.emoji              Starter emoji list
SWAR.udata                 Starter persistence/theme/snippet file
docs/                      User/developer/spec/release documentation
```

## Privacy note

Do not upload personal show scripts that contain stream keys, chat tokens, or private links. SWAR masks these in reader mode, but the source files themselves still contain the original text.
