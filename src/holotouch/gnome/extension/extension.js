// HoloTouch's hands inside GNOME Shell.
//
// Under Wayland no program outside the compositor may list windows, move them, or press keys.
// HoloTouch (the Python program) therefore asks this extension to, over the session bus: see
// holotouch/gnome/backend.py, which is the only caller. Positions and sizes here are in the
// stage's own units, which are not screen pixels on a scaled monitor; the caller converts.
//
// Nothing is watched, and no signal is sent, until a caller says Watch, and it all stops again
// when the last caller has left the bus.

import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import Mtk from 'gi://Mtk';
import Shell from 'gi://Shell';
import St from 'gi://St';
import Cairo from 'cairo';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const BUS_NAME = 'dev.internetguy.HoloTouch';
const OBJECT_PATH = '/dev/internetguy/HoloTouch';
// What the Python side checks, so that an extension left over from an older HoloTouch is told
// apart. Raised whenever a method or the state below changes its meaning.
const VERSION = 1;

const INTERFACE = `
<node>
  <interface name="dev.internetguy.HoloTouch">
    <method name="Watch"><arg type="s" direction="out" name="state"/></method>
    <method name="Unwatch"/>
    <signal name="StateChanged"><arg type="s" name="state"/></signal>
    <method name="Activate"><arg type="t" direction="in" name="window"/></method>
    <method name="MoveResize">
      <arg type="t" direction="in" name="window"/>
      <arg type="i" direction="in" name="x"/>
      <arg type="i" direction="in" name="y"/>
      <arg type="i" direction="in" name="width"/>
      <arg type="i" direction="in" name="height"/>
    </method>
    <method name="SetMaximized">
      <arg type="t" direction="in" name="window"/>
      <arg type="b" direction="in" name="on"/>
    </method>
    <method name="Minimize"><arg type="t" direction="in" name="window"/></method>
    <method name="Close"><arg type="t" direction="in" name="window"/></method>
    <method name="SwitchWorkspace"><arg type="i" direction="in" name="index"/></method>
    <method name="SetWindowWorkspace">
      <arg type="t" direction="in" name="window"/>
      <arg type="i" direction="in" name="index"/>
    </method>
    <method name="Pointer">
      <arg type="i" direction="out" name="x"/>
      <arg type="i" direction="out" name="y"/>
    </method>
    <method name="WarpPointer">
      <arg type="d" direction="in" name="x"/>
      <arg type="d" direction="in" name="y"/>
    </method>
    <method name="Button"><arg type="b" direction="in" name="down"/></method>
    <method name="Scroll"><arg type="d" direction="in" name="notches"/></method>
    <method name="Keys"><arg type="au" direction="in" name="keyvals"/></method>
    <method name="TypeText"><arg type="s" direction="in" name="text"/></method>
    <method name="GetClipboard">
      <arg type="b" direction="out" name="has_text"/>
      <arg type="s" direction="out" name="text"/>
      <arg type="u" direction="out" name="serial"/>
    </method>
    <method name="SetClipboard"><arg type="s" direction="in" name="text"/></method>
    <method name="Thumbnails">
      <arg type="at" direction="in" name="windows"/>
      <arg type="i" direction="in" name="max_width"/>
      <arg type="i" direction="in" name="max_height"/>
      <arg type="s" direction="out" name="paths"/>
    </method>
  </interface>
</node>`;

// Application windows: not the desktop, a dock, or the menus and tooltips of other windows.
const WINDOW_TYPES = new Set([
    Meta.WindowType.NORMAL,
    Meta.WindowType.DIALOG,
    Meta.WindowType.MODAL_DIALOG,
    Meta.WindowType.UTILITY,
]);
const WINDOW_SIGNALS = [
    'position-changed',
    'size-changed',
    'workspace-changed',
    'notify::title',
    'notify::wm-class',
    'notify::minimized',
    'notify::maximized-horizontally',
    'notify::maximized-vertically',
    'notify::fullscreen',
    'notify::skip-taskbar',
];
const STATE_INTERVAL_MS = 8; // the state is sent no more often than this
const SCROLL_PER_NOTCH = 10; // what one notch of a mouse wheel scrolls, in Clutter's units
const TYPE_INTERVAL_MS = 5;
const TYPE_BATCH = 8; // characters typed every TYPE_INTERVAL_MS

// Maximizing took the directions as an argument before GNOME 49, and has kept them apart since.
function isMaximized(win) {
    return win.is_maximized ? win.is_maximized() : win.get_maximized() === Meta.MaximizeFlags.BOTH;
}

function maximizedFlags(win) {
    return win.get_maximize_flags ? win.get_maximize_flags() : win.get_maximized();
}

