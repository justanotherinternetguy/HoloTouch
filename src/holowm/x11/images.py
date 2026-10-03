"""Window icons and scaled-down pictures of live windows, read from the X server."""

from __future__ import annotations

import io
import logging
import struct

import numpy as np
import xcffib
import xcffib.render as xr
import xcffib.xproto as xp

from holowm.core.actions import Pixels
from holowm.x11.conn import X11

log = logging.getLogger(__name__)

_ICON_MAX_LONGS = 1 << 21  # 8 MB of icon data at most
_INCLUDE_INFERIORS = 1
_REPEAT_PAD = 2
_Z_PIXMAP = 2
# Request opcodes, for the requests built by hand below.
_GET_PROPERTY = 20
_GET_IMAGE = 73
_SET_PICTURE_FILTER = 30


# xcffib turns reply payloads into Python lists one byte at a time, which is far too slow for
# images, so these two replies keep the payload as bytes.
class _ImageReply(xcffib.Reply):
    def __init__(self, unpacker):
        xcffib.Reply.__init__(self, unpacker)
        self.depth, self.visual = unpacker.unpack("=xB2x4xI20x")
        (self.data,) = unpacker.unpack(f"={self.length * 4}s")


class _ImageCookie(xcffib.Cookie):
    reply_type = _ImageReply


class _PropertyReply(xcffib.Reply):
    def __init__(self, unpacker):
        xcffib.Reply.__init__(self, unpacker)
        self.format, self.type, self.bytes_after, self.value_len = unpacker.unpack("=xB2x4xIII12x")
        (self.data,) = unpacker.unpack(f"={self.value_len * (self.format // 8)}s")


class _PropertyCookie(xcffib.Cookie):
    reply_type = _PropertyReply


def _fixed(value: float) -> int:
    return round(value * 65536)


def best_icon(data: bytes, size: int) -> Pixels | None:
    """Pick an image from _NET_WM_ICON data: the smallest one of at least `size`, else the largest."""
    longs = memoryview(data[: len(data) // 4 * 4]).cast("I")
    found, offset = [], 0
    while offset + 2 <= len(longs):
        w, h = longs[offset], longs[offset + 1]
        end = offset + 2 + w * h
        if w == 0 or h == 0 or end > len(longs):
            break
        found.append((w, h, offset + 2))
        offset = end
    if not found:
        return None
    big_enough = [f for f in found if min(f[0], f[1]) >= size]
    w, h, start = min(big_enough) if big_enough else max(found)
    return Pixels(w, h, data[start * 4 : (start + w * h) * 4])


class WindowImager:
    def __init__(self, x: X11):
        self.x = x
        self._render = None
        self._formats: dict[int, int] = {}  # visual -> picture format
        # Asked first, because a request to an extension the server lacks closes the connection.
        if not x.core.QueryExtension(6, "RENDER").reply().present:
            log.info("no RENDER extension, so the switcher will not show window pictures")
            return
        self._render = x.conn(xr.key)
        self._render.QueryVersion(0, 11).reply()
        for depth in self._render.QueryPictFormats().reply().screens[x.conn.pref_screen].depths:
            for visual in depth.visuals:
                self._formats[visual.visual] = visual.format

    def icon(self, win: int, size: int) -> Pixels | None:
        x = self.x
        request = struct.pack("=xB2xIIIII", 0, win, x.atom("_NET_WM_ICON"), xp.Atom.CARDINAL, 0, _ICON_MAX_LONGS)
        cookie = x.core.send_request(_GET_PROPERTY, io.BytesIO(request), _PropertyCookie, is_checked=True)
        reply = x.reply(cookie)
        if reply is None or reply.format != 32:
            return None
        return best_icon(reply.data, size)

    def _composited(self) -> bool:
        """Windows only keep their full contents off screen while a compositing manager runs."""
        atom = self.x.atom(f"_NET_WM_CM_S{self.x.conn.pref_screen}")
        return bool(self.x.core.GetSelectionOwner(atom).reply().owner)

    def _scale(self, source: int, region: tuple[int, int, int, int], w: int, h: int, free: list) -> int:
        """Draw a region of a picture into a new w x h pixmap and return that pixmap."""
        x, render = self.x, self._render
        left, top, region_w, region_h = region
        pixmap, target = x.conn.generate_id(), x.conn.generate_id()
        x.core.CreatePixmap(x.screen.root_depth, pixmap, x.root, w, h)
        render.CreatePicture(target, pixmap, self._formats[x.screen.root_visual], xr.CP.Repeat, [_REPEAT_PAD])
        render.SetPictureTransform(
            source,
            [_fixed(region_w / w), 0, _fixed(left), 0, _fixed(region_h / h), _fixed(top), 0, 0, _fixed(1)],
        )
        # Sent by hand: xcffib's SetPictureFilter appends a stray parameter the server rejects.
        render.send_request(_SET_PICTURE_FILTER, io.BytesIO(struct.pack("=xx2xIH2x", source, 8) + b"bilinear"))
        render.Composite(xr.PictOp.Src, source, 0, target, 0, 0, 0, 0, 0, 0, w, h)
        free.append((target, pixmap))
        return pixmap

    def thumbnails(
        self, sources: list[tuple[int, int, tuple[int, int, int, int]]], max_w: int, max_h: int
    ) -> dict[int, Pixels]:
        """Scaled pictures of mapped windows. Each source is (window, visual, crop x/y/w/h)."""
        x, render = self.x, self._render
        if render is None or x.screen.root_visual not in self._formats:
            return {}
        if not sources or not self._composited():
            return {}
        pending = []
        for win, visual, region in sources:
            source_format = self._formats.get(visual)
            if source_format is None or region[2] < 1 or region[3] < 1:
                continue
            scale = min(max_w / region[2], max_h / region[3], 1.0)
            w, h = max(round(region[2] * scale), 1), max(round(region[3] * scale), 1)
            # The server does the scaling, so only the small result crosses the socket.
            picture = x.conn.generate_id()
            render.CreatePicture(
                picture, win, source_format, xr.CP.Repeat | xr.CP.SubwindowMode, [_REPEAT_PAD, _INCLUDE_INFERIORS]
            )
            free: list[tuple[int, int]] = [(picture, 0)]
            # Bilinear filtering only averages 2x2 pixels, so shrink by exact halves first.
            while region[2] > 2 * w and region[3] > 2 * h:
                half_w, half_h = (region[2] + 1) // 2, (region[3] + 1) // 2
                self._scale(picture, region, half_w, half_h, free)
                picture, region = free[-1][0], (0, 0, half_w, half_h)
            pixmap = self._scale(picture, region, w, h, free)
            request = struct.pack("=xB2xIhhHHI", _Z_PIXMAP, pixmap, 0, 0, w, h, 0xFFFFFFFF)
            cookie = x.core.send_request(_GET_IMAGE, io.BytesIO(request), _ImageCookie, is_checked=True)
            pending.append((win, w, h, cookie))
            for used_picture, used_pixmap in free:
                render.FreePicture(used_picture)
                if used_pixmap:
                    x.core.FreePixmap(used_pixmap)
        x.conn.flush()
        result = {}
        for win, w, h, cookie in pending:
            reply = x.reply(cookie)
            if reply is not None and len(reply.data) >= w * h * 4:
                # The server leaves the fourth byte of each pixel at zero, which would read as
                # fully transparent, so make every pixel opaque.
                pixels = np.frombuffer(reply.data, dtype="<u4", count=w * h) | 0xFF000000
                result[win] = Pixels(w, h, pixels.astype("<u4").tobytes())
        return result
