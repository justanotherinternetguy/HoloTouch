// The looping demonstrations of the control panel's gesture guide
// (src/holotouch/panel/qml/GestureStage.qml), one for each gesture: an illustrated hand, and what it
// acts on. Each is drawn on a 170 by 104 unit stage and is a function of time alone.
(function () {
    'use strict';

    const HT = window.HoloTouch;
    const el = HT.el;

    const ease = {
        linear: function (p) { return p; },
        sine: function (p) { return 0.5 - Math.cos(Math.PI * p) / 2; },
        outCubic: function (p) { return 1 - Math.pow(1 - p, 3); },
        outBack: function (p) { const s = 1.70158; p -= 1; return p * p * ((s + 1) * p + s) + 1; },
        inQuad: function (p) { return p * p; },
        outQuad: function (p) { return p * (2 - p); }
    };

    // A value over a loop, written as the panel writes a SequentialAnimation:
    // ['p', ms] waits, ['to', value, ms, easing] moves, ['set', value] jumps.
    function track(start, steps) {
        let total = 0;
        steps.forEach(function (s) { total += s[0] === 'p' ? s[1] : s[0] === 'to' ? s[2] : 0; });
        return function (t) {
            t %= total;
            let value = start;
            let at = 0;
            for (let i = 0; i < steps.length; i++) {
                const s = steps[i];
                if (s[0] === 'set') { value = s[1]; continue; }
                const length = s[0] === 'p' ? s[1] : s[2];
                if (t < at + length) {
                    return s[0] === 'p' ? value : value + (s[1] - value) * (s[3] || ease.linear)((t - at) / length);
                }
                if (s[0] === 'to') value = s[1];
                at += length;
            }
            return value;
        };
    }

    // Swings a value back and forth.
    function sway(from, to, time, rest) {
        time = time || 1400;
        rest = rest === undefined ? 200 : rest;
        return track(from, [['to', to, time, ease.sine], ['p', rest], ['to', from, time, ease.sine], ['p', rest]]);
    }

    function about(cx, cy, scale) {
        return 'translate(' + cx + ' ' + cy + ') scale(' + scale + ') translate(' + -cx + ' ' + -cy + ')';
    }

    function Kit(svg) { this.svg = svg; }
    Kit.prototype.group = function (parent) { return el('g', {}, parent || this.svg); };
    Kit.prototype.pane = function (parent, x, y, w, h) {
        return el('rect', { 'class': 'st-pane', x: x, y: y, width: w || 56, height: h || 38, rx: 8 }, parent);
    };
    Kit.prototype.hand = function (parent, pose, x, y, size, side) {
        const hand = new HT.Hand({ pose: pose, side: side });
        parent.appendChild(hand.place(x, y, size).g);
        return hand;
    };
    // A ring that fills clockwise from twelve; returns the setter for how far, in degrees.
    Kit.prototype.ring = function (cx, cy, r, trackWidth, arcWidth) {
        el('circle', { 'class': 'st-ring', cx: cx, cy: cy, r: r, 'stroke-width': trackWidth }, this.svg);
        const arc = el('circle', {
            'class': 'st-arc', cx: cx, cy: cy, r: r, 'stroke-width': arcWidth, pathLength: 360,
            transform: 'rotate(-90 ' + cx + ' ' + cy + ')'
        }, this.svg);
        return function (sweep) { arc.setAttribute('stroke-dasharray', sweep + ' 360'); };
    };

    const ENTER = 'M19 6 L19 11 A3 3 0 0 1 16 14 L5 14 M9.5 9.5 L5 14 L9.5 18.5';

    const stages = {
        move: function (k) {
            const both = k.group();
            k.pane(both, 44, 36);
            k.hand(both, 'index', 59, 28, 64);
            const x = sway(-18, 18);
            return function (t) { both.setAttribute('transform', 'translate(' + x(t) + ' 0)'); };
        },

        resize: function (k) {
            const pane = k.pane(k.svg, 56, 34, 62, 40);
            const left = k.hand(k.svg, 'index', 17, 48, 52, 'left');
            const right = k.hand(k.svg, 'index', 105, 10, 52);
            const scale = sway(1, 1.26);
            const lx = sway(17, 8), ly = sway(48, 55), rx = sway(105, 114), ry = sway(10, 3);
            return function (t) {
                pane.setAttribute('transform', about(87, 54, scale(t)));
                left.place(lx(t), ly(t), 52);
                right.place(rx(t), ry(t), 52);
            };
        },

        flick: function (k) {
            el('rect', { 'class': 'st-bar', x: 18, y: 7, width: 134, height: 3, rx: 1.5 }, k.svg);
            const both = k.group();
            k.pane(both, 50, 40, 50, 34);
            k.hand(both, 'index', 63, 33, 58);
            const y = track(12, [['p', 1300], ['to', -22, 220, ease.outCubic], ['p', 700], ['to', 12, 400, ease.sine]]);
            return function (t) { both.setAttribute('transform', 'translate(0 ' + y(t) + ')'); };
        },

        edge: function (k) {
            el('rect', { 'class': 'st-ink', x: 160, y: 18, width: 20, height: 68, rx: 10 }, k.svg);
            const fill = el('rect', { 'class': 'st-butter', x: 160, width: 20, rx: 10 }, k.svg);
            const both = k.group();
            k.pane(both, 84, 36);
            k.hand(both, 'index', 106, 30, 58);
            const height = track(0, [['p', 1500], ['to', 68, 1300], ['p', 300], ['set', 0], ['p', 500]]);
            const x = track(-34, [['p', 300], ['to', 0, 1100, ease.sine], ['p', 1700], ['to', -34, 500, ease.sine]]);
            return function (t) {
                const h = height(t);
                fill.setAttribute('height', h);
                fill.setAttribute('y', 52 - h / 2);
                both.setAttribute('transform', 'translate(' + x(t) + ' 0)');
            };
        },

        // The thumb is held out to take aim, then comes down: the ripple leaves as it lands.
        click: function (k) {
            const ripple = el('circle', { 'class': 'st-ripple', cx: 84, cy: 53, r: 14 }, k.svg);
            const hand = k.hand(k.svg, 'press', 53, 20, 64);
            return function (t) {
                t %= 1700;
                const down = t >= 800;
                const p = down ? (t - 800) / 900 : 1;
                hand.setPose(down ? 'press' : 'aim');
                ripple.setAttribute('transform', about(84, 53, 0.4 + 1.6 * ease.outCubic(p)));
                ripple.setAttribute('opacity', 1 - p);
            };
        },

        menu: function (k) {
            k.hand(k.svg, 'pinky', 55, 30, 60);
            const buds = [[75, 14, 'butter'], [109, 38, 'lilac'], [97, 78, 'mint'], [53, 78, 'butter'], [41, 38, 'lilac']]
                .map(function (bud, i) {
                    return {
                        cx: bud[0] + 8, cy: bud[1] + 8,
                        node: el('circle', { 'class': 'st-bud st-' + bud[2], cx: bud[0] + 8, cy: bud[1] + 8, r: 8 }, k.svg),
                        scale: track(0, [['set', 0], ['p', 500 + 60 * i], ['to', 1, 280, ease.outBack],
                                         ['p', 1700 - 60 * i], ['to', 0, 160]])
                    };
                });
            return function (t) {
                buds.forEach(function (b) { b.node.setAttribute('transform', about(b.cx, b.cy, b.scale(t))); });
            };
        },

        close: function (k) {
            const fill = k.ring(85, 52, 36, 9, 7);
            k.hand(k.svg, 'fist', 55, 16, 60);
            const sweep = track(1, [['p', 400], ['to', 360, 2000], ['p', 500], ['set', 1]]);
            return function (t) { fill(sweep(t)); };
        },

        scroll: function (k) {
            const hand = k.hand(k.svg, 'two', 53, 20, 64);
            const tilt = sway(0, 18, 1000);
            return function (t) { hand.place(53, 20, 64, { deg: tilt(t), x: 85, y: 84 }); };
        },

        knob: function (k) {
            const hand = k.hand(k.svg, 'claw', 53, 20, 64);
            const turn = sway(-18, 24, 1200);
            return function (t) { hand.place(53, 20, 64, { deg: turn(t), x: 85, y: 52 }); };
        },

        // The open hand is swept to the right, and the Enter key goes down as it gets there.
        swipe: function (k) {
            const key = k.group();
            el('rect', { 'class': 'st-pane', x: 14, y: 60, width: 34, height: 30, rx: 8 }, key);
            el('path', { 'class': 'st-icon', d: ENTER, transform: 'translate(22 66) scale(0.75)' }, key);
            const hand = k.hand(k.svg, 'open', 30, 12, 62);
            const press = track(1, [['p', 1150], ['to', 0.8, 90], ['to', 1, 220, ease.outBack], ['p', 1260]]);
            const x = track(30, [['p', 900], ['to', 100, 320, ease.outCubic], ['p', 900], ['to', 30, 600, ease.sine]]);
            return function (t) {
                key.setAttribute('transform', about(31, 75, press(t)));
                hand.place(x(t), 12, 62);
            };
        },

        // A chin, and a fist coming up to it.
        switcher: function (k) {
            el('circle', { 'class': 'st-chin', cx: 85, cy: -14, r: 34 }, k.svg);
            const hand = k.hand(k.svg, 'fist', 55, 44, 60);
            const y = track(44, [['p', 700], ['to', 6, 600, ease.outCubic], ['p', 1100], ['to', 44, 500, ease.sine]]);
            return function (t) { hand.place(55, y(t), 60); };
        },

        camera: function (k) {
            k.hand(k.svg, 'peace', 2, 24, 62, 'left');
            k.hand(k.svg, 'peace', 106, 24, 62);
            const fill = k.ring(85, 52, 17, 7, 6);
            const sweep = track(1, [['p', 400], ['to', 360, 2400], ['p', 500], ['set', 1]]);
            return function (t) { fill(sweep(t)); };
        },

        // The sign is held and words come; it is dropped, and they are in the text box.
        dictate: function (k) {
            k.hand(k.svg, 'y', 4, 22, 62);
            k.pane(k.svg, 72, 34, 88, 36);
            let x = 82;
            const words = [14, 9, 17, 11].map(function (width) {
                const word = { end: x + width + 4, node: el('rect', { 'class': 'st-ink', x: x, y: 49, width: width, height: 6, rx: 3 }, k.svg) };
                x = word.end;
                return word;
            });
            const caret = el('rect', { 'class': 'st-caret', y: 44, width: 2.5, height: 16 }, k.svg);
            const said = track(0, [['set', 0], ['p', 500], ['to', 1, 1500], ['p', 1200]]);
            return function (t) {
                const now = said(t) * 4;
                let at = 82;
                words.forEach(function (word, i) {
                    const shown = now > i + 0.5;
                    word.node.setAttribute('visibility', shown ? 'visible' : 'hidden');
                    if (shown) at = word.end;
                });
                caret.setAttribute('x', at);
            };
        },

        // The sign is held up, and the letters come one after the other.
        spell: function (k) {
            k.hand(k.svg, 'ily', 4, 22, 62);
            const tiles = ['R', 'S'].map(function (letter, i) {
                const x = 82 + 38 * i;
                const tile = el('rect', { 'class': 'st-tile', x: x, y: 36, width: 32, height: 34, rx: 8 }, k.svg);
                const text = el('text', { 'class': 'st-letter', x: x + 16, y: 53.5 }, k.svg);
                text.textContent = letter;
                return { tile: tile, text: text };
            });
            return function (t) {
                t %= 2800;
                const taken = t < 700 ? 0 : t < 1400 ? 1 : 2;
                tiles.forEach(function (it, i) {
                    it.tile.setAttribute('class', 'st-tile' + (taken > i ? (taken >= 2 ? ' is-done' : ' is-taken') : ''));
                    it.text.setAttribute('visibility', taken > i ? 'visible' : 'hidden');
                });
            };
        },

        // The hands meet twice, and a tab is added to the row of them.
        clap: function (k) {
            const tabs = [0, 1, 2].map(function (i) {
                return el('rect', { 'class': 'st-pane' + (i === 2 ? ' st-mint' : ''), x: 43 + 30 * i, y: 8, width: 26, height: 14, rx: 5 }, k.svg);
            });
            const left = k.hand(k.svg, 'open', 6, 34, 60, 'left');
            const right = k.hand(k.svg, 'open', 104, 34, 60);
            const apart = track(1, [['p', 500], ['to', 0, 130, ease.inQuad], ['to', 1, 190, ease.outQuad],
                                    ['to', 0, 130, ease.inQuad], ['to', 1, 190, ease.outQuad], ['p', 1500]]);
            return function (t) {
                const a = apart(t);
                left.place(28 - 22 * a, 34, 60);
                right.place(82 + 22 * a, 34, 60);
                tabs[2].setAttribute('visibility', t % 2640 >= 950 ? 'visible' : 'hidden');
            };
        },

        // The open hand is tossed upward from rest, and the page turns up on the phone.
        toss: function (k) {
            const phone = el('rect', { 'class': 'st-pane', x: 118, y: 22, width: 34, height: 58, rx: 9 }, k.svg);
            el('rect', { 'class': 'st-ink', x: 130, y: 70, width: 10, height: 2.5, rx: 1.25 }, k.svg);
            const hand = k.hand(k.svg, 'open', 34, 40, 60);
            const y = track(40, [['p', 900], ['to', 2, 300, ease.outCubic], ['p', 1100], ['to', 40, 600, ease.sine]]);
            return function (t) {
                hand.place(34, y(t), 60);
                phone.setAttribute('class', t % 2900 >= 1200 ? 'st-pane st-mint' : 'st-pane');
            };
        }
    };

    // Draw `gesture` into `slot`. Returns what sets the stage to a time in milliseconds.
    function mountStage(slot, gesture) {
        const svg = el('svg', { 'class': 'stage', viewBox: '0 0 170 104', 'aria-hidden': 'true' }, slot);
        const update = (stages[gesture] || stages.move)(new Kit(svg));
        update(0);
        return update;
    }

    HT.ease = ease;
    HT.mountStage = mountStage;
})();