function setMaximized(win, on) {
    const both = Meta.MaximizeFlags.BOTH;
    if (on) {
        if (win.set_maximize_flags) {
            win.set_maximize_flags(both);
            win.maximize();
        } else {
            win.maximize(both);
        }
    } else if (win.set_unmaximize_flags) {
        win.set_unmaximize_flags(both);
        win.unmaximize();
    } else {
        win.unmaximize(both);
    }
}

function describe(win, tracker) {
    const rect = win.get_frame_rect();
    const workspace = win.get_workspace();
    // The least size the window will take, if it names one: given with the shadow it draws
    // round itself, which the rectangle above leaves out.
    const [hasMin, minWidth, minHeight] = win.get_min_size ? win.get_min_size() : [false, 1, 1];
    const buffer = win.get_buffer_rect();
    return {
        id: win.get_id(),
        x: rect.x,
        y: rect.y,
        w: rect.width,
        h: rect.height,
        workspace: win.is_on_all_workspaces() || !workspace ? -1 : workspace.index(),
        title: win.get_title() ?? '',
        class: win.get_wm_class() ?? '',
        maximized: isMaximized(win),
        fullscreen: win.is_fullscreen(),
        minimized: win.minimized,
        skip: win.is_skip_taskbar(),
        min: hasMin ? [minWidth - (buffer.width - rect.width), minHeight - (buffer.height - rect.height)] : [1, 1],
        // The name of the app's icon in the icon theme, or the file it is in.
        icon: tracker.get_window_app(win)?.get_icon()?.to_string() ?? '',
    };
}

class Service {
    constructor() {
        this._watchers = new Map(); // bus name -> what watches for it leaving
        this._stateTimeout = 0;
        this._sent = '';
        this._pointer = null;
        this._keyboard = null;
        this._buttonDown = false;
        this._typing = []; // keyvals yet to be typed
        this._typeTimeout = 0;
        this._thumbnailIdles = new Set();
        this._clipboardSerial = 0;
        global.display.get_selection().connectObject('owner-changed', (_selection, type) => {
            if (type === Meta.SelectionType.SELECTION_CLIPBOARD)
                this._clipboardSerial++;
        }, this);
        this._dbus = Gio.DBusExportedObject.wrapJSObject(INTERFACE, this);
        this._dbus.export(Gio.DBus.session, OBJECT_PATH);
        this._owner = Gio.bus_own_name_on_connection(
            Gio.DBus.session, BUS_NAME, Gio.BusNameOwnerFlags.NONE, null, null);
    }

    destroy() {
        for (const name of [...this._watchers.keys()])
            this._drop(name);
        for (const id of [this._typeTimeout, ...this._thumbnailIdles]) {
            if (id)
                GLib.source_remove(id);
        }
        this._typing = [];
        this._thumbnailIdles.clear();
        global.display.get_selection().disconnectObject(this);
        Gio.bus_unown_name(this._owner);
        this._dbus.unexport();
        this._dbus = null;
        this._pointer = null;
        this._keyboard = null;
    }

    // -- the windows, and telling the callers of them -----------------------------------------

    _windows() {
        return global.display.list_all_windows().filter(
            win => !win.is_override_redirect() && WINDOW_TYPES.has(win.get_window_type()));
    }

    _window(id) {
        return this._windows().find(win => win.get_id() === id) ?? null;
    }

    _state() {
        const display = global.display;
        const manager = global.workspace_manager;
        const monitor = display.get_primary_monitor();
        const [width, height] = display.get_size();
        const area = monitor >= 0
            ? manager.get_active_workspace().get_work_area_for_monitor(monitor)
            : {x: 0, y: 0, width, height};
        const focus = display.get_focus_window();
        const tracker = Shell.WindowTracker.get_default();
        return {
            version: VERSION,
            size: [width, height],
            workarea: [area.x, area.y, area.width, area.height],
            workspace: manager.get_active_workspace_index(),
            workspaces: manager.get_n_workspaces(),
            active: focus ? focus.get_id() : 0,
            // From the bottom of the stack to the top.
            windows: display.sort_windows_by_stacking(this._windows()).map(win => describe(win, tracker)),
        };
    }

    _queueState() {
        if (this._stateTimeout)
            return;
        this._stateTimeout = GLib.timeout_add(GLib.PRIORITY_DEFAULT, STATE_INTERVAL_MS, () => {
            this._stateTimeout = 0;
            const state = JSON.stringify(this._state());
            if (state !== this._sent) {
                this._sent = state;
                this._dbus.emit_signal('StateChanged', new GLib.Variant('(s)', [state]));
            }
            return GLib.SOURCE_REMOVE;
        });
    }

    _track(win) {
        const changed = () => this._queueState();
        win.connectObject(
            ...WINDOW_SIGNALS.flatMap(signal => [signal, changed]),
            'unmanaged', () => {
                win.disconnectObject(this);
                changed();
            }, this);
    }

