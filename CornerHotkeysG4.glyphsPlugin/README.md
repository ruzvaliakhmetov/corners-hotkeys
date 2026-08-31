# Corner Hotkeys G4

A Glyphs 4 plugin for working with corner components using keyboard shortcuts.

- **1–5** — insert or replace configured corner components
- **Q** — mirror the selected corner horizontally
- **§** — cycle through alignment modes

Corner assignments and the alignment shortcut can be changed in **Glyph → Corner Hotkeys G4 Settings…**. Each number-key dropdown includes **None**. New `_corner.*` glyphs are automatically assigned to the first free number key, while unused keys remain unassigned instead of repeating existing corners.

For saved Glyphs files, number-key assignments are remembered **per file path**. The plugin keeps profiles for the **99 most recently used files**, so switching between projects restores the corresponding corner assignments automatically. Moving or renaming a file gives it a new path and therefore a new assignment profile.

The shortcuts can be enabled or disabled from the Glyph menu.

Coloured corner highlights are optional and **off by default**. Enable **Colored corner highlights** in Settings to use them.

## Corner colours

When **Colored corner highlights** is enabled, corner components assigned to number keys are colour-coded in Edit View, including both the centreline and the 9 px corner aura:

- **1** — `#bcddf0`
- **2** — `#e1a0a0`
- **3** — `#83eb7b`
- **4** — `#d57beb`
- **5** — `#ebd27b`
