# encoding: utf-8
from __future__ import division, print_function, unicode_literals

import traceback

import objc
from AppKit import NSApplication, NSEvent, NSMenuItem
from GlyphsApp import (
    CORNER,
    GLYPH_MENU,
    GSHandle,
    GSHint,
    GSNode,
    Glyphs,
)
from GlyphsApp.plugins import GeneralPlugin
from vanilla import Button, FloatingWindow, PopUpButton, TextBox

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


class CornerHotkeys(GeneralPlugin):
    """Fast, temporary keyboard workflow for two corner components.

    Physical key 1: add/replace Corner 1
    Physical key 2: add/replace Corner 2
    Physical key Q: mirror selected/attached corner horizontally

    The plugin deliberately consumes a key event only when it can perform a
    corner action in an active Edit View. Otherwise Glyphs receives the event
    normally.
    """

    enabledDefaultsKey = "com.ruz.CornerHotkeys.enabled"
    corner1DefaultsKey = "com.ruz.CornerHotkeys.corner1Name"
    corner2DefaultsKey = "com.ruz.CornerHotkeys.corner2Name"

    # macOS virtual key codes. These follow the physical key positions and
    # therefore keep working when the current input source is Russian, Swedish,
    # or another non-Latin layout.
    keyCode1 = 18
    keyCode2 = 19
    keyCodeQ = 12

    @objc.python_method
    def settings(self):
        self.name = Glyphs.localize({"en": "Corner Hotkeys"})
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
        except Exception:
            pass

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
                "Corner Hotkeys Enabled (1, 2, Q)",
                self.toggleCornerHotkeys_,
                "",
            )
            self._enabledMenuItem.setTarget_(self)

            self._settingsMenuItem = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Corner Hotkeys Settings…",
                self.openCornerHotkeysSettings_,
                "",
            )
            self._settingsMenuItem.setTarget_(self)

            Glyphs.menu[GLYPH_MENU].append(self._separatorMenuItem)
            Glyphs.menu[GLYPH_MENU].append(self._enabledMenuItem)
            Glyphs.menu[GLYPH_MENU].append(self._settingsMenuItem)
            self._updateMenuState()
        except Exception:
            print("Corner Hotkeys: could not add menu items")
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
                (390, 174),
                "Corner Hotkeys",
                autosaveName="com.ruz.CornerHotkeys.settingsWindow",
            )
            self._settingsWindow.intro = TextBox(
                (16, 14, -16, 34),
                "Choose the two _corner.* glyphs assigned to the physical 1 and 2 keys.",
            )
            self._settingsWindow.label1 = TextBox((16, 62, 70, 20), "Key 1")
            self._settingsWindow.corner1 = PopUpButton((82, 58, -16, 25), [])
            self._settingsWindow.label2 = TextBox((16, 99, 70, 20), "Key 2")
            self._settingsWindow.corner2 = PopUpButton((82, 95, -16, 25), [])
            self._settingsWindow.save = Button(
                (-94, -40, 78, 24), "Save", callback=self._saveSettings
            )
            self._settingsWindow.status = TextBox((16, -36, -110, 18), "", sizeStyle="small")

        displayNames = names if names else ["No _corner.* glyphs found"]
        self._settingsWindow.corner1.setItems(displayNames)
        self._settingsWindow.corner2.setItems(displayNames)

        if names:
            name1 = self._resolvedCornerName(1, font)
            name2 = self._resolvedCornerName(2, font)
            self._settingsWindow.corner1.set(self._indexForName(name1, names, 0))
            self._settingsWindow.corner2.set(self._indexForName(name2, names, 1))
            self._settingsWindow.save.enable(True)
            self._settingsWindow.status.set("Q mirrors the selected corner horizontally.")
        else:
            self._settingsWindow.corner1.set(0)
            self._settingsWindow.corner2.set(0)
            self._settingsWindow.save.enable(False)
            self._settingsWindow.status.set("Open a font containing _corner.* glyphs.")

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
        if not names:
            return
        try:
            index1 = int(self._settingsWindow.corner1.get())
            index2 = int(self._settingsWindow.corner2.get())
            Glyphs.defaults[self.corner1DefaultsKey] = names[index1]
            Glyphs.defaults[self.corner2DefaultsKey] = names[index2]
            self._settingsWindow.status.set("Saved: 1 → %s, 2 → %s" % (names[index1], names[index2]))
            self._settingsWindow.close()
        except Exception:
            print("Corner Hotkeys: could not save settings")
            print(traceback.format_exc())
            Glyphs.showMacroWindow()

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
            print("Corner Hotkeys: could not install keyboard event monitor")
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

            layer = self._currentLayer(font)
            if layer is None:
                return event

            if action == "corner1":
                performed = self._applyCornerSlot(layer, font, 1)
            elif action == "corner2":
                performed = self._applyCornerSlot(layer, font, 2)
            else:
                performed = self._mirrorSelectedCorners(layer)

            # Returning None consumes the event. We do that only when a corner
            # action was actually performed (or settings were opened for a
            # valid selection), so normal Glyphs typing and shortcuts survive.
            return None if performed else event

        except Exception:
            print("Corner Hotkeys: keyboard handling error")
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

        if keyCode == self.keyCode1 and not shiftDown:
            return "corner1"
        if keyCode == self.keyCode2 and not shiftDown:
            return "corner2"
        if keyCode == self.keyCodeQ:
            return "mirror"

        # Fallback for unusual keyboards / PyObjC builds.
        try:
            chars = str(event.charactersIgnoringModifiers() or "").lower()
        except Exception:
            chars = ""
        if chars == "1" and not shiftDown:
            return "corner1"
        if chars == "2" and not shiftDown:
            return "corner2"
        if chars == "q":
            return "mirror"
        return None

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
                "Open Glyph → Corner Hotkeys Settings… and choose the _corner.* glyph for key %d." % slot,
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
        selectedHints, selectedNodes = self._selectedCornersAndNodes(layer)

        corners = list(selectedHints)
        for node in selectedNodes:
            corners.extend(self._cornerHintsAttachedToNode(layer, node))
        corners = self._dedupeObjects(corners)

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
                    print("Corner Hotkeys: could not mirror corner %r" % hint)
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
            print("Corner Hotkeys: could not create corner")
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

        key = self.corner1DefaultsKey if int(slot) == 1 else self.corner2DefaultsKey
        configured = None
        try:
            configured = Glyphs.defaults[key]
        except Exception:
            pass
        if configured in names:
            return configured

        # Zero-configuration behaviour for the intended temporary workflow:
        # the first two _corner.* glyphs in font order map to 1 and 2.
        index = 0 if int(slot) == 1 else 1
        if index < len(names):
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
