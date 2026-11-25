"""Small charts for the dashboard, drawn with QPainter (no extra package needed).

- BarChart:   stacked bars, one per day, with gridlines and a hover tooltip.
- DonutChart: a ring split by category with the total in the middle.
- ColorDot:   the little coloured circle used in legends.

Colours come from theme.py, so the charts follow the rest of the app.
"""
import math

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from ui.theme import COLORS


def nice_step(top):
    """A tidy gridline step (1, 2, 5, 10, 20, 50, ...) so four steps cover `top`."""
    raw = max(top, 1) / 4
    magnitude = 10 ** math.floor(math.log10(raw))
    for factor in (1, 2, 5, 10):
        if raw <= factor * magnitude:
            return max(1, round(factor * magnitude))
    return max(1, round(10 * magnitude))


def small_font(widget, pixels=11, bold=False):
    font = QFont(widget.font())
    font.setPixelSize(pixels)
    font.setBold(bold)
    return font


class ColorDot(QWidget):
    """A small filled circle, for legends."""

    def __init__(self, color, size=10):
        super().__init__()
        self.color = QColor(color)
        self.setFixedSize(size, size)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.color)
        painter.drawEllipse(self.rect())


class BarChart(QWidget):
    """Stacked bars. series = [(key, label, color), ...] (bottom to top).

    set_data takes one entry per bar:
        {"label": "Mon", "title": "Mon, Nov 24", "values": {"emails": 2, ...}}"""

    def __init__(self, series):
        super().__init__()
        self.series = series
        self.days = []
        self.hover = -1
        self.plot = QRectF()
        self.setMouseTracking(True)
        self.setMinimumHeight(170)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_data(self, days):
        self.days = list(days)
        self.hover = -1
        self.update()

    def total(self, day):
        return sum(day["values"].get(key, 0) for key, _label, _color in self.series)

    # ---------- Drawing ----------

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        font = small_font(self)
        painter.setFont(font)
        metrics = QFontMetrics(font)

        totals = [self.total(day) for day in self.days]
        step = nice_step(max(totals, default=0))
        top = step * 4
        left = metrics.horizontalAdvance(str(top)) + 14
        bottom = metrics.height() + 10
        self.plot = plot = QRectF(left, 6, self.width() - left - 6,
                                  self.height() - bottom - 6)

        # Gridlines and the numbers on the left
        for i in range(5):
            y = plot.bottom() - plot.height() * i / 4
            painter.setPen(QPen(QColor(COLORS["border"]), 1))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(QColor(COLORS["muted"]))
            painter.drawText(QRectF(0, y - 8, left - 8, 16),
                             Qt.AlignRight | Qt.AlignVCenter, str(step * i))

        count = max(len(self.days), 1)
        slot = plot.width() / count
        bar_width = min(40.0, slot * 0.5)

        for i, day in enumerate(self.days):
            x = plot.left() + slot * i
            if i == self.hover:                     # a soft band behind the hovered day
                painter.fillRect(QRectF(x + 2, plot.top(), slot - 4, plot.height()),
                                 QColor(COLORS["soft"]))

            height = plot.height() * totals[i] / top
            if height > 0:
                bar = QRectF(x + (slot - bar_width) / 2, plot.bottom() - height,
                             bar_width, height)
                path = QPainterPath()
                path.addRoundedRect(bar, 4, 4)
                painter.save()
                painter.setClipPath(path)           # rounded ends, flat joins inside
                y = plot.bottom()
                for key, _label, color in self.series:
                    value = day["values"].get(key, 0)
                    if value:
                        segment = plot.height() * value / top
                        painter.fillRect(QRectF(bar.left(), y - segment, bar_width, segment),
                                         QColor(color))
                        y -= segment
                painter.restore()

            painter.setPen(QColor(COLORS["text"] if i == len(self.days) - 1
                                  else COLORS["muted"]))
            painter.drawText(QRectF(x, plot.bottom() + 5, slot, metrics.height() + 2),
                             Qt.AlignHCenter | Qt.AlignTop, day["label"])

        if not any(totals):
            painter.setPen(QColor(COLORS["muted"]))
            painter.drawText(plot, Qt.AlignCenter, "No activity in the last 7 days")

    # ---------- Hover ----------

    def day_at(self, x):
        if not self.days or self.plot.width() <= 0:
            return -1
        index = int((x - self.plot.left()) / (self.plot.width() / len(self.days)))
        return index if 0 <= index < len(self.days) else -1

    def mouseMoveEvent(self, event):
        index = self.day_at(event.position().x())
        if index != self.hover:
            self.hover = index
            self.update()
        if index < 0:
            QToolTip.hideText()
            return
        day = self.days[index]
        lines = [day["title"]]
        for key, label, _color in self.series:
            lines.append(f"{label}: {day['values'].get(key, 0)}")
        QToolTip.showText(event.globalPosition().toPoint(), "\n".join(lines), self)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.hover = -1
        QToolTip.hideText()
        self.update()


class DonutChart(QWidget):
    """A ring split by category, with the total in the middle.

    set_data takes [(label, value, color), ...]."""

    def __init__(self):
        super().__init__()
        self.items = []
        self.setMinimumSize(150, 150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_data(self, items):
        self.items = list(items)
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height()) - 8
        if side <= 0:
            return
        thickness = side * 0.15
        ring = QRectF((self.width() - side) / 2, (self.height() - side) / 2,
                      side, side).adjusted(thickness / 2, thickness / 2,
                                           -thickness / 2, -thickness / 2)

        total = sum(value for _label, value, _color in self.items)
        pen = QPen(QColor(COLORS["border"]), thickness)
        pen.setCapStyle(Qt.FlatCap)
        if total == 0:
            painter.setPen(pen)
            painter.drawEllipse(ring)
        else:
            shown = [item for item in self.items if item[1] > 0]
            gap = 16 * 2 if len(shown) > 1 else 0         # a thin gap between slices
            start = 90 * 16                               # start at 12 o'clock
            for _label, value, color in shown:
                span = -round(360 * 16 * value / total)
                pen.setColor(QColor(color))
                painter.setPen(pen)
                painter.drawArc(ring, start, min(span + gap, 0) if gap else span)
                start += span

        painter.setPen(QColor(COLORS["text"]))
        painter.setFont(small_font(self, max(18, int(side * 0.2)), bold=True))
        center = QRectF(self.rect())
        painter.drawText(center.adjusted(0, -10, 0, -10), Qt.AlignCenter, str(total))
        painter.setPen(QColor(COLORS["muted"]))
        painter.setFont(small_font(self, 11))
        label_rect = QRectF(center.left(), center.center().y() + side * 0.07,
                            center.width(), 16)
        painter.drawText(label_rect, Qt.AlignHCenter | Qt.AlignTop, "in total")