    _startWatching() {
        const changed = () => this._queueState();
        global.display.connectObject(
            'window-created', (_display, win) => {
                this._track(win);
                changed();
            },
            'restacked', changed,
            'notify::focus-window', changed,
            'workareas-changed', changed, this);
        global.window_manager.connectObject(
            'switch-workspace', changed,
            'minimize', changed,
            'unminimize', changed,
            'map', changed,
            'destroy', changed, this);
        global.workspace_manager.connectObject(
            'notify::n-workspaces', changed,
            'active-workspace-changed', changed, this);
        for (const win of global.display.list_all_windows())
            this._track(win);
        // Made now and not when first used: a program only learns of a new device a moment
        // after it appears, and what the device does before then is lost on it.
        this._mouse();
        this._keys();
    }

    _stopWatching() {
        for (const win of global.display.list_all_windows())
            win.disconnectObject(this);
        global.display.disconnectObject(this);
        global.window_manager.disconnectObject(this);
        global.workspace_manager.disconnectObject(this);
        if (this._stateTimeout)
            GLib.source_remove(this._stateTimeout);
        this._stateTimeout = 0;
        this._sent = '';
        this._pointer = null;
        this._keyboard = null;
    }

    _drop(name) {
        const watch = this._watchers.get(name);
        if (watch === undefined)
            return;
        Gio.bus_unwatch_name(watch);
        this._watchers.delete(name);
        if (this._watchers.size === 0) {
            this.Button(false); // a button left down would stay down
            this._stopWatching();
        }
    }

    WatchAsync(_params, invocation) {
        const name = invocation.get_sender();
        if (!this._watchers.has(name)) {
            if (this._watchers.size === 0)
                this._startWatching();
            this._watchers.set(name, Gio.bus_watch_name_on_connection(
                Gio.DBus.session, name, Gio.BusNameWatcherFlags.NONE, null, () => this._drop(name)));
        }
        invocation.return_value(new GLib.Variant('(s)', [JSON.stringify(this._state())]));
    }

    UnwatchAsync(_params, invocation) {
        this._drop(invocation.get_sender());
        invocation.return_value(null);
    }

    // -- changing the windows -----------------------------------------------------------------

    Activate(id) {
        const win = this._window(id);
        if (win)
            Main.activateWindow(win);
    }

    MoveResize(id, x, y, width, height) {
        const win = this._window(id);
        if (!win)
            return;
        // A window tiled to one side of the screen is held there until it is let out.
        if (maximizedFlags(win) && !isMaximized(win))
            setMaximized(win, false);
        win.move_resize_frame(true, x, y, width, height);
    }

    SetMaximized(id, on) {
        const win = this._window(id);
        if (win)
            setMaximized(win, on);
    }

    Minimize(id) {
        this._window(id)?.minimize();
    }

    Close(id) {
        this._window(id)?.delete(global.get_current_time());
    }

    SwitchWorkspace(index) {
        global.workspace_manager.get_workspace_by_index(index)?.activate(global.get_current_time());
    }

    SetWindowWorkspace(id, index) {
        this._window(id)?.change_workspace_by_index(index, false);
    }

    // -- the pointer and the keyboard ---------------------------------------------------------

    _device(type) {
        return Clutter.get_default_backend().get_default_seat().create_virtual_device(type);
    }

    _mouse() {
        this._pointer ??= this._device(Clutter.InputDeviceType.POINTER_DEVICE);
        return this._pointer;
    }

    _keys() {
        this._keyboard ??= this._device(Clutter.InputDeviceType.KEYBOARD_DEVICE);
        return this._keyboard;
    }

    Pointer() {
        const [x, y] = global.get_pointer();
        return [x, y];
    }

    WarpPointer(x, y) {
        this._mouse().notify_absolute_motion(GLib.get_monotonic_time(), x, y);
    }

    Button(down) {
        if (down === this._buttonDown)
            return;
        this._buttonDown = down;
        this._mouse().notify_button(
            GLib.get_monotonic_time(), Clutter.BUTTON_PRIMARY,
            down ? Clutter.ButtonState.PRESSED : Clutter.ButtonState.RELEASED);
    }

    // Positive scrolls up, by so many notches of a mouse wheel, or a part of one.
    Scroll(notches) {
        this._mouse().notify_scroll_continuous(
            GLib.get_monotonic_time(), 0, -notches * SCROLL_PER_NOTCH,
            Clutter.ScrollSource.WHEEL, Clutter.ScrollFinishFlags.NONE);
    }

