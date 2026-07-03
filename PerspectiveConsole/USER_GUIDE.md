# 3DCP Perspective Console User Guide

## Purpose

3DCP Perspective Console is a low-resource Tkinter overlay controller for streamer / VTuber discussion segments. It provides a private controller window and a separate OBS-friendly output window.

The app is designed around:

- no pygame
- no browser/Electron overlay
- low resource usage
- stable `.buttstore` persistence
- window capture in OBS

## Launch flow

From a version folder:

```bash
chmod +x *.sh
./doctor_3dcp_console.sh
./migrate_legacy_buttstores.sh
./setup_venv_3dcp_console.sh
./acceptance_3dcp_console.sh
./health_report_3dcp_console.sh
./launch_3dcp_console_venv.sh
```

For normal daily use after setup has already passed:

```bash
./launch_3dcp_console_venv.sh
```

## Shared user data

Runtime files are stored outside the version folder:

```text
user_data/
  buttstores/
  deckbutts/
  emoji presets
  exports/
  imported_pngs/
  reports/
  runtime/
  .venv/
```

This lets you unzip new app versions without losing your work.

## Controller and output

The controller is private. The output window is intended for OBS Window Capture.

Stable output window title:

```text
3DCP Perspective Console - Output
```

## Layer system

Each card can contain:

- emoji layers
- PNG image layers
- custom text layers

Each layer can be:

- named
- moved
- shown/hidden
- nudged
- snapped
- duplicated
- layered up/down
- deleted

## Deck cards

The first six cards appear as sidebar deck buttons. Additional cards remain in Deck Card Storage.

Deck tools include:

- rename card
- add source card
- add blank card
- duplicate card
- delete card
- save/load `.deckbutt`
- swap active
- swap click
- silent swap click

## Exporting

Single-card export:

```text
user_data/exports/YYYYMMDD/
```

Export all cards:

```text
user_data/exports/YYYYMMDD_backup/
```

## Hotkeys

Hotkeys work when the controller window has focus and are ignored while typing.

Common hotkeys:

```text
Ctrl+1 ... Ctrl+6    Select deck cards
Ctrl+B               Blank / Hide
Ctrl+O               Show output
Ctrl+Shift+O         Hide output
Ctrl+R               Scan Once
Ctrl+L               Toggle Scan Loop
Ctrl+S               Save + Apply
Ctrl+E               Export Card PNG
Ctrl+Alt+R           Rescue Output Window
Ctrl+Alt+O           Toggle OBS mode
```
