# OBS Setup Guide

## Recommended capture method

Use OBS Window Capture and select:

```text
3DCP Perspective Console - Output
```

The output title is stable and does not include the app version.

## Recommended app steps

1. Launch the app.
2. Confirm the output window is visible.
3. In OBS, add or refresh Window Capture.
4. Capture `3DCP Perspective Console - Output`.
5. Use the Output Tools tab only after you confirm the window is visible.

## Output Tools tab

Controls:

- Always on top
- Borderless OBS mode
- Apply OBS Mode
- Normal Output
- Bring Output Front
- Rescue Output Window
- Reset Output Window
- Save Output Settings

## Safe recovery

If the output is not visible:

1. Open the Output Tools tab.
2. Press **Rescue Output Window**.
3. Press **Reset Output Window** if needed.
4. Re-select the window in OBS if OBS still holds an old capture target.

Hotkey:

```text
Ctrl+Alt+R
```

## Notes for KDE / KWin / Kubuntu

On some X11/Wayland setups, a borderless window can exist without visibly mapping. The app starts in normal framed mode first to avoid this. Enable Borderless OBS mode only after the output window is visible.
