// The illustrated hand of the control panel (src/holowm/panel/qml/HandFigure.qml), drawn as SVG:
// a palm and five capsule fingers on a 96-unit grid. Coral is the right hand and sky the left.
// Here a hand also turns from one pose into the next, rather than being swapped for it.
(function () {
    'use strict';

    const SVG = 'http://www.w3.org/2000/svg';

    function el(name, attrs, parent) {
        const node = document.createElementNS(SVG, name);
        for (const key in attrs) node.setAttribute(key, attrs[key]);
        if (parent) parent.appendChild(node);
        return node;
    }

    // One callback list on one animation frame, so that a page of small loops costs one timer.
    const subscribers = new Set();
    let frame = 0;
    function loop(now) {
        frame = 0;
        subscribers.forEach(function (fn) { fn(now); });
        if (subscribers.size) frame = requestAnimationFrame(loop);
    }
    const ticker = {
        add: function (fn) {
            subscribers.add(fn);
            if (!frame) frame = requestAnimationFrame(loop);
        },
        remove: function (fn) { subscribers.delete(fn); }
    };

    // Each finger from its knuckle to its tip, then the thumb: the same paths the panel draws.
    const FINGERS = {
        open: 'M37 52 L33 18 M46 52 L45 12 M55 52 L57 17 M63 54 L68 28 M35 68 L15 50',
        index: 'M37 52 L31 30 L21 38 M46 52 L45 12 M55 52 L57 17 M63 54 L68 28 M35 68 L19 43',
        aim: 'M37 52 L33 18 M46 52 L46 40 M55 52 L55 42 M63 54 L63 45 M35 68 L15 50',
        press: 'M37 52 L33 18 M46 52 L46 40 M55 52 L55 42 M63 54 L63 45 M35 68 L44 55',
        pinky: 'M37 52 L33 18 M46 52 L45 12 M55 52 L57 17 M63 54 L64 38 L47 43 M35 68 L43 49',
        fist: 'M37 52 L37 42 M46 52 L46 40 M55 52 L55 42 M63 54 L63 45 M35 68 L48 60',
        two: 'M37 52 L31 18 M46 52 L49 13 M55 52 L55 42 M63 54 L63 45 M35 68 L47 61',
        claw: 'M37 52 L30 33 M46 52 L45 28 M55 52 L60 32 M63 54 L72 41 M35 68 L19 58',
        peace: 'M37 52 L27 20 M46 52 L53 15 M55 52 L55 42 M63 54 L63 45 M35 68 L47 61',
        y: 'M37 52 L37 42 M46 52 L46 40 M55 52 L55 42 M63 54 L76 32 M35 68 L15 50',
        ily: 'M37 52 L33 18 M46 52 L46 40 M55 52 L55 42 M63 54 L76 32 M35 68 L15 50'
    };
    // Where the fingertips meet, in the poses where they do.
    const TOUCHES = { index: [20, 40], press: [46, 50], pinky: [45, 45] };
    const MORPH_MS = 150;

    // Every finger as knuckle, bend and tip (30 numbers a hand), so any pose can become any other.
    function parse(d) {
        const flat = [];
        d.split('M').slice(1).forEach(function (sub) {
            const n = sub.replace(/L/g, ' ').trim().split(/\s+/).map(Number);
            if (n.length === 4) n.splice(2, 0, (n[0] + n[2]) / 2, (n[1] + n[3]) / 2);
            flat.push.apply(flat, n);
        });
        return flat;
    }
    const POSES = {};
    for (const name in FINGERS) POSES[name] = parse(FINGERS[name]);

    function pathOf(p) {
        let d = '';
        for (let i = 0; i < 30; i += 6) {
            d += 'M' + p[i].toFixed(2) + ' ' + p[i + 1].toFixed(2) +
                'L' + p[i + 2].toFixed(2) + ' ' + p[i + 3].toFixed(2) +
                'L' + p[i + 4].toFixed(2) + ' ' + p[i + 5].toFixed(2);
        }
        return d;
    }

    function Hand(options) {
        options = options || {};
        this.side = options.side === 'left' ? 'left' : 'right';
        this.pose = POSES[options.pose] ? options.pose : 'open';
        this.g = el('g', {
            'class': 'hand' + (this.side === 'left' ? ' hand--left' : '') + (options.plain ? ' hand--plain' : '')
        });
        // The left hand is the right one mirrored.
        const inner = el('g', this.side === 'left' ? { transform: 'translate(96 0) scale(-1 1)' } : {}, this.g);
        const palm = { x: 31, y: 46, width: 36, height: 36, rx: 15 };
        this.under = el('path', { 'class': 'hand__ink' }, inner);
        el('rect', Object.assign({ 'class': 'hand__palm-ink' }, palm), inner);
        this.over = el('path', { 'class': 'hand__tone' }, inner);
        el('rect', Object.assign({ 'class': 'hand__palm' }, palm), inner);
        this.dot = el('circle', { 'class': 'hand__dot', r: 6.75 }, inner);

        this.points = POSES[this.pose].slice();
        this.touch = (TOUCHES[this.pose] || [46, 50]).slice();
        this.touching = TOUCHES[this.pose] ? 1 : 0;
        this.morph = null;
        this.step = this.step.bind(this);
        this.draw();
    }

    // Put the hand's 96-unit grid at x, y, `size` units across, turned by `turn` if given.
    Hand.prototype.place = function (x, y, size, turn) {
        let transform = 'translate(' + x + ' ' + y + ') scale(' + size / 96 + ')';
        if (turn) transform = 'rotate(' + turn.deg + ' ' + turn.x + ' ' + turn.y + ') ' + transform;
        this.g.setAttribute('transform', transform);
        return this;
    };

    Hand.prototype.draw = function () {
        const d = pathOf(this.points);
        this.under.setAttribute('d', d);
        this.over.setAttribute('d', d);
        this.dot.setAttribute('cx', this.touch[0]);
        this.dot.setAttribute('cy', this.touch[1]);
        this.dot.setAttribute('opacity', this.touching);
        this.dot.setAttribute('r', 6.75 * (0.4 + 0.6 * this.touching));
    };

    Hand.prototype.setPose = function (pose, instant) {
        if (!POSES[pose] || pose === this.pose) return;
        this.pose = pose;
        const touch = TOUCHES[pose];
        this.morph = {
            from: this.points.slice(), to: POSES[pose],
            // A dot that was not showing starts where it is going, so it does not slide in.
            touchFrom: this.touching > 0.05 ? this.touch.slice() : (touch || this.touch).slice(),
            touchTo: (touch || this.touch).slice(),
            touchingFrom: this.touching, touchingTo: touch ? 1 : 0,
            start: instant ? -Infinity : null
        };
        if (instant) this.step(0);
        else ticker.add(this.step);
    };

    Hand.prototype.step = function (now) {
        const m = this.morph;
        if (!m) return;
        if (m.start === null) m.start = now;
        const raw = Math.min(1, (now - m.start) / MORPH_MS);
        const p = 1 - Math.pow(1 - raw, 3);
        for (let i = 0; i < 30; i++) this.points[i] = m.from[i] + (m.to[i] - m.from[i]) * p;
        this.touch[0] = m.touchFrom[0] + (m.touchTo[0] - m.touchFrom[0]) * p;
        this.touch[1] = m.touchFrom[1] + (m.touchTo[1] - m.touchFrom[1]) * p;
        this.touching = m.touchingFrom + (m.touchingTo - m.touchingFrom) * p;
        this.draw();
        if (raw >= 1) {
            this.morph = null;
            ticker.remove(this.step);
        }
    };

    // A hand on its own, as an <svg> to put in the page.
    Hand.figure = function (options) {
        const hand = new Hand(options);
        hand.svg = el('svg', { viewBox: '0 0 96 96', 'class': 'figure', 'aria-hidden': 'true' });
        hand.svg.appendChild(hand.g);
        return hand;
    };

    window.HoloWM = { el: el, ticker: ticker, Hand: Hand, poses: Object.keys(POSES) };
})();
