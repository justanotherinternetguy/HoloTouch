// The desktop at the top of the page: HoloWM's overlay, played over a stand-in desktop. Two ring
// cursors move a window, resize it, open the pie menu and close what it opened, on a loop.
// Everything on it is a function of the scene and the time within it, so any scene can be jumped to.
(function () {
    'use strict';

    const HW = window.HoloWM;
    const ease = HW.ease;
    const W = 880;

    // The line icons the overlay draws (src/holowm/ui/Icons.js), on a 24-unit grid.
    const ICONS = {
        terminal: 'M6 4 L18 4 A3 3 0 0 1 21 7 L21 17 A3 3 0 0 1 18 20 L6 20 A3 3 0 0 1 3 17 L3 7 A3 3 0 0 1 6 4 Z M7 10 L10 12.5 L7 15 M13 15 L17 15',
        globe: 'M12 3 A9 9 0 1 0 12 21 A9 9 0 1 0 12 3 Z M3 12 L21 12 M12 3 C14.8 6 14.8 18 12 21 M12 3 C9.2 6 9.2 18 12 21',
        folder: 'M3 7.5 A2.5 2.5 0 0 1 5.5 5 L9 5 L11 7.5 L18.5 7.5 A2.5 2.5 0 0 1 21 10 L21 16.5 A2.5 2.5 0 0 1 18.5 19 L5.5 19 A2.5 2.5 0 0 1 3 16.5 Z',
        music: 'M9 18 L9 6 L19 4 L19 16 M9 18 A2.5 2.5 0 1 1 4 18 A2.5 2.5 0 1 1 9 18 Z M19 16 A2.5 2.5 0 1 1 14 16 A2.5 2.5 0 1 1 19 16 Z',
        grid: 'M6 4 L9 4 A2 2 0 0 1 11 6 L11 9 A2 2 0 0 1 9 11 L6 11 A2 2 0 0 1 4 9 L4 6 A2 2 0 0 1 6 4 Z M15 4 L18 4 A2 2 0 0 1 20 6 L20 9 A2 2 0 0 1 18 11 L15 11 A2 2 0 0 1 13 9 L13 6 A2 2 0 0 1 15 4 Z M6 13 L9 13 A2 2 0 0 1 11 15 L11 18 A2 2 0 0 1 9 20 L6 20 A2 2 0 0 1 4 18 L4 15 A2 2 0 0 1 6 13 Z M15 13 L18 13 A2 2 0 0 1 20 15 L20 18 A2 2 0 0 1 18 20 L15 20 A2 2 0 0 1 13 18 L13 15 A2 2 0 0 1 15 13 Z',
        window: 'M6 5 L18 5 A3 3 0 0 1 21 8 L21 16 A3 3 0 0 1 18 19 L6 19 A3 3 0 0 1 3 16 L3 8 A3 3 0 0 1 6 5 Z M3 9.5 L21 9.5',
        workspaces: 'M5.5 8 L12.5 8 A2.5 2.5 0 0 1 15 10.5 L15 16.5 A2.5 2.5 0 0 1 12.5 19 L5.5 19 A2.5 2.5 0 0 1 3 16.5 L3 10.5 A2.5 2.5 0 0 1 5.5 8 Z M9 8 L9 7.5 A2.5 2.5 0 0 1 11.5 5 L18.5 5 A2.5 2.5 0 0 1 21 7.5 L21 13.5 A2.5 2.5 0 0 1 18.5 16 L15 16'
    };
    // The built-in pie menu, clockwise from twelve. Butter launches, lilac opens further, mint acts
    // on the window under the hand.
    const PETALS = [
        ['terminal', 'butter', 'Terminal', 'let go to open'], ['globe', 'butter', 'Browser', 'let go to open'],
        ['folder', 'butter', 'Files', 'let go to open'], ['music', 'lilac', 'Music', 'opens further'],
        ['grid', 'lilac', 'Windows', 'opens further'], ['window', 'mint', 'Window', 'opens further'],
        ['workspaces', 'lilac', 'Workspaces', 'opens further']
    ];
    const ORBIT = 104;
    const DEAD_ZONE = 26;

    // The windows' places: where the browser starts, where it is carried to, and what it is resized to.
    const A0 = { x: 60, y: 64, w: 400, h: 280 };
    const A1 = { x: 200, y: 100, w: 400, h: 280 };
    const A2 = { x: 140, y: 80, w: 500, h: 340 };
    const TERMINAL = { x: 560, y: 96, w: 280, h: 196 };
    const MENU = { x: 660, y: 262 };

    // A value at time t along keyframes [time, value, easing into it].
    function kf(t, points) {
        if (t <= points[0][0]) return points[0][1];
        for (let i = 1; i < points.length; i++) {
            if (t <= points[i][0]) {
                const a = points[i - 1], b = points[i];
                return a[1] + (b[1] - a[1]) * (b[2] || ease.sine)((t - a[0]) / (b[0] - a[0]));
            }
        }
        return points[points.length - 1][1];
    }
    // The same for a position: [time, x, y].
    function along(t, points) {
        return {
            x: kf(t, points.map(function (p) { return [p[0], p[1]]; })),
            y: kf(t, points.map(function (p) { return [p[0], p[2]]; }))
        };
    }
    function hand(at, more) {
        return Object.assign({ x: at.x, y: at.y, alpha: 1, pinch: 0, idle: 0, pose: 'open' }, more);
    }
    // The mint ring every finished action ends with.
    function pulseAt(t, when, at) {
        const p = (t - when) / 320;
        return p >= 0 && p <= 1 ? { x: at.x, y: at.y, p: p } : null;
    }

    const SCENES = [
        {
            id: 'move', length: 5200, still: 2400,
            title: 'Move a window', pose: 'Thumb + index pinch', how: 'Pinch over a window and carry it.',
            at: function (t) {
                const at = along(t, [[0, 640, 440], [1100, 250, 190], [1700, 250, 190], [3000, 390, 226]]);
                const pinch = kf(t, [[1250, 0], [1500, 1, ease.linear], [3300, 1], [3450, 0, ease.linear]]);
                const carried = t >= 1700;
                const a = { x: A0.x + (carried ? at.x - 250 : 0), y: A0.y + (carried ? at.y - 190 : 0), w: A0.w, h: A0.h };
                return {
                    a: a,
                    right: hand(at, { alpha: kf(t, [[0, 0], [350, 1]]), pinch: pinch, pose: pinch > 0.5 ? 'index' : 'open' }),
                    frame: t > 700 ? { rect: a, held: t >= 1500 && t < 3450 } : null,
                    squeeze: kf(t, [[1500, 0], [1620, 1], [3450, 1], [3560, -0.8], [3800, 0]]),
                    pulse: pulseAt(t, 3450, at)
                };
            }
        },
        {
            id: 'resize', length: 6200, still: 3700,
            title: 'Resize', pose: 'Second hand pinches too', how: 'The two hands pull apart or together.',
            at: function (t) {
                const r = along(t, [[0, 390, 226], [800, 530, 150], [2300, 530, 150], [3500, 620, 110], [4100, 620, 110], [4900, 570, 130]]);
                const l = along(t, [[500, 120, 470], [1600, 270, 330], [2300, 270, 330], [3500, 160, 400], [4100, 160, 400], [4900, 210, 370]]);
                const rightPinch = kf(t, [[900, 0], [1100, 1, ease.linear], [5300, 1], [5450, 0, ease.linear]]);
                const leftPinch = kf(t, [[1750, 0], [1950, 1, ease.linear], [5300, 1], [5450, 0, ease.linear]]);
                // The right hand has the top right corner and the left hand the bottom left.
                const edges = { left: 200 + (l.x - 270), top: 100 + (r.y - 150), right: 600 + (r.x - 530), bottom: 380 + (l.y - 330) };
                const a = { x: edges.left, y: edges.top, w: edges.right - edges.left, h: edges.bottom - edges.top };
                return {
                    a: a,
                    right: hand(r, { pinch: rightPinch, pose: rightPinch > 0.5 ? 'index' : 'open' }),
                    left: hand(l, { alpha: kf(t, [[500, 0], [800, 1]]), pinch: leftPinch, pose: leftPinch > 0.5 ? 'index' : 'open' }),
                    frame: { rect: a, held: t >= 1100 && t < 5450 },
                    squeeze: kf(t, [[1100, 0], [1220, 1], [5450, 1], [5560, -0.8], [5800, 0]]),
                    resize: t >= 1950 && t < 5450 ? A1 : null,
                    pulse: pulseAt(t, 5450, r)
                };
            }
        },
        {
            id: 'menu', length: 6000, still: 4500,
            title: 'Pie menu', pose: 'Thumb + pinky pinch', how: 'Move toward an item and let go to pick it.',
            at: function (t) {
                const r = along(t, [[0, 570, 130], [900, MENU.x, MENU.y], [1500, MENU.x, MENU.y], [2300, 718, 276], [2700, 718, 276],
                                    [3300, 706, 224], [3600, 706, 224], [4200, 664, 202]]);
                const pinch = kf(t, [[1300, 0], [1500, 1, ease.linear], [4900, 1], [5050, 0, ease.linear]]);
                let aim = -1;
                if (t >= 4900) {
                    aim = 0;
                } else if (t >= 1500 && Math.hypot(r.x - MENU.x, r.y - MENU.y) > DEAD_ZONE) {
                    const turn = Math.atan2(r.x - MENU.x, MENU.y - r.y) * 180 / Math.PI;
                    aim = Math.round(((turn + 360) % 360) / (360 / PETALS.length)) % PETALS.length;
                }
                return {
                    a: A2,
                    terminal: kf(t, [[5000, 0], [5380, 1, ease.outBack]]),
                    right: hand(r, { pinch: pinch, pose: pinch > 0.5 ? 'pinky' : 'open' }),
                    left: hand(along(t, [[0, 210, 370], [1200, 150, 440]]), { idle: kf(t, [[1800, 0], [2200, 1]]) }),
                    frame: t < 600 ? { rect: A2, held: false } : null,
                    menu: t >= 1500 && t < 5300 ? { open: t - 1500, shut: t - 4900, aim: aim } : null,
                    pulse: pulseAt(t, 4900, r)
                };
            }
        },
        {
            id: 'close', length: 4900, still: 1500,
            title: 'Close a window', pose: 'Fist, held still', how: 'A ring fills for about 0.7 s. Moving or opening the hand cancels it.',
            at: function (t) {
                const r = along(t, [[0, 664, 202], [700, 700, 190]]);
                const leaving = kf(t, [[3500, 1], [3850, 0]]);
                const home = kf(t, [[3800, 0], [4600, 1]]);
                return {
                    // With the terminal gone the hands leave, and the browser goes back to where it began.
                    a: { x: A2.x + (A0.x - A2.x) * home, y: A2.y + (A0.y - A2.y) * home, w: A2.w + (A0.w - A2.w) * home, h: A2.h + (A0.h - A2.h) * home },
                    terminal: kf(t, [[1800, 1], [2020, 0]]),
                    right: hand(r, { alpha: leaving, pose: t >= 900 && t < 2400 ? 'fist' : 'open' }),
                    left: hand({ x: 150, y: 440 }, { alpha: leaving, idle: 1 }),
                    frame: t < 1800 ? { rect: TERMINAL, held: false } : null,
                    hold: t >= 1000 && t < 2150 ? { x: r.x, y: r.y, p: kf(t, [[1100, 0], [1800, 1, ease.linear]]), done: t >= 1800,
                                                    pop: kf(t, [[1800, 1], [1880, 1.16], [2000, 1]]), alpha: kf(t, [[1000, 0], [1100, 1], [2000, 1], [2150, 0]]) } : null,
                    pulse: pulseAt(t, 1800, r)
                };
            }
        }
    ];

    function div(className, parent, html) {
        const node = document.createElement('div');
        node.className = className;
        if (html) node.innerHTML = html;
        if (parent) parent.appendChild(node);
        return node;
    }
    function px(n) { return n.toFixed(2) + 'px'; }
    function box(node, rect, grow) {
        node.style.transform = 'translate(' + px(rect.x - grow) + ',' + px(rect.y - grow) + ')';
        node.style.width = px(rect.w + 2 * grow);
        node.style.height = px(rect.h + 2 * grow);
    }
    function icon(name) {
        return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="' + ICONS[name] + '"/></svg>';
    }

    function cursor(overlay, side) {
        const node = div('cur cur--' + side, overlay,
            '<div class="cur__ring"><div class="cur__dot"></div></div><div class="cur__tag">' + (side === 'l' ? 'L' : 'R') + '</div>');
        return function (s) {
            if (!s) { node.style.opacity = 0; return; }
            node.style.transform = 'translate(' + px(s.x) + ',' + px(s.y) + ')';
            node.style.opacity = s.alpha * (1 - 0.3 * s.idle);
            node.style.setProperty('--d', px(56 - 8 * s.pinch - 12 * s.idle));
            node.style.setProperty('--dot', px(26 * s.pinch));
            node.classList.toggle('is-pinching', s.pinch > 0.02);
        };
    }

    function pieMenu(overlay) {
        const half = Math.PI / PETALS.length;
        const sin = Math.sin(half), cos = Math.cos(half);
        const inner = 46, outer = 156;
        const wedge = 'M' + -inner * sin + ' ' + -inner * cos + ' L' + -outer * sin + ' ' + -outer * cos +
            ' A' + outer + ' ' + outer + ' 0 0 1 ' + outer * sin + ' ' + -outer * cos +
            ' L' + inner * sin + ' ' + -inner * cos + ' A' + inner + ' ' + inner + ' 0 0 0 ' + -inner * sin + ' ' + -inner * cos + ' Z';
        const arc = 'M' + -ORBIT * sin + ' ' + -ORBIT * cos + ' A' + ORBIT + ' ' + ORBIT + ' 0 0 1 ' + ORBIT * sin + ' ' + -ORBIT * cos;
        const node = div('pie', overlay,
            '<svg class="pie__lines" viewBox="-170 -170 340 340" aria-hidden="true">' +
            '<circle class="pie__orbit-ink" r="' + ORBIT + '"/><circle class="pie__orbit" r="' + ORBIT + '"/>' +
            '<g class="pie__aim"><path class="pie__wedge-ink" d="' + wedge + '"/><path class="pie__wedge" d="' + wedge + '"/>' +
            '<path class="pie__arc-key" d="' + arc + '"/><path class="pie__arc" d="' + arc + '"/></g></svg>');
        node.style.transform = 'translate(' + MENU.x + 'px,' + MENU.y + 'px)';
        const lines = node.querySelector('.pie__lines');
        const aimed = node.querySelector('.pie__aim');
        const petals = PETALS.map(function (petal) {
            return div('petal', node, '<div class="petal__face petal__face--' + petal[1] + '"><div class="petal__disc">' + icon(petal[0]) + '</div></div>');
        });
        const seed = div('pie__seed', node, '<div class="pie__word"></div><div class="pie__hint"></div>');
        const word = seed.querySelector('.pie__word'), hint = seed.querySelector('.pie__hint');
        let shownAim = null;

        return function (m) {
            node.style.display = m ? '' : 'none';
            if (!m) return;
            const shutting = m.shut >= 0;
            // The chosen petal pulses once, then every petal falls back into the seed.
            const wilt = shutting ? ease.inQuad(Math.min(1, Math.max(0, (m.shut - 120) / 160))) : 0;
            petals.forEach(function (petal, i) {
                const bloom = ease.outBack(Math.min(1, Math.max(0, (m.open - 40 * i) / 320))) * (1 - wilt);
                const turn = i * 2 * half;
                const reach = ORBIT * bloom;
                petal.style.transform = 'translate(' + px(reach * Math.sin(turn)) + ',' + px(-reach * Math.cos(turn)) + ') scale(' + (0.3 + 0.7 * bloom) + ')';
                petal.style.opacity = Math.min(1, m.open / 60) * (1 - wilt);
                petal.classList.toggle('is-aimed', i === m.aim);
                petal.classList.toggle('is-picked', shutting && i === m.aim && m.shut < 120);
            });
            const grown = ease.outBack(Math.min(1, m.open / 220));
            seed.style.transform = 'scale(' + grown + ')';
            seed.style.opacity = shutting ? 1 - Math.min(1, Math.max(0, (m.shut - 200) / 160)) : 1;
            lines.style.opacity = Math.min(1, m.open / 200) * (1 - wilt);
            aimed.style.opacity = m.aim < 0 ? 0 : 1;
            if (m.aim !== shownAim) {
                shownAim = m.aim;
                if (m.aim >= 0) aimed.style.transform = 'rotate(' + m.aim * 360 / PETALS.length + 'deg)';
                word.textContent = m.aim < 0 ? 'Menu' : PETALS[m.aim][2];
                hint.textContent = m.aim < 0 ? 'move to aim' : PETALS[m.aim][3];
            }
        };
    }

    HW.initDesk = function (root, controls) {
        const desk = root.querySelector('.desk__inner');
        const browser = desk.querySelector('[data-window="browser"]');
        const terminal = desk.querySelector('[data-window="terminal"]');
        const overlay = div('ov', desk);

        const ghost = div('ov-ghost', overlay);
        const frame = div('ov-frame', overlay, '<i></i><i></i><i></i><i></i>');
        const gripRight = div('ov-grip ov-grip--r', overlay), gripLeft = div('ov-grip ov-grip--l', overlay);
        const size = div('ov-chip ov-size', overlay);
        const drawMenu = pieMenu(overlay);
        const hold = div('ov-hold', overlay,
            '<svg viewBox="-60 -60 120 120" aria-hidden="true"><circle class="ov-hold__ink" r="46"/><circle class="ov-hold__track" r="46"/>' +
            '<circle class="ov-hold__arc" r="46" pathLength="100" transform="rotate(-90)"/></svg><div class="ov-chip">Close</div>');
        const holdArc = hold.querySelector('.ov-hold__arc');
        const pulse = div('ov-pulse', overlay);
        const drawLeft = cursor(overlay, 'l'), drawRight = cursor(overlay, 'r');

        // The two hands under the desktop show what each hand out in front of the camera is doing.
        const figures = {
            left: HW.Hand.figure({ side: 'left' }),
            right: HW.Hand.figure({ side: 'right' })
        };
        controls.hands.appendChild(figures.left.svg);
        controls.hands.appendChild(figures.right.svg);

        function draw(scene, t) {
            const s = scene.at(t);
            box(browser, s.a, 0);
            const shown = s.terminal || 0;
            terminal.style.opacity = Math.min(1, shown * 1.4);
            box(terminal, TERMINAL, 0);
            terminal.style.transform += ' scale(' + (0.86 + 0.14 * shown) + ')';

            frame.classList.toggle('is-on', !!s.frame);
            if (s.frame) {
                frame.classList.toggle('is-held', s.frame.held);
                box(frame, s.frame.rect, 5 - 3 * (s.squeeze || 0));
            }
            const sizing = s.resize;
            [ghost, gripRight, gripLeft, size].forEach(function (node) { node.classList.toggle('is-on', !!sizing); });
            if (sizing) {
                box(ghost, sizing, 0);
                gripRight.style.transform = 'translate(' + px(s.a.x + s.a.w) + ',' + px(s.a.y) + ')';
                gripLeft.style.transform = 'translate(' + px(s.a.x) + ',' + px(s.a.y + s.a.h) + ')';
                size.style.transform = 'translate(' + px(s.a.x + s.a.w / 2) + ',' + px(s.a.y + s.a.h + 4) + ') translate(-50%, -50%)';
                size.textContent = Math.round(s.a.w * 1.6) + ' × ' + Math.round(s.a.h * 1.6);
            }

            drawMenu(s.menu);

            hold.style.display = s.hold ? '' : 'none';
            if (s.hold) {
                hold.style.transform = 'translate(' + px(s.hold.x) + ',' + px(s.hold.y) + ') scale(' + s.hold.pop + ')';
                hold.style.opacity = s.hold.alpha;
                hold.classList.toggle('is-done', s.hold.done);
                holdArc.setAttribute('stroke-dasharray', 100 * s.hold.p + ' 100');
            }
            pulse.style.display = s.pulse ? '' : 'none';
            if (s.pulse) {
                pulse.style.transform = 'translate(' + px(s.pulse.x) + ',' + px(s.pulse.y) + ') scale(' + (1 + 0.6 * ease.outCubic(s.pulse.p)) + ')';
                pulse.style.opacity = 1 - s.pulse.p;
            }

            drawLeft(s.left);
            drawRight(s.right);
            figures.left.setPose(s.left ? s.left.pose : 'open');
            figures.right.setPose(s.right ? s.right.pose : 'open');
            figures.left.svg.classList.toggle('is-away', !s.left || s.left.alpha < 0.5);
            figures.right.svg.classList.toggle('is-away', !s.right || s.right.alpha < 0.5);
        }

        let index = 0, time = 0, last = null, playing = false, visible = true;
        const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        function caption() {
            const scene = SCENES[index];
            controls.title.textContent = scene.title;
            controls.pose.textContent = scene.pose;
            controls.how.textContent = scene.how;
            controls.tabs.forEach(function (tab) { tab.setAttribute('aria-pressed', tab.dataset.scene === scene.id); });
        }
        function tick(now) {
            const step = last === null ? 0 : Math.min(100, now - last);
            last = now;
            time += step;
            if (time >= SCENES[index].length) {
                time -= SCENES[index].length;
                index = (index + 1) % SCENES.length;
                caption();
            }
            draw(SCENES[index], time);
        }
        function run() {
            last = null;
            if (playing && visible) HW.ticker.add(tick);
            else HW.ticker.remove(tick);
        }
        function setPlaying(on) {
            playing = on;
            controls.toggle.setAttribute('aria-pressed', on);
            controls.toggle.querySelector('span').textContent = on ? 'Pause' : 'Play';
            run();
        }
        function go(id, t) {
            index = SCENES.findIndex(function (scene) { return scene.id === id; });
            time = t;
            caption();
            draw(SCENES[index], time);
        }
        controls.tabs.forEach(function (tab) {
            tab.addEventListener('click', function () {
                // Paused, a scene is shown at the moment that says most about it.
                const scene = SCENES.find(function (s) { return s.id === tab.dataset.scene; });
                go(scene.id, playing ? 0 : scene.still);
            });
        });
        controls.toggle.addEventListener('click', function () { setPlaying(!playing); });

        function fit() { desk.style.transform = 'scale(' + root.clientWidth / W + ')'; }
        new ResizeObserver(fit).observe(root);
        fit();
        new IntersectionObserver(function (entries) {
            visible = entries[0].isIntersecting;
            run();
        }).observe(root);

        if (calm) time = SCENES[0].still;
        caption();
        draw(SCENES[index], time);
        setPlaying(!calm);

        return {
            // Stop on one moment of one scene.
            show: function (id, t) {
                setPlaying(false);
                go(id, t);
            }
        };
    };
})();
