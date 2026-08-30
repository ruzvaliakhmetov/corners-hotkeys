# encoding: utf-8
from __future__ import division, print_function, unicode_literals

import traceback

import objc
from AppKit import NSApplication, NSColor, NSEvent, NSMenuItem, NSTextField, NSTextView
from GlyphsApp import (
    CORNER,
    DRAWFOREGROUND,
    GLYPH_MENU,
    GSHandle,
    GSHint,
    GSNode,
    Glyphs,
)
from GlyphsApp.plugins import GeneralPlugin
from vanilla import Button, CheckBox, EditText, FloatingWindow, PopUpButton, TextBox

try:
    from AppKit import NSControlStateValueOff, NSControlStateValueOn
except Exception:
    NSControlStateValueOff = 0
    NSControlStateValueOn = 1

try:
    from AppKit import NSEventMaskKeyDown
except Exception:
    # NSEventTypeKeyDown is 10, and an event mask is 1 << eventType.
    NSEventMaskKeyDown = 1 << 10

try:
    from AppKit import (
        NSEventModifierFlagCapsLock,
        NSEventModifierFlagCommand,
        NSEventModifierFlagControl,
        NSEventModifierFlagFunction,
        NSEventModifierFlagOption,
        NSEventModifierFlagShift,
    )
except Exception:
    # Legacy NSEvent modifier masks.
    NSEventModifierFlagCapsLock = 1 << 16
    NSEventModifierFlagShift = 1 << 17
    NSEventModifierFlagControl = 1 << 18
    NSEventModifierFlagOption = 1 << 19
    NSEventModifierFlagCommand = 1 << 20
    NSEventModifierFlagFunction = 1 << 23


