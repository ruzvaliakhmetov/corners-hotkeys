# encoding: utf-8
from __future__ import division, print_function, unicode_literals

import traceback

import objc
from AppKit import NSApplication, NSEvent, NSMenuItem, NSTextField, NSTextView
from GlyphsApp import (
    CORNER,
    GLYPH_MENU,
    GSHandle,
    GSHint,
    GSNode,
    Glyphs,
)
from GlyphsApp.plugins import GeneralPlugin
from vanilla import Button, EditText, FloatingWindow, PopUpButton, TextBox

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

    @objc.python_method
    def settings(self):
        self.name = Glyphs.localize({"en": "Corner Hotkeys G4"})
        self._eventMonitor = None
        self._eventHandler = None
        self._enabledMenuItem = None
        self._settingsMenuItem = None
        self._separatorMenuItem = None
        self._settingsWindow = None
        self._settingsCornerNames = []

    @objc.python_method
    def start(self):
        self._ensureDefaults()
        self._addMenuItems()
        self._installEventMonitor()

    @objc.python_method
    def stop(self):
        self._removeEventMonitor()
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
        names = self._availableCornerNames(font)
        self._settingsCornerNames = names

        if self._settingsWindow is None:
            self._settingsWindow = FloatingWindow(
                (390, 345),
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

            self._settingsWindow.save = Button(
                (-94, -40, 78, 24), "Save", callback=self._saveSettings
            )
            self._settingsWindow.status = TextBox((16, -36, -110, 18), "", sizeStyle="small")

        displayNames = names if names else ["No _corner.* glyphs found"]
        for slot in range(1, 6):
            popup = getattr(self._settingsWindow, "corner%d" % slot)
            popup.setItems(displayNames)

        self._settingsWindow.alignmentShortcut.set(self._alignmentShortcut())

        if names:
            for slot in range(1, 6):
                name = self._resolvedCornerName(slot, font)
                popup = getattr(self._settingsWindow, "corner%d" % slot)
                popup.set(self._indexForName(name, names, slot - 1))
            self._settingsWindow.save.enable(True)
            self._settingsWindow.status.set(
                "Q mirrors; %s cycles alignment modes." % self._alignmentShortcut()
            )
        else:
            for slot in range(1, 6):
                getattr(self._settingsWindow, "corner%d" % slot).set(0)
            self._settingsWindow.save.enable(True)
            self._settingsWindow.status.set(
                "No _corner.* glyphs found; the shortcut can still be saved."
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
            if names:
                for slot in range(1, 6):
                    popup = getattr(self._settingsWindow, "corner%d" % slot)
                    index = int(popup.get())
                    name = names[index]
                    Glyphs.defaults[self.cornerDefaultsKeys[slot]] = name
                    saved.append("%d → %s" % (slot, name))

            shortcut = self._normalisedShortcut(
                self._settingsWindow.alignmentShortcut.get()
            )
            if shortcut.casefold() in ("1", "2", "3", "4", "5", "q"):
                self._settingsWindow.status.set(
                    "Choose a key other than 1–5 or Q."
                )
                return
            Glyphs.defaults[self.alignmentShortcutDefaultsKey] = shortcut
            self._updateMenuState()

            saved.append("alignment → %s" % shortcut)
            self._settingsWindow.status.set("Saved: " + ", ".join(saved))
            self._settingsWindow.close()
        except Exception:
            print("Corner Hotkeys G4: could not save settings")
            print(traceback.format_exc())
            Glyphs.showMacroWindow()

    @objc.python_method
    def _normalisedShortcut(self, value):
        value = str(value or "").strip()
        return value[0] if value else "§"

    @objc.python_method
    def _indexForName(self, name, names, fallbackIndex):
        try:
            return names.index(name)
        except Exception:
            if not names:
                return 0
            return min(max(int(fallbackIndex), 0), len(names) - 1)

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
    # Corner name resolution

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
    def _resolvedCornerName(self, slot, font):
        names = self._availableCornerNames(font)
        if not names:
            return None

        slot = int(slot)
        key = self.cornerDefaultsKeys.get(slot)
        configured = None
        try:
            configured = Glyphs.defaults[key] if key else None
        except Exception:
            pass
        if configured in names:
            return configured

        # Zero-configuration behaviour: the first five _corner.* glyphs in
        # font order map to keys 1–5. If fewer exist, the first one is used.
        index = slot - 1
        if 0 <= index < len(names):
            return names[index]
        return names[0]

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
