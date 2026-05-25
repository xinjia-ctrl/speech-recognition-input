from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QMenu, QWidget


class FloatingVoiceBall(QWidget):
    toggle_requested = Signal()
    panel_requested = Signal()
    insert_requested = Signal()
    close_requested = Signal()
    quit_requested = Signal()
    moved = Signal()

    COLORS = {
        "idle": "#AAAAAA",
        "listening": "#FF4136",
        "processing": "#FF851B",
        "error": "#FFDC00",
        "success": "#2ECC40",
    }

    def __init__(self) -> None:
        super().__init__()
        self._drag_start: QPoint | None = None
        self._dragging = False
        self._close_pressed = False
        self._state = "idle"
        self._level = 0.0
        self._click_timer = QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self.toggle_requested.emit)
        self.setWindowTitle("XinVoice")
        self.setFixedSize(60, 60)
        self.setToolTip("单击开始/停止录音，右上角关闭，拖动移动，右键打开菜单")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName("floatingVoiceBall")
        self.set_state("idle", "待机", "点击开始语音输入")

    def set_state(
        self,
        state: str,
        title: str,
        preview: str,
        can_insert: bool = False,
    ) -> None:
        self._state = state
        self.update()

    def set_audio_level(self, level: float) -> None:
        self._level = min(max(level, 0.0), 1.0)
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(self.COLORS.get(self._state, self.COLORS["idle"])))
        painter.setPen(QPen(QColor("#111827"), 3))
        rect = self.rect().adjusted(4, 4, -4, -4)
        painter.drawEllipse(rect)
        self._draw_recorder_icon(painter)
        if self._state in {"listening", "success"}:
            self._draw_waveform(painter)
        self._draw_close_button(painter)

    def _draw_recorder_icon(self, painter: QPainter) -> None:
        painter.setPen(QPen(QColor("#111827"), 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        center_x = self.width() // 2
        painter.drawRoundedRect(center_x - 7, 16, 14, 18, 7, 7)
        painter.drawLine(center_x - 12, 27, center_x - 12, 30)
        painter.drawArc(center_x - 13, 21, 26, 20, 200 * 16, 140 * 16)
        painter.drawLine(center_x, 35, center_x, 42)
        painter.drawLine(center_x - 8, 42, center_x + 8, 42)

    def _draw_close_button(self, painter: QPainter) -> None:
        rect = self._close_rect()
        painter.setBrush(QColor("#111827"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 6, 6)
        painter.setPen(QPen(QColor("#ffffff"), 1))
        painter.drawLine(rect.left() + 4, rect.top() + 4, rect.right() - 4, rect.bottom() - 4)
        painter.drawLine(rect.right() - 4, rect.top() + 4, rect.left() + 4, rect.bottom() - 4)

    def _close_rect(self) -> QRect:
        return QRect(self.width() - 18, 2, 14, 14)

    def _draw_waveform(self, painter: QPainter) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#111827"))
        center_x = self.width() // 2
        base_y = 51
        bar_width = 2
        gap = 3
        levels = [0.45, 0.75, 1.0, 0.75, 0.45]
        for index, factor in enumerate(levels):
            height = 3 + int(self._level * 12 * factor)
            x = center_x - 2 * (bar_width + gap) + index * (bar_width + gap)
            y = base_y - height // 2
            painter.drawRoundedRect(x, y, bar_width, height, 2, 2)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._close_rect().contains(event.position().toPoint()):
                self._close_pressed = True
                event.accept()
                return
            self._drag_start = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._dragging = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_start is not None:
            self._dragging = True
            self.move(event.globalPosition().toPoint() - self._drag_start)
            self.moved.emit()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._close_pressed:
            self._close_pressed = False
            if self._close_rect().contains(event.position().toPoint()):
                self.close_requested.emit()
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and not self._dragging:
            self._drag_start = None
            self._click_timer.start(180)
            event.accept()
            return
        self._drag_start = None
        self._dragging = False
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        menu = QMenu(self)
        show_action = menu.addAction("打开面板")
        record_action = menu.addAction("开始/停止录音")
        insert_action = menu.addAction("插入预览文本")
        menu.addSeparator()
        quit_action = menu.addAction("退出")
        action = menu.exec(event.globalPos())
        if action == show_action:
            self.panel_requested.emit()
        elif action == record_action:
            self.toggle_requested.emit()
        elif action == insert_action:
            self.insert_requested.emit()
        elif action == quit_action:
            self.quit_requested.emit()
