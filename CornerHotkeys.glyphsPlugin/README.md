# Corner Hotkeys

Temporary workflow helper for Glyphs 3.

- Select one or more nodes and press a physical number key from **1** to **5** to add or replace its configured `_corner.*` component.
- Select a corner component (or its host node) and press the physical **Q** key to mirror it horizontally.
- Enable or disable the shortcuts in **Glyph → Corner Hotkeys Enabled (1–5, Q)**.
- Assign a corner component to each number key with five dropdown menus in **Glyph → Corner Hotkeys Settings…**.

If no explicit settings are saved, the first five `_corner.*` glyphs in font order are assigned automatically. When fewer than five corner glyphs exist, unfilled slots fall back to the first one.

The event monitor only consumes a key when an applicable node or corner is selected on the glyph editing canvas. It explicitly ignores text fields and field editors, including controls in the right-hand palette, so normal typing and Glyphs shortcuts remain untouched.
