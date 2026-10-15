"""
SysPulse Cairo-Based Graph Drawing Engine
Native GTK 4 Cairo rendering for lightweight, high-performance real-time charts.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import cairo
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from syspulse.utils import format_bytes


class CairoGraph(Gtk.DrawingArea):
    """
    Real-time area and line graph widget rendered with Cairo in GTK 4.
    Supports single or dual series, auto-scaling or fixed ranges, grid lines, and gradients.
    """

    def __init__(
        self,
        title: str = "",
        unit: str = "%",
        fixed_max: Optional[float] = 100.0,
        primary_color: Tuple[float, float, float] = (0.24, 0.65, 0.95),  # Accent blue
        secondary_color: Optional[Tuple[float, float, float]] = None,      # Optional 2nd series
        primary_label: str = "Usage",
        secondary_label: str = "",
        is_rate: bool = False,
    ) -> None:
        super().__init__()
        self.title = title
        self.unit = unit
        self.fixed_max = fixed_max
        self.primary_color = primary_color
        self.secondary_color = secondary_color
        self.primary_label = primary_label
        self.secondary_label = secondary_label
        self.is_rate = is_rate

        self.primary_data: List[float] = []
        self.secondary_data: List[float] = []
        self.current_primary: float = 0.0
        self.current_secondary: float = 0.0

        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_content_height(140)
        self.set_content_width(260)
        self.set_draw_func(self._on_draw, None)

    def update_data(
        self,
        primary_series: List[float],
        secondary_series: Optional[List[float]] = None,
    ) -> None:
        """Update data series and schedule a repaint on the GTK main thread."""
        self.primary_data = primary_series
        self.current_primary = primary_series[-1] if primary_series else 0.0

        if secondary_series is not None:
            self.secondary_data = secondary_series
            self.current_secondary = secondary_series[-1] if secondary_series else 0.0
        else:
            self.secondary_data = []
            self.current_secondary = 0.0

        self.queue_draw()

    def _format_val(self, val: float) -> str:
        if self.is_rate:
            return format_bytes(val, rate=True)
        if self.unit == "%":
            return f"{val:.1f}%"
        return f"{val:.1f} {self.unit}"

    def _on_draw(
        self,
        _drawing_area: Gtk.DrawingArea,
        cr: cairo.Context,
        width: int,
        height: int,
        _user_data: object,
    ) -> None:
        padding_top = 34
        padding_bottom = 22
        padding_left = 12
        padding_right = 12

        plot_w = max(10, width - padding_left - padding_right)
        plot_h = max(10, height - padding_top - padding_bottom)

        # 1. Background Card
        cr.save()
        radius = 8.0
        # Draw rounded rectangle for chart card
        x0 = 0.5
        y0 = 0.5
        w0 = width - 1.0
        h0 = height - 1.0
        cr.new_sub_path()
        cr.arc(x0 + w0 - radius, y0 + radius, radius, -1.5707963, 0)
        cr.arc(x0 + w0 - radius, y0 + h0 - radius, radius, 0, 1.5707963)
        cr.arc(x0 + radius, y0 + h0 - radius, radius, 1.5707963, 3.1415926)
        cr.arc(x0 + radius, y0 + radius, radius, 3.1415926, 4.7123889)
        cr.close_path()

        # Dark card background (#18181f)
        cr.set_source_rgb(0.094, 0.094, 0.122)
        cr.fill_preserve()
        # Card border (#2c2c38)
        cr.set_source_rgb(0.172, 0.172, 0.220)
        cr.set_line_width(1.0)
        cr.stroke()
        cr.restore()

        # 2. Header Text (Title & Current Values)
        cr.save()
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(12.0)
        cr.set_source_rgb(0.85, 0.87, 0.92)  # Light header
        cr.move_to(padding_left, 20)
        cr.show_text(self.title)

        # Legend and live reading
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(11.0)

        # Draw Secondary Legend if present
        offset_x = width - padding_right
        if self.secondary_color and self.secondary_data:
            txt_sec = f"{self.secondary_label}: {self._format_val(self.current_secondary)}"
            extents = cr.text_extents(txt_sec)
            offset_x -= extents.x_advance
            cr.set_source_rgb(*self.secondary_color)
            cr.move_to(offset_x, 20)
            cr.show_text(txt_sec)
            offset_x -= 16

        # Draw Primary Legend
        lbl_p = f"{self.primary_label}: {self._format_val(self.current_primary)}"
        extents_p = cr.text_extents(lbl_p)
        offset_x -= extents_p.x_advance
        cr.set_source_rgb(*self.primary_color)
        cr.move_to(offset_x, 20)
        cr.show_text(lbl_p)
        cr.restore()

        # 3. Compute Max Scale
        if self.fixed_max is not None:
            max_val = max(1.0, float(self.fixed_max))
        else:
            # Auto-scale with minimum floor
            observed = 0.0
            if self.primary_data:
                observed = max(observed, max(self.primary_data))
            if self.secondary_data:
                observed = max(observed, max(self.secondary_data))
            # Pad by 20%
            max_val = max(1024.0 if self.is_rate else 10.0, observed * 1.2)

        # 4. Grid Lines (3 subtle dashed lines)
        cr.save()
        cr.set_line_width(0.8)
        cr.set_source_rgba(0.24, 0.25, 0.32, 0.6)
        cr.set_dash([4.0, 4.0])

        for step in (0.25, 0.5, 0.75):
            y_pos = padding_top + plot_h * (1.0 - step)
            cr.move_to(padding_left, y_pos)
            cr.line_to(padding_left + plot_w, y_pos)
            cr.stroke()
        cr.restore()

        # 5. Draw Primary Series
        if self.primary_data:
            self._render_series(
                cr,
                self.primary_data,
                max_val,
                padding_left,
                padding_top,
                plot_w,
                plot_h,
                self.primary_color,
                fill=True,
            )

        # 6. Draw Secondary Series
        if self.secondary_color and self.secondary_data:
            self._render_series(
                cr,
                self.secondary_data,
                max_val,
                padding_left,
                padding_top,
                plot_w,
                plot_h,
                self.secondary_color,
                fill=True,
            )

        # 7. Bottom Scale Indicator (0 to Max)
        cr.save()
        cr.set_font_size(9.0)
        cr.set_source_rgb(0.50, 0.52, 0.60)
        cr.move_to(padding_left, height - 8)
        cr.show_text("60s ago")

        max_lbl = self._format_val(max_val)
        ext_max = cr.text_extents(max_lbl)
        cr.move_to(width - padding_right - ext_max.x_advance, height - 8)
        cr.show_text(max_lbl)
        cr.restore()

    def _render_series(
        self,
        cr: cairo.Context,
        data: List[float],
        max_val: float,
        x_start: float,
        y_start: float,
        w: float,
        h: float,
        color: Tuple[float, float, float],
        fill: bool = True,
    ) -> None:
        n = len(data)
        if n < 2:
            return

        dx = w / float(n - 1)
        points: List[Tuple[float, float]] = []

        for i, val in enumerate(data):
            norm = max(0.0, min(val / max_val, 1.0))
            px = x_start + i * dx
            py = y_start + h * (1.0 - norm)
            points.append((px, py))

        # Fill path with vertical gradient
        if fill:
            cr.save()
            cr.new_path()
            cr.move_to(points[0][0], y_start + h)
            for px, py in points:
                cr.line_to(px, py)
            cr.line_to(points[-1][0], y_start + h)
            cr.close_path()

            # Gradient: top color to transparent bottom
            grad = cairo.LinearGradient(0, y_start, 0, y_start + h)
            r, g, b = color
            grad.add_color_stop_rgba(0.0, r, g, b, 0.35)
            grad.add_color_stop_rgba(1.0, r, g, b, 0.02)
            cr.set_source(grad)
            cr.fill()
            cr.restore()

        # Stroke line path
        cr.save()
        cr.new_path()
        cr.move_to(points[0][0], points[0][1])
        for px, py in points[1:]:
            cr.line_to(px, py)

        cr.set_source_rgb(*color)
        cr.set_line_width(2.0)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.stroke()
        cr.restore()
