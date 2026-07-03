# Troubleshooting

## Output window is not visible

Use:

- Output Tools tab → Rescue Output Window
- Output Tools tab → Reset Output Window

Hotkey:

```text
Ctrl+Alt+R
```

## OBS cannot see the output window

Confirm the window title:

```text
3DCP Perspective Console - Output
```

Then refresh or recreate the OBS Window Capture source.

## QR dependencies missing

Run:

```bash
./setup_venv_3dcp_console.sh
```

Then launch with:

```bash
./launch_3dcp_console_venv.sh
```

## Duplicate `.buttstore` files

The app archives duplicate-looking buttstores after startup and removes the temporary archive at clean shutdown.

Manual helper:

```bash
./archive_duplicate_buttstores.sh
```

## Acceptance check

Run:

```bash
./acceptance_3dcp_console.sh
```

## Health report

Run:

```bash
./health_report_3dcp_console.sh
```

Reports are written to:

```text
user_data/reports/
```
