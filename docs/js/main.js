// Wires the page together: the desktop at the top, the gesture guide, the hand shapes, and the
// small conveniences round them.
(function () {
    'use strict';

    const HT = window.HoloTouch;
    const calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const all = function (selector) { return Array.from(document.querySelectorAll(selector)); };
    const byId = function (id) { return document.getElementById(id); };

    function press(buttons, chosen) {
        buttons.forEach(function (button) { button.setAttribute('aria-pressed', button === chosen); });
    }

    // Hands written into the page as <div data-hand="index" data-side="left">.
    all('[data-hand]').forEach(function (slot) {
        slot.appendChild(HT.Hand.figure({ pose: slot.dataset.hand, side: slot.dataset.side }).svg);
    });

    HT.desk = HT.initDesk(document.querySelector('.desk'), {
        hands: byId('now-hands'), title: byId('now-title'), pose: byId('now-pose'), how: byId('now-how'),
        tabs: all('[data-scene]'), toggle: byId('desk-toggle')
    });

    // The gesture guide. A stage plays only while it is on screen; with reduced motion asked for,
    // each holds the moment that says most about it.
    const STILLS = { edge: 2200, click: 900, menu: 1500, close: 1500, camera: 1700, dictate: 1900, spell: 1500, swipe: 1200, switcher: 1600 };
    const players = new Map();
    const watcher = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            const play = players.get(entry.target);
            if (entry.isIntersecting) HT.ticker.add(play);
            else HT.ticker.remove(play);
        });
    }, { rootMargin: '60px' });
    all('[data-gesture]').forEach(function (slot) {
        const update = HT.mountStage(slot, slot.dataset.gesture);
        if (calm) {
            update(STILLS[slot.dataset.gesture] || 0);
            return;
        }
        let start = null;
        players.set(slot, function (now) {
            if (start === null) start = now;
            update(now - start);
        });
        watcher.observe(slot);
    });

    const filters = all('[data-filter]');
    const cards = all('.gcard');
    filters.forEach(function (button) {
        button.addEventListener('click', function () {
            press(filters, button);
            cards.forEach(function (card) {
                card.hidden = button.dataset.filter !== 'all' && card.dataset.kind !== button.dataset.filter;
            });
        });
    });

    // The hand shapes: one large hand that turns into whichever shape is picked. Until someone
    // picks one it goes through them by itself.
    const well = byId('shape-hand');
    const figures = { left: HT.Hand.figure({ side: 'left' }), right: HT.Hand.figure({ side: 'right' }) };
    well.appendChild(figures.left.svg);
    well.appendChild(figures.right.svg);
    const shapes = all('[data-shape]');
    const sides = all('[data-shape-side]');
    const note = byId('shape-note');
    function showSide(side) {
        figures.left.svg.style.display = side === 'left' ? '' : 'none';
        figures.right.svg.style.display = side === 'right' ? '' : 'none';
    }
    function showShape(button) {
        press(shapes, button);
        figures.left.setPose(button.dataset.shape);
        figures.right.setPose(button.dataset.shape);
        note.textContent = button.dataset.note;
    }
    showSide('right');
    let touring = calm ? 0 : setInterval(function () {
        const at = shapes.findIndex(function (button) { return button.getAttribute('aria-pressed') === 'true'; });
        showShape(shapes[(at + 1) % shapes.length]);
    }, 1800);
    function stopTour() {
        clearInterval(touring);
        touring = 0;
    }
    shapes.forEach(function (button) {
        button.addEventListener('click', function () {
            stopTour();
            showShape(button);
        });
    });
    sides.forEach(function (button) {
        button.addEventListener('click', function () {
            press(sides, button);
            showSide(button.dataset.shapeSide);
        });
    });

    const copy = byId('copy');
    copy.addEventListener('click', function () {
        const text = byId('commands').textContent.replace(/^\$ /gm, '');
        navigator.clipboard.writeText(text).then(function () {
            copy.textContent = 'Copied';
            setTimeout(function () { copy.textContent = 'Copy'; }, 1600);
        }, function () {
            copy.textContent = 'Select and copy';
        });
    });

    const nav = document.querySelector('.nav');
    const scrolled = function () { nav.classList.toggle('is-scrolled', window.scrollY > 8); };
    window.addEventListener('scroll', scrolled, { passive: true });
    scrolled();
})();