class CornerHotkeysG4(GeneralPlugin):
    """Fast keyboard workflow for corner components.

    Physical keys 1–5: add or replace the corresponding configured corner
    Physical key Q: mirror selected/attached corner horizontally
    Configurable key (default: §): cycle through corner alignment modes

    The plugin deliberately consumes a key event only when it can perform a
    corner action in an active Edit View. Otherwise Glyphs receives the event
    normally.
    """

    enabledDefaultsKey = "com.ruz.CornerHotkeysG4.enabled"
    alignmentShortcutDefaultsKey = "com.ruz.CornerHotkeysG4.alignmentShortcut"
    coloredHighlightsDefaultsKey = "com.ruz.CornerHotkeysG4.coloredHighlights"
    cornerDefaultsKeys = {
        1: "com.ruz.CornerHotkeysG4.corner1Name",
        2: "com.ruz.CornerHotkeysG4.corner2Name",
        3: "com.ruz.CornerHotkeysG4.corner3Name",
        4: "com.ruz.CornerHotkeysG4.corner4Name",
        5: "com.ruz.CornerHotkeysG4.corner5Name",
    }

    # macOS virtual key codes. These follow the physical key positions and
    # therefore keep working when the current input source is Russian, Swedish,
    # or another non-Latin layout.
    cornerKeyCodes = {
        18: 1,
        19: 2,
        20: 3,
        21: 4,
        23: 5,
    }
    keyCodeQ = 12
    keyCodeISOSection = 10

    # The three alignment modes shown for corner components in Glyphs 4:
    # left, centre, right.
    alignmentModes = (0, 2, 1)

    # Corner highlight colours for keys 1–5. The first colour matches
    # Glyphs’ standard corner-component blue; the others make each hotkey
    # assignment immediately distinguishable in Edit View.
    cornerColors = {
        1: (0xBC / 255.0, 0xDD / 255.0, 0xF0 / 255.0),
        2: (0xE1 / 255.0, 0xA0 / 255.0, 0xA0 / 255.0),
        3: (0x83 / 255.0, 0xEB / 255.0, 0x7B / 255.0),
        4: (0xD5 / 255.0, 0x7B / 255.0, 0xEB / 255.0),
        5: (0xEB / 255.0, 0xD2 / 255.0, 0x7B / 255.0),
    }

    @objc.python_method
    def settings(self):
        self.name = Glyphs.localize({"en": "Corner Hotkeys G4"})
        self._eventMonitor = None
        self._eventHandler = None
        self._drawCallback = None
        self._enabledMenuItem = None
        self._settingsMenuItem = None
        self._separatorMenuItem = None
        self._settingsWindow = None
        self._settingsCornerNames = []
        self._knownCornerNamesByFont = {}

    @objc.python_method
    def start(self):
        self._ensureDefaults()
        self._addMenuItems()
        self._installEventMonitor()
        self._installDrawCallback()
        try:
            self._observeCornerNames(Glyphs.font)
        except Exception:
            pass

    @objc.python_method
    def stop(self):
        self._removeEventMonitor()
        self._removeDrawCallback()
        self._removeMenuItems()
        self._closeSettingsWindow()

    @objc.python_method
    def __del__(self):
        try:
            self.stop()
        except Exception:
            pass

    # ---------------------------------------------------------------------
    # Defaults and menu

    @objc.python_method
    def _ensureDefaults(self):
        try:
            if Glyphs.defaults[self.enabledDefaultsKey] is None:
                Glyphs.defaults[self.enabledDefaultsKey] = True
            if Glyphs.defaults[self.alignmentShortcutDefaultsKey] is None:
                Glyphs.defaults[self.alignmentShortcutDefaultsKey] = "§"
            if Glyphs.defaults[self.coloredHighlightsDefaultsKey] is None:
                Glyphs.defaults[self.coloredHighlightsDefaultsKey] = False
        except Exception:
            pass

    @objc.python_method
    def _alignmentShortcut(self):
        try:
            value = Glyphs.defaults[self.alignmentShortcutDefaultsKey]
        except Exception:
            value = None
        value = str(value or "").strip()
        return value[0] if value else "§"

    @objc.python_method
    def _isEnabled(self):
        try:
            value = Glyphs.defaults[self.enabledDefaultsKey]
            return True if value is None else bool(value)
        except Exception:
            return True

    @objc.python_method
    def _setEnabled(self, enabled):
        try:
            Glyphs.defaults[self.enabledDefaultsKey] = bool(enabled)
        except Exception:
            pass
        self._updateMenuState()

    @objc.python_method
    def _coloredHighlightsEnabled(self):
        try:
            value = Glyphs.defaults[self.coloredHighlightsDefaultsKey]
            return False if value is None else bool(value)
        except Exception:
            return False

    @objc.python_method
    def _addMenuItems(self):
        if self._enabledMenuItem is not None:
            return
        try:
            self._separatorMenuItem = NSMenuItem.separatorItem()

            self._enabledMenuItem = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Corner Hotkeys G4 Enabled",
                self.toggleCornerHotkeys_,
                "",
            )
            self._enabledMenuItem.setTarget_(self)

            self._settingsMenuItem = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Corner Hotkeys G4 Settings…",
                self.openCornerHotkeysSettings_,
                "",
            )
            self._settingsMenuItem.setTarget_(self)

            Glyphs.menu[GLYPH_MENU].append(self._separatorMenuItem)
            Glyphs.menu[GLYPH_MENU].append(self._enabledMenuItem)
            Glyphs.menu[GLYPH_MENU].append(self._settingsMenuItem)
            self._updateMenuState()
        except Exception:
            print("Corner Hotkeys G4: could not add menu items")
            print(traceback.format_exc())

    @objc.python_method
    def _removeMenuItems(self):
        for item in (
            getattr(self, "_settingsMenuItem", None),
            getattr(self, "_enabledMenuItem", None),
            getattr(self, "_separatorMenuItem", None),
        ):
            if item is None:
                continue
            try:
                Glyphs.menu[GLYPH_MENU].remove(item)
            except Exception:
                pass
        self._settingsMenuItem = None
        self._enabledMenuItem = None
        self._separatorMenuItem = None

    @objc.python_method
    def _updateMenuState(self):
        item = getattr(self, "_enabledMenuItem", None)
        if item is None:
            return
        try:
            item.setState_(
                NSControlStateValueOn if self._isEnabled() else NSControlStateValueOff
            )
            item.setTitle_(
                "Corner Hotkeys G4 Enabled (1–5, Q, %s)" % self._alignmentShortcut()
            )
        except Exception:
            pass

    def toggleCornerHotkeys_(self, sender):
        self._setEnabled(not self._isEnabled())

    def openCornerHotkeysSettings_(self, sender):
        self._openSettingsWindow()

    def validateMenuItem_(self, menuItem):
        try:
            if menuItem == getattr(self, "_enabledMenuItem", None):
                self._updateMenuState()
        except Exception:
            pass
        return True

    # ---------------------------------------------------------------------
    # Settings window

    @objc.python_method
    def _openSettingsWindow(self):
        font = Glyphs.font
        self._observeCornerNames(font)
        names = self._availableCornerNames(font)
        self._settingsCornerNames = names

        # A vanilla Window cannot be reopened after it has been closed.
        # If Settings is already visible, just bring it forward; otherwise
        # discard the stale wrapper and create a fresh window below.
        window = getattr(self, "_settingsWindow", None)
        if window is not None:
            try:
                nsWindow = window.getNSWindow()
                if nsWindow is not None and nsWindow.isVisible():
                    try:
                        window.makeKey()
                    except Exception:
                        pass
                    return
            except Exception:
                pass
            self._settingsWindow = None

        if self._settingsWindow is None:
            self._settingsWindow = FloatingWindow(
                (390, 380),
                "Corner Hotkeys G4",
                autosaveName="com.ruz.CornerHotkeysG4.settingsWindow",
            )
            self._settingsWindow.intro = TextBox(
                (16, 14, -16, 34),
                "Choose the _corner.* glyph assigned to each number key.",
            )

            firstY = 58
            rowHeight = 37
            for slot in range(1, 6):
                y = firstY + (slot - 1) * rowHeight
                setattr(
                    self._settingsWindow,
                    "label%d" % slot,
                    TextBox((16, y + 4, 70, 20), "Key %d" % slot),
                )
                setattr(
                    self._settingsWindow,
                    "corner%d" % slot,
                    PopUpButton((82, y, -16, 25), []),
                )

            self._settingsWindow.alignmentLabel = TextBox(
                (16, 253, 130, 20), "Alignment mode key"
            )
            self._settingsWindow.alignmentShortcut = EditText(
                (150, 248, 52, 24), "§"
            )
            self._settingsWindow.alignmentHint = TextBox(
                (212, 253, -16, 18), "one character", sizeStyle="small"
            )

            self._settingsWindow.coloredHighlights = CheckBox(
                (16, 292, -16, 20),
                "Colored corner highlights",
                value=False,
            )

            self._settingsWindow.save = Button(
                (-94, -40, 78, 24), "Save", callback=self._saveSettings
            )
            self._settingsWindow.status = TextBox((16, -36, -110, 18), "", sizeStyle="small")

        displayNames = ["None"] + names
        for slot in range(1, 6):
            popup = getattr(self._settingsWindow, "corner%d" % slot)
            popup.setItems(displayNames)

        self._settingsWindow.alignmentShortcut.set(self._alignmentShortcut())
        self._settingsWindow.coloredHighlights.set(
            self._coloredHighlightsEnabled()
        )

        for slot in range(1, 6):
            name = self._resolvedCornerName(slot, font)
            popup = getattr(self._settingsWindow, "corner%d" % slot)
            popup.set(self._indexForName(name, names))

        self._settingsWindow.save.enable(True)
        if names:
            self._settingsWindow.status.set(
                "Q mirrors; %s cycles alignment modes." % self._alignmentShortcut()
            )
        else:
            self._settingsWindow.status.set(
                "No _corner.* glyphs found yet. New corners will use the first free key."
            )

        self._settingsWindow.open()
        try:
            self._settingsWindow.makeKey()
        except Exception:
            pass

    @objc.python_method
    def _closeSettingsWindow(self):
        window = getattr(self, "_settingsWindow", None)
        if window is None:
            return
        try:
            window.close()
        except Exception:
            pass
        self._settingsWindow = None

    @objc.python_method
    def _saveSettings(self, sender):
        names = list(getattr(self, "_settingsCornerNames", []) or [])
        try:
            saved = []
            assigned = set()
            for slot in range(1, 6):
                popup = getattr(self._settingsWindow, "corner%d" % slot)
                index = int(popup.get())
                name = names[index - 1] if index > 0 and index <= len(names) else ""
                # Keep assignments unique. If the same corner is selected for
                # more than one key, the lower-numbered key wins.
                if name and name in assigned:
                    name = ""
                if name:
                    assigned.add(name)
                Glyphs.defaults[self.cornerDefaultsKeys[slot]] = name
                saved.append("%d → %s" % (slot, name or "None"))

            shortcut = self._normalisedShortcut(
                self._settingsWindow.alignmentShortcut.get()
            )
            if shortcut.casefold() in ("1", "2", "3", "4", "5", "q"):
                self._settingsWindow.status.set(
                    "Choose a key other than 1–5 or Q."
                )
                return
            Glyphs.defaults[self.alignmentShortcutDefaultsKey] = shortcut
            Glyphs.defaults[self.coloredHighlightsDefaultsKey] = bool(
                self._settingsWindow.coloredHighlights.get()
            )
            self._updateMenuState()

            saved.append("alignment → %s" % shortcut)
            saved.append(
                "colors → %s"
                % ("on" if self._coloredHighlightsEnabled() else "off")
            )
            self._settingsWindow.status.set("Saved: " + ", ".join(saved))
            window = self._settingsWindow
            self._settingsWindow = None
            window.close()
        except Exception:
            print("Corner Hotkeys G4: could not save settings")
            print(traceback.format_exc())
            Glyphs.showMacroWindow()

    @objc.python_method
    def _normalisedShortcut(self, value):
        value = str(value or "").strip()
        return value[0] if value else "§"

    @objc.python_method
    def _indexForName(self, name, names):
        if not name:
            return 0
        try:
            return names.index(name) + 1
        except Exception:
            return 0

    # ---------------------------------------------------------------------
    # Event monitor

    @objc.python_method
    def _installEventMonitor(self):
        if self._eventMonitor is not None:
            return
        try:
            # Keep the callable alive for as long as the monitor exists.
            self._eventHandler = self._handleKeyEvent
            self._eventMonitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
                NSEventMaskKeyDown,
                self._eventHandler,
            )
        except Exception:
            print("Corner Hotkeys G4: could not install keyboard event monitor")
            print(traceback.format_exc())
            self._eventMonitor = None
            self._eventHandler = None

    @objc.python_method
    def _removeEventMonitor(self):
        monitor = getattr(self, "_eventMonitor", None)
        if monitor is not None:
            try:
                NSEvent.removeMonitor_(monitor)
            except Exception:
                pass
        self._eventMonitor = None
        self._eventHandler = None

    # ---------------------------------------------------------------------
    # Coloured corner highlights

    @objc.python_method
    def _installDrawCallback(self):
        if self._drawCallback is not None:
            return
        try:
            # Keep the exact bound-method object alive so removeCallback gets
            # the same callable later.
            self._drawCallback = self._drawCornerHighlights
            Glyphs.addCallback(self._drawCallback, DRAWFOREGROUND)
        except Exception:
            print("Corner Hotkeys G4: could not install drawing callback")
            print(traceback.format_exc())
            self._drawCallback = None

    @objc.python_method
    def _removeDrawCallback(self):
        callback = getattr(self, "_drawCallback", None)
        if callback is not None:
            try:
                Glyphs.removeCallback(callback, DRAWFOREGROUND)
            except Exception:
                pass
        self._drawCallback = None

    @objc.python_method
    def _drawCornerHighlights(self, layer, info):
        """Overlay assigned corner components with their hotkey colour.

        Glyphs computes the fully transformed corner shape while drawing and
        exposes it as hint.tempData["cornerHighlightPath"]. Reusing that path
        keeps stretching, mirroring and alignment identical to Glyphs’ own
        corner rendering.
        """
        try:
            if layer is None:
                return

            font = getattr(layer, "font", None)
            if callable(font):
                font = font()
            if font is None:
                glyph = getattr(layer, "parent", None)
                font = getattr(glyph, "parent", None) if glyph is not None else None
            if font is None:
                font = Glyphs.font
            if font is None:
                return

            # The draw callback also acts as a lightweight observer for newly
            # created _corner.* glyphs. This runs even when coloured highlights
            # are disabled, because automatic hotkey assignment is independent
            # from the visual highlight option.
            self._observeCornerNames(font)

            if not self._isEnabled() or not self._coloredHighlightsEnabled():
                return

            # Resolve current assignments every draw so Settings changes are
            # reflected immediately. If the same corner is assigned twice, the
            # lower-numbered key wins because the hint itself stores only name.
            slotForName = {}
            for slot in range(1, 6):
                name = self._resolvedCornerName(slot, font)
                if name and name not in slotForName:
                    slotForName[name] = slot

            try:
                hints = list(layer.hints or [])
            except Exception:
                hints = []
            if not hints:
                return

            # Accessing the layer path asks Glyphs to calculate corner highlight
            # paths when they are not cached yet.
            try:
                _ = layer.bezierPath
            except Exception:
                pass

            for hint in hints:
                if not self._isCornerHint(hint):
                    continue
                try:
                    name = str(hint.name or "")
                except Exception:
                    continue
                slot = slotForName.get(name)
                if slot is None:
                    continue

                try:
                    tempData = hint.tempData
                    path = tempData.get("cornerHighlightPath") if tempData else None
                except Exception:
                    path = None
                if path is None:
                    continue

                rgb = self.cornerColors.get(slot)
                if rgb is None:
                    continue
                try:
                    lineColor = NSColor.colorWithSRGBRed_green_blue_alpha_(
                        rgb[0], rgb[1], rgb[2], 1.0
                    )
                    auraColor = NSColor.colorWithSRGBRed_green_blue_alpha_(
                        rgb[0], rgb[1], rgb[2], 0.62
                    )
                except Exception:
                    lineColor = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                        rgb[0], rgb[1], rgb[2], 1.0
                    )
                    auraColor = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                        rgb[0], rgb[1], rgb[2], 0.62
                    )

                # cornerHighlightPath is the open centreline Glyphs uses for
                # its own blue corner aura. Draw a broad translucent stroke on
                # top of that system highlight first, then the crisp 1 pt
                # centreline. The broad overlay is deliberately a little more
                # opaque than Glyphs' native glow so the underlying blue does
                # not dominate the assigned hotkey colour.
                try:
                    scale = float((info or {}).get("Scale", 1.0) or 1.0)
                except Exception:
                    scale = 1.0
                scale = max(scale, 0.000001)

                try:
                    auraPath = path.copy()
                except Exception:
                    auraPath = path
                try:
                    auraPath.setLineCapStyle_(1)  # NSRoundLineCapStyle
                except Exception:
                    pass
                auraPath.setLineWidth_(9.0 / scale)
                auraColor.set()
                auraPath.stroke()

                try:
                    linePath = path.copy()
                except Exception:
                    linePath = path
                try:
                    linePath.setLineCapStyle_(1)
                except Exception:
                    pass
                linePath.setLineWidth_(1.0 / scale)
                lineColor.set()
                linePath.stroke()
        except Exception:
            # Drawing callbacks must never break the Edit View.
            print("Corner Hotkeys G4: corner highlight drawing error")
            print(traceback.format_exc())

    @objc.python_method
    def _handleKeyEvent(self, event):
        try:
            if not self._isEnabled():
                return event
            if event is None:
                return event
            try:
                if event.isARepeat():
                    return event
            except Exception:
                pass

            action = self._actionForEvent(event)
            if action is None:
                return event

            font = Glyphs.font
            if not self._isActiveEditWindow(font):
                return event
            if self._textInputHasFocus():
                return event

            # Detect newly created _corner.* glyphs before resolving a number
            # key, so a fresh corner can immediately occupy the first free slot.
            self._observeCornerNames(font)

            layer = self._currentLayer(font)
            if layer is None:
                return event

            if isinstance(action, int):
                performed = self._applyCornerSlot(layer, font, action)
            elif action == "alignment":
                performed = self._cycleSelectedCornerAlignment(layer)
            else:
                performed = self._mirrorSelectedCorners(layer)

            # Returning None consumes the event. We do that only when a corner
            # action was actually performed (or settings were opened for a
            # valid selection), so normal Glyphs typing and shortcuts survive.
            return None if performed else event

        except Exception:
            print("Corner Hotkeys G4: keyboard handling error")
            print(traceback.format_exc())
            Glyphs.showMacroWindow()
            return event

    @objc.python_method
    def _actionForEvent(self, event):
        try:
            flags = int(event.modifierFlags())
        except Exception:
            flags = 0

        forbidden = (
            int(NSEventModifierFlagCommand)
            | int(NSEventModifierFlagControl)
            | int(NSEventModifierFlagOption)
            | int(NSEventModifierFlagFunction)
        )
        if flags & forbidden:
            return None

        try:
            keyCode = int(event.keyCode())
        except Exception:
            keyCode = -1

        shiftDown = bool(flags & int(NSEventModifierFlagShift))

        if not shiftDown and keyCode in self.cornerKeyCodes:
            return self.cornerKeyCodes[keyCode]
        if keyCode == self.keyCodeQ:
            return "mirror"

        alignmentShortcut = self._alignmentShortcut()
        # The Swedish § key is the ISO key immediately to the left of 1.
        # Matching its physical key code keeps the default useful even if the
        # input source changes temporarily.
        if (
            alignmentShortcut == "§"
            and not shiftDown
            and keyCode == self.keyCodeISOSection
        ):
            return "alignment"

        # Fallback for unusual keyboards / PyObjC builds.
        try:
            chars = str(event.charactersIgnoringModifiers() or "")
        except Exception:
            chars = ""
        try:
            actualChars = str(event.characters() or "")
        except Exception:
            actualChars = chars

        lowerChars = chars.casefold()
        if not shiftDown and lowerChars in ("1", "2", "3", "4", "5"):
            return int(lowerChars)
        if lowerChars == "q":
            return "mirror"
        if self._shortcutMatchesCharacters(
            alignmentShortcut, actualChars, chars
        ):
            return "alignment"
        return None

    @objc.python_method
    def _shortcutMatchesCharacters(self, shortcut, actualChars, unmodifiedChars):
        shortcut = self._normalisedShortcut(shortcut)
        candidates = [str(actualChars or ""), str(unmodifiedChars or "")]
        for candidate in candidates:
            if not candidate:
                continue
            if candidate == shortcut:
                return True
            # Letter shortcuts should remain convenient with Caps Lock or
            # Shift, while punctuation remains an exact match.
            if shortcut.isalpha() and candidate.casefold() == shortcut.casefold():
                return True
        return False

    @objc.python_method
    def _isActiveEditWindow(self, font):
        if font is None:
            return False
        try:
            if font.currentTab is None:
                return False
        except Exception:
            return False

        # Do not fire while the settings window, Macro Panel, Font Info, etc.
        # is the key window. The current font document itself must be active.
        try:
            keyWindow = NSApplication.sharedApplication().keyWindow()
            document = font.parent
            windowController = document.windowController()
            documentWindow = windowController.window()
            if keyWindow is not None and documentWindow is not None and keyWindow != documentWindow:
                return False
        except Exception:
            # If a Glyphs build does not expose this chain, the selection tests
            # below still keep the monitor conservative.
            pass
        return True

    @objc.python_method
    def _textInputHasFocus(self):
        """Return True while a text-editing control owns keyboard focus.

        Glyphs keeps the glyph document window active while the user edits
        fields in the right-hand palette. A key-window check alone therefore
        cannot distinguish canvas editing from typing in those controls. The
        active field editor is an NSTextView, so number keys and Q must pass
        through untouched whenever it is first responder.
        """
        try:
            keyWindow = NSApplication.sharedApplication().keyWindow()
            if keyWindow is None:
                return False
            responder = keyWindow.firstResponder()
            if responder is None:
                return False

            for textClass in (NSTextView, NSTextField):
                try:
                    if responder.isKindOfClass_(textClass):
                        return True
                except Exception:
                    try:
                        if isinstance(responder, textClass):
                            return True
                    except Exception:
                        pass

            # A field editor is normally an NSTextView, but retain this
            # selector-based fallback for older AppKit/PyObjC combinations.
            try:
                value = responder.isFieldEditor()
                if bool(value):
                    return True
            except Exception:
                pass
        except Exception:
            # Failing closed here would disable the plugin on unusual builds;
            # instead leave the remaining conservative selection checks active.
            pass
        return False

    @objc.python_method
    def _currentLayer(self, font):
        if font is None:
            return None
        try:
            layers = font.selectedLayers
            if layers and len(layers) > 0:
                return layers[0]
        except Exception:
            pass
        try:
            tab = font.currentTab
            activeLayer = tab.activeLayer()
            if activeLayer is not None:
                return activeLayer
        except Exception:
            pass
        return None

    # ---------------------------------------------------------------------
    # Corner actions

    @objc.python_method
    def _applyCornerSlot(self, layer, font, slot):
        selectedHints, selectedNodes = self._selectedCornersAndNodes(layer)
        if not selectedHints and not selectedNodes:
            return False

        cornerName = self._resolvedCornerName(slot, font)
        if not cornerName:
            self._notify(
                "No corner assigned",
                "Open Glyph → Corner Hotkeys G4 Settings… and choose the _corner.* glyph for key %d." % slot,
            )
            self._openSettingsWindow()
            return True

        glyph = getattr(layer, "parent", None)
        if glyph is not None:
            try:
                glyph.beginUndo()
            except Exception:
                pass

        changed = False
        try:
            handledHintIds = set()

            # If the corner itself is selected, replacing its name preserves
            # scale, alignment, stem direction, and all other settings.
            for hint in selectedHints:
                try:
                    hint.name = cornerName
                    handledHintIds.add(id(hint))
                    changed = True
                except Exception:
                    pass

            # Selected nodes either update an attached corner or receive a new
            # one. Multiple selected nodes are supported in one undo step.
            for node in selectedNodes:
                attached = self._cornerHintsAttachedToNode(layer, node)
                attached = [h for h in attached if id(h) not in handledHintIds]
                if attached:
                    for hint in attached:
                        try:
                            hint.name = cornerName
                            handledHintIds.add(id(hint))
                            changed = True
                        except Exception:
                            pass
                else:
                    hint = self._newCornerHintForNode(node, cornerName)
                    if hint is not None:
                        layer.hints.append(hint)
                        try:
                            hint.updateIndexes()
                        except Exception:
                            pass
                        changed = True

            if changed:
                self._redraw()
            return changed
        finally:
            if glyph is not None:
                try:
                    glyph.endUndo()
                except Exception:
                    pass

    @objc.python_method
    def _mirrorSelectedCorners(self, layer):
        corners = self._selectedOrAttachedCorners(layer)

        if not corners:
            return False

        glyph = getattr(layer, "parent", None)
        if glyph is not None:
            try:
                glyph.beginUndo()
            except Exception:
                pass

        changed = False
        try:
            for hint in corners:
                try:
                    scale = hint.scale
                    if callable(scale):
                        scale = scale()
                    x = float(scale[0])
                    y = float(scale[1])
                    # Avoid an unusable -0.0 scale if a malformed corner happens
                    # to have zero horizontal scale.
                    newX = -x if abs(x) > 0.000001 else -1.0
                    try:
                        hint.scale = (newX, y)
                    except Exception:
                        hint.setScale_((newX, y))
                    changed = True
                except Exception:
                    print("Corner Hotkeys G4: could not mirror corner %r" % hint)
                    print(traceback.format_exc())

            if changed:
                self._redraw()
            return changed
        finally:
            if glyph is not None:
                try:
                    glyph.endUndo()
                except Exception:
                    pass

    @objc.python_method
    def _cycleSelectedCornerAlignment(self, layer):
        corners = self._selectedOrAttachedCorners(layer)
        if not corners:
            return False

        glyph = getattr(layer, "parent", None)
        if glyph is not None:
            try:
                glyph.beginUndo()
            except Exception:
                pass

        changed = False
        try:
            for hint in corners:
                try:
                    options = hint.options
                    if callable(options):
                        options = options()
                    currentMode = int(options or 0)

                    try:
                        index = self.alignmentModes.index(currentMode)
                        nextMode = self.alignmentModes[
                            (index + 1) % len(self.alignmentModes)
                        ]
                    except ValueError:
                        nextMode = self.alignmentModes[0]

                    # GSHint.options stores the corner alignment directly:
                    # 0 = left, 2 = centre, 1 = right. Calling the Objective-C
                    # setter first proved more reliable for immediate UI updates
                    # in Glyphs 4 than mutating guessed option bit flags.
                    try:
                        hint.setOptions_(int(nextMode))
                    except Exception:
                        hint.options = int(nextMode)
                    changed = True
                except Exception:
                    print(
                        "Corner Hotkeys G4: could not change alignment for corner %r"
                        % hint
                    )
                    print(traceback.format_exc())

            if changed:
                self._redraw()
            return changed
        finally:
            if glyph is not None:
                try:
                    glyph.endUndo()
                except Exception:
                    pass

    @objc.python_method
    def _selectedOrAttachedCorners(self, layer):
        selectedHints, selectedNodes = self._selectedCornersAndNodes(layer)
        corners = list(selectedHints)
        for node in selectedNodes:
            corners.extend(self._cornerHintsAttachedToNode(layer, node))
        return self._dedupeObjects(corners)

    @objc.python_method
    def _selectedCornersAndNodes(self, layer):
        try:
            selection = list(layer.selection or [])
        except Exception:
            selection = []

        hints = []
        nodes = []
        for item in selection:
            if self._isCornerHint(item):
                hints.append(item)
            elif isinstance(item, (GSNode, GSHandle)):
                nodes.append(item)

        return self._dedupeObjects(hints), self._dedupeObjects(nodes)

    @objc.python_method
    def _isCornerHint(self, item):
        if not isinstance(item, GSHint):
            return False
        try:
            return int(item.type) == int(CORNER)
        except Exception:
            try:
                value = item.isCorner
                return bool(value() if callable(value) else value)
            except Exception:
                return False

    @objc.python_method
    def _cornerHintsAttachedToNode(self, layer, node):
        result = []
        try:
            hints = list(layer.hints or [])
        except Exception:
            hints = []
        for hint in hints:
            if not self._isCornerHint(hint):
                continue
            if self._hintMatchesNode(hint, node):
                result.append(hint)
        return result

    @objc.python_method
    def _hintMatchesNode(self, hint, node):
        try:
            if hint.originNode == node:
                return True
        except Exception:
            pass

        if isinstance(node, GSHandle):
            try:
                hintIndex = hint.originIndex
                nodeIndex = node.object()
                sameIndex = hintIndex == nodeIndex
                if not sameIndex and hasattr(hintIndex, "isEqual_"):
                    sameIndex = bool(hintIndex.isEqual_(nodeIndex))
                if sameIndex and int(hint.stem) == int(node.flag()):
                    return True
            except Exception:
                pass
        return False

    @objc.python_method
    def _newCornerHintForNode(self, node, cornerName):
        try:
            hint = GSHint()
            hint.type = CORNER
            hint.name = cornerName

            if isinstance(node, GSHandle):
                # Current Glyphs API: intersection/extra nodes are represented
                # by an index path plus a direction flag.
                hint.originIndex = node.object()
                hint.stem = node.flag()
            else:
                hint.originNode = node
            return hint
        except Exception:
            print("Corner Hotkeys G4: could not create corner")
            print(traceback.format_exc())
            return None

    # ---------------------------------------------------------------------
    # Corner name resolution and automatic assignment

    @objc.python_method
    def _availableCornerNames(self, font):
        if font is None:
            return []
        names = []
        try:
            for glyph in font.glyphs:
                name = getattr(glyph, "name", None)
                if name and str(name).startswith("_corner."):
                    names.append(str(name))
        except Exception:
            pass
        return names

    @objc.python_method
    def _rawCornerAssignment(self, slot):
        key = self.cornerDefaultsKeys.get(int(slot))
        if not key:
            return None
        try:
            value = Glyphs.defaults[key]
        except Exception:
            value = None
        if value is None:
            return None
        return str(value or "").strip()

    @objc.python_method
    def _initialiseCornerAssignments(self, font, names=None):
        """Migrate the old zero-config behaviour without repeating corners.

        Older versions left untouched slots absent from defaults and resolved
        them dynamically. On first encounter, assign existing corner glyphs to
        those uninitialised slots once, in font order, then mark the remaining
        slots as empty. A deliberately saved None is stored as an empty string
        and is therefore not re-filled by this migration on later launches.
        """
        if font is None:
            return
        if names is None:
            names = self._availableCornerNames(font)

        raw = {slot: self._rawCornerAssignment(slot) for slot in range(1, 6)}

        # Older builds could save the same corner into several slots when the
        # font had fewer than five _corner.* glyphs. Collapse those duplicates
        # once so the extra keys become genuinely free.
        assigned = set()
        for slot in range(1, 6):
            value = raw[slot]
            if value and value in assigned:
                raw[slot] = ""
                try:
                    Glyphs.defaults[self.cornerDefaultsKeys[slot]] = ""
                except Exception:
                    pass
            elif value:
                assigned.add(value)

        if not any(value is None for value in raw.values()):
            return

        remaining = [name for name in names if name not in assigned]

        for slot in range(1, 6):
            if raw[slot] is not None:
                continue
            name = remaining.pop(0) if remaining else ""
            if name:
                assigned.add(name)
            try:
                Glyphs.defaults[self.cornerDefaultsKeys[slot]] = name
            except Exception:
                pass

    @objc.python_method
    def _autoAssignNewCornerNames(self, names, font):
        if not names or font is None:
            return

        for name in names:
            # Do nothing if this corner is already assigned somewhere.
            alreadyAssigned = False
            for slot in range(1, 6):
                if self._rawCornerAssignment(slot) == name:
                    alreadyAssigned = True
                    break
            if alreadyAssigned:
                continue

            # Empty / None means the key is currently free. Selecting None in
            # Settings intentionally returns a key to this free pool.
            freeSlot = None
            for slot in range(1, 6):
                value = self._rawCornerAssignment(slot)
                if value is None or value == "":
                    freeSlot = slot
                    break
            if freeSlot is None:
                break

            try:
                Glyphs.defaults[self.cornerDefaultsKeys[freeSlot]] = name
            except Exception:
                pass

    @objc.python_method
    def _observeCornerNames(self, font):
        """Assign only genuinely new corners after the initial snapshot."""
        if font is None:
            return

        names = self._availableCornerNames(font)
        self._initialiseCornerAssignments(font, names)

        try:
            marker = hash(font)
        except Exception:
            marker = id(font)
        previous = self._knownCornerNamesByFont.get(marker)
        current = set(names)
        self._knownCornerNamesByFont[marker] = current

        if previous is None:
            return

        added = [name for name in names if name not in previous]
        if added:
            self._autoAssignNewCornerNames(added, font)

    @objc.python_method
    def _resolvedCornerName(self, slot, font):
        names = self._availableCornerNames(font)
        if not names:
            return None

        configured = self._rawCornerAssignment(slot)
        if configured and configured in names:
            return configured
        return None

    # ---------------------------------------------------------------------

    @objc.python_method
    def _dedupeObjects(self, objects):
        result = []
        seen = set()
        for obj in objects:
            marker = id(obj)
            if marker in seen:
                continue
            seen.add(marker)
            result.append(obj)
        return result

    @objc.python_method
    def _redraw(self):
        try:
            Glyphs.redraw()
        except Exception:
            pass
        try:
            font = Glyphs.font
            if font is not None and font.currentTab is not None:
                font.currentTab.redraw()
        except Exception:
            pass

    @objc.python_method
    def _notify(self, title, message):
        try:
            Glyphs.showNotification(title, message)
        except Exception:
            print("%s: %s" % (title, message))
