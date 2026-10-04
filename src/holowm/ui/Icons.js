.pragma library

// Line icons on a 24-unit grid, as SVG path data. Drawn by Icon.qml with round caps and joins.
var paths = {
    "check": "M5 12.5 L9.5 17 L19 7.5",
    "bang": "M12 5 L12 13 M12 18.5 L12 19",
    "cross": "M6 6 L18 18 M18 6 L6 18",
    "power": "M12 3 L12 11 M6.3 6.8 A8 8 0 1 0 17.7 6.8",
    "pause": "M8 5 L8 19 M16 5 L16 19",
    "play": "M8 5.5 L8 18.5 A1 1 0 0 0 9.5 19.37 L20.5 12.87 A1 1 0 0 0 20.5 11.13 L9.5 4.63 A1 1 0 0 0 8 5.5 Z",
    "stop": "M8 8 L16 8 L16 16 L8 16 Z",
    "info": "M12 3 A9 9 0 1 0 12 21 A9 9 0 1 0 12 3 Z M12 11 L12 17 M12 7.5 L12 8",
    "up": "M6 15 L12 9 L18 15",
    "down": "M6 9 L12 15 L18 9",
    "right": "M5 12 L19 12 M13 6 L19 12 L13 18",
    "left": "M19 12 L5 12 M11 6 L5 12 L11 18",
    "arrowDown": "M12 5 L12 19 M6 13 L12 19 L18 13",
    "back": "M9 14 L4 9 L9 4 M4 9 L14 9 A6 6 0 0 1 14 21 L12 21",
    "wrench": "M14.5 6.5 A4.5 4.5 0 0 0 8.5 12.2 L3.5 17.2 L6.8 20.5 L11.8 15.5 A4.5 4.5 0 0 0 17.5 9.5 L14.5 12.5 L12 10 Z",
    "camera": "M6 7 L18 7 A3 3 0 0 1 21 10 L21 17 A3 3 0 0 1 18 20 L6 20 A3 3 0 0 1 3 17 L3 10 A3 3 0 0 1 6 7 Z M12 10 A3.5 3.5 0 1 0 12 17 A3.5 3.5 0 1 0 12 10 Z M8.5 7 L10 4.5 L14 4.5 L15.5 7",
    "plus": "M12 5 L12 19 M5 12 L19 12",
    "enter": "M19 6 L19 11 A3 3 0 0 1 16 14 L5 14 M9.5 9.5 L5 14 L9.5 18.5",
    "mic": "M12 3 A3 3 0 0 0 9 6 L9 11 A3 3 0 0 0 15 11 L15 6 A3 3 0 0 0 12 3 Z M5.5 11 A6.5 6.5 0 0 0 18.5 11 M12 17.5 L12 21",
    "speaker": "M4 9.5 L7.5 9.5 L12 6 L12 18 L7.5 14.5 L4 14.5 Z M15.5 9.5 A4 4 0 0 1 15.5 14.5 M18 7 A7.5 7.5 0 0 1 18 17",
    "sun": "M12 8 A4 4 0 1 0 12 16 A4 4 0 1 0 12 8 Z M12 3 L12 5 M12 19 L12 21 M3 12 L5 12 M19 12 L21 12 M5.6 5.6 L7 7 M17 17 L18.4 18.4 M5.6 18.4 L7 17 M17 7 L18.4 5.6",
    "windows": "M5.5 5 L12.5 5 A2 2 0 0 1 14.5 7 L14.5 12 A2 2 0 0 1 12.5 14 L5.5 14 A2 2 0 0 1 3.5 12 L3.5 7 A2 2 0 0 1 5.5 5 Z M17 10 L18.5 10 A2 2 0 0 1 20.5 12 L20.5 17 A2 2 0 0 1 18.5 19 L11.5 19 A2 2 0 0 1 9.5 17 L9.5 16.5",
    "terminal": "M6 4 L18 4 A3 3 0 0 1 21 7 L21 17 A3 3 0 0 1 18 20 L6 20 A3 3 0 0 1 3 17 L3 7 A3 3 0 0 1 6 4 Z M7 10 L10 12.5 L7 15 M13 15 L17 15",
    "globe": "M12 3 A9 9 0 1 0 12 21 A9 9 0 1 0 12 3 Z M3 12 L21 12 M12 3 C14.8 6 14.8 18 12 21 M12 3 C9.2 6 9.2 18 12 21",
    "folder": "M3 7.5 A2.5 2.5 0 0 1 5.5 5 L9 5 L11 7.5 L18.5 7.5 A2.5 2.5 0 0 1 21 10 L21 16.5 A2.5 2.5 0 0 1 18.5 19 L5.5 19 A2.5 2.5 0 0 1 3 16.5 Z",
    "music": "M9 18 L9 6 L19 4 L19 16 M9 18 A2.5 2.5 0 1 1 4 18 A2.5 2.5 0 1 1 9 18 Z M19 16 A2.5 2.5 0 1 1 14 16 A2.5 2.5 0 1 1 19 16 Z",
    "grid": "M6 4 L9 4 A2 2 0 0 1 11 6 L11 9 A2 2 0 0 1 9 11 L6 11 A2 2 0 0 1 4 9 L4 6 A2 2 0 0 1 6 4 Z M15 4 L18 4 A2 2 0 0 1 20 6 L20 9 A2 2 0 0 1 18 11 L15 11 A2 2 0 0 1 13 9 L13 6 A2 2 0 0 1 15 4 Z M6 13 L9 13 A2 2 0 0 1 11 15 L11 18 A2 2 0 0 1 9 20 L6 20 A2 2 0 0 1 4 18 L4 15 A2 2 0 0 1 6 13 Z M15 13 L18 13 A2 2 0 0 1 20 15 L20 18 A2 2 0 0 1 18 20 L15 20 A2 2 0 0 1 13 18 L13 15 A2 2 0 0 1 15 13 Z",
    "window": "M6 5 L18 5 A3 3 0 0 1 21 8 L21 16 A3 3 0 0 1 18 19 L6 19 A3 3 0 0 1 3 16 L3 8 A3 3 0 0 1 6 5 Z M3 9.5 L21 9.5",
    "workspaces": "M5.5 8 L12.5 8 A2.5 2.5 0 0 1 15 10.5 L15 16.5 A2.5 2.5 0 0 1 12.5 19 L5.5 19 A2.5 2.5 0 0 1 3 16.5 L3 10.5 A2.5 2.5 0 0 1 5.5 8 Z M9 8 L9 7.5 A2.5 2.5 0 0 1 11.5 5 L18.5 5 A2.5 2.5 0 0 1 21 7.5 L21 13.5 A2.5 2.5 0 0 1 18.5 16 L15 16",
    "maximize": "M4 9 L4 4 L9 4 M20 15 L20 20 L15 20 M4 4 L10 10 M20 20 L14 14",
    "next": "M6 6 L14 12 L6 18 Z M17 6 L17 18",
    "previous": "M18 6 L10 12 L18 18 Z M7 6 L7 18"
}

// The icon names the built-in menu uses, and the commonest ones a menu.toml would, by glyph.
var named = {
    "utilities-terminal": "terminal",
    "web-browser": "globe",
    "system-file-manager": "folder",
    "applications-multimedia": "music",
    "view-grid": "grid",
    "preferences-system-windows": "window",
    "preferences-desktop-workspaces": "workspaces",
    "view-fullscreen": "maximize",
    "go-next": "right",
    "go-previous": "left",
    "go-down": "arrowDown",
    "window-close": "cross",
    "media-skip-forward": "next",
    "media-skip-backward": "previous"
}

// The path for a glyph of ours, or for an icon-theme name we draw ourselves; "" if neither.
function path(name) {
    return paths[name] || paths[named[name]] || ""
}