    // The keys are pressed in the order given and let go in the other: Control, then T.
    Keys(keyvals) {
        const keyboard = this._keys();
        for (const keyval of keyvals)
            keyboard.notify_keyval(GLib.get_monotonic_time(), keyval, Clutter.KeyState.PRESSED);
        for (const keyval of [...keyvals].reverse())
            keyboard.notify_keyval(GLib.get_monotonic_time(), keyval, Clutter.KeyState.RELEASED);
    }

    TypeText(text) {
        // Where a text field has the keyboard the text is handed over whole, as an input method
        // hands it over, which no keyboard layout can get in the way of. Elsewhere (a terminal,
        // or an X11 program) it is typed key by key, a few at a time.
        if (Main.inputMethod.currentFocus) {
            Main.inputMethod.commit(text);
            return;
        }
        for (const char of text) {
            if (char === '\n')
                this._typing.push(Clutter.KEY_Return);
            else if (char === '\t')
                this._typing.push(Clutter.KEY_Tab);
            else
                this._typing.push(Clutter.unicode_to_keysym(char.codePointAt(0)));
        }
        if (this._typeTimeout)
            return;
        this._typeTimeout = GLib.timeout_add(GLib.PRIORITY_DEFAULT, TYPE_INTERVAL_MS, () => {
            for (const keyval of this._typing.splice(0, TYPE_BATCH))
                this.Keys([keyval]);
            if (this._typing.length)
                return GLib.SOURCE_CONTINUE;
            this._typeTimeout = 0;
            return GLib.SOURCE_REMOVE;
        });
    }

    // -- the clipboard ------------------------------------------------------------------------

    // The serial goes up whenever something new is copied, which tells a copy of the same text
    // from no copy at all.
    GetClipboardAsync(_params, invocation) {
        St.Clipboard.get_default().get_text(St.ClipboardType.CLIPBOARD, (_clipboard, text) => {
            invocation.return_value(new GLib.Variant(
                '(bsu)', [text !== null, text ?? '', this._clipboardSerial]));
        });
    }

    SetClipboard(text) {
        St.Clipboard.get_default().set_text(St.ClipboardType.CLIPBOARD, text);
    }

    // -- pictures of the windows --------------------------------------------------------------

    _thumbnail(actor, maxWidth, maxHeight, directory) {
        const win = actor.meta_window;
        const frame = win.get_frame_rect();
        const buffer = win.get_buffer_rect();
        // Without the shadow a window draws round itself.
        const image = actor.get_image(new Mtk.Rectangle({
            x: frame.x - buffer.x,
            y: frame.y - buffer.y,
            width: frame.width,
            height: frame.height,
        }));
        if (!image)
            return null;
        const scale = Math.min(maxWidth / image.getWidth(), maxHeight / image.getHeight(), 1);
        const width = Math.max(Math.round(image.getWidth() * scale), 1);
        const height = Math.max(Math.round(image.getHeight() * scale), 1);
        const small = new Cairo.ImageSurface(Cairo.Format.ARGB32, width, height);
        const cr = new Cairo.Context(small);
        cr.scale(width / image.getWidth(), height / image.getHeight());
        cr.setSourceSurface(image, 0, 0);
        cr.paint();
        cr.$dispose();
        const path = GLib.build_filenamev([directory, `${win.get_id()}.png`]);
        small.writeToPNG(path);
        return path;
    }

    // Pictures of these windows, each made to fit the size given and saved as a PNG file for
    // the caller to read and delete. One window is done at a time, between frames, so that the
    // desktop does not stand still while they are made.
    ThumbnailsAsync([ids, maxWidth, maxHeight], invocation) {
        const directory = GLib.build_filenamev([GLib.get_user_runtime_dir(), 'holotouch-thumbnails']);
        GLib.mkdir_with_parents(directory, 0o700);
        const wanted = new Set(ids.map(Number));
        const actors = global.get_window_actors().filter(
            actor => actor.meta_window && wanted.has(actor.meta_window.get_id()));
        const paths = {};
        const idle = GLib.idle_add(GLib.PRIORITY_DEFAULT, () => {
            const actor = actors.shift();
            if (actor) {
                try {
                    const path = this._thumbnail(actor, maxWidth, maxHeight, directory);
                    if (path)
                        paths[actor.meta_window.get_id()] = path;
                } catch (error) {
                    console.debug(`HoloTouch: no picture of a window: ${error}`);
                }
                return GLib.SOURCE_CONTINUE;
            }
            this._thumbnailIdles.delete(idle);
            invocation.return_value(new GLib.Variant('(s)', [JSON.stringify(paths)]));
            return GLib.SOURCE_REMOVE;
        });
        this._thumbnailIdles.add(idle);
    }
}

export default class HoloTouchExtension extends Extension {
    enable() {
        this._service = new Service();
    }

    disable() {
        this._service.destroy();
        this._service = null;
    }
}
