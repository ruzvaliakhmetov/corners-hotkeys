# Corner Hotkeys

Temporary workflow helper for Glyphs 3.

- Select one or more nodes and press the physical **1** key to add or replace the first configured `_corner.*` component.
- Press the physical **2** key for the second configured corner.
- Select a corner component (or its host node) and press the physical **Q** key to mirror it horizontally.
- Enable or disable the shortcuts in **Glyph → Corner Hotkeys Enabled (1, 2, Q)**.
- Choose the two components in **Glyph → Corner Hotkeys Settings…**.

If no explicit settings are saved, the first two `_corner.*` glyphs in font order are used automatically.

The event monitor only consumes a key when an applicable node or corner is selected in an active Edit View. It leaves normal typing and Glyphs shortcuts alone in all other contexts.
