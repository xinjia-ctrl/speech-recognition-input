from __future__ import annotations


MAIN_WINDOW_STYLE = """
QMainWindow {
    background: #f4f6f8;
}
QTabWidget::pane {
    border: none;
    border-radius: 10px;
    background: #ffffff;
    top: 8px;
}
QTabWidget::tab-bar {
    left: 0;
}
QTabBar {
    background: #e9eef6;
    border: 1px solid #d7dfeb;
    border-radius: 11px;
    padding: 3px;
}
QTabBar::tab {
    min-width: 62px;
    padding: 7px 12px;
    color: #586276;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    margin: 0;
}
QTabBar::tab:selected {
    color: #1d4ed8;
    background: #ffffff;
    border: 1px solid #c8d4e6;
    font-weight: 700;
}
QTabBar::tab:hover:!selected {
    color: #243044;
    background: #f5f7fb;
}
QScrollArea {
    border: none;
    background: #ffffff;
}
QScrollArea > QWidget > QWidget#settingsPage {
    background: #ffffff;
}
QScrollBar:vertical {
    width: 10px;
    background: #f3f6fa;
    margin: 4px 2px 4px 2px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    min-height: 32px;
    background: #c7d0df;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #aeb9ca;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}
QLabel#configHintLabel {
    color: #92400e;
    background: #fffbeb;
    border: 1px solid #fde68a;
    border-radius: 6px;
    padding: 6px 8px;
}
QWidget#configCheckPage {
    background: #ffffff;
}
QLabel#checkPageTitle {
    color: #172033;
    font-size: 16px;
    font-weight: 700;
}
QLabel#checkSummaryLabel {
    color: #384153;
    background: #f7f9fc;
    border: 1px solid #d9dee7;
    border-radius: 8px;
    padding: 8px 10px;
}
QFrame#configCheckItem {
    border: 1px solid #d9dee7;
    border-radius: 8px;
    background: #ffffff;
}
QFrame#configCheckItem[status="ok"] {
    border-color: #b8e3dc;
    background: #f0fdfa;
}
QFrame#configCheckItem[status="warning"] {
    border-color: #fde68a;
    background: #fffbeb;
}
QFrame#configCheckItem[status="error"] {
    border-color: #fecaca;
    background: #fef2f2;
}
QLabel#checkStatusLabel {
    color: #172033;
    font-weight: 700;
}
QLabel#checkTitleLabel {
    color: #172033;
    font-weight: 700;
}
QLabel#checkDetailLabel {
    color: #5d6675;
}
QFrame#header {
    border: 1px solid #d9dee7;
    border-radius: 8px;
    background: #fbfcfe;
}
QLabel#statusLabel {
    color: #172033;
    font-size: 15px;
    font-weight: 600;
}
QLabel#feedbackLabel {
    color: #0f766e;
    background: #e8f7f4;
    border: 1px solid #b8e3dc;
    border-radius: 6px;
    padding: 6px 8px;
}
QLabel#badge {
    color: #384153;
    background: #eef2f7;
    border: 1px solid #d8dee9;
    border-radius: 6px;
    padding: 4px 8px;
}
QTextEdit#resultEdit {
    border: 1px solid #d4dbe6;
    border-radius: 8px;
    padding: 10px;
    font-size: 15px;
    color: #172033;
    background: #ffffff;
    selection-background-color: #bfd7ff;
}
QPushButton {
    min-height: 34px;
    border-radius: 7px;
    padding: 7px 12px;
    font-weight: 600;
}
QPushButton#primaryButton {
    color: #ffffff;
    background: #2563eb;
    border: 1px solid #1d4ed8;
}
QPushButton#primaryButton:hover {
    background: #1d4ed8;
}
QPushButton#recordingButton {
    color: #ffffff;
    background: #dc2626;
    border: 1px solid #b91c1c;
}
QPushButton#recordingButton:hover {
    background: #b91c1c;
}
QPushButton#accentButton {
    color: #ffffff;
    background: #0f766e;
    border: 1px solid #0f6a62;
}
QPushButton#accentButton:hover {
    background: #0d625b;
}
QPushButton#saveSettingsButton {
    color: #ffffff;
    background: #2563eb;
    border: 1px solid #1d4ed8;
    border-radius: 7px;
    padding: 8px 14px;
}
QPushButton#saveSettingsButton:hover {
    background: #1d4ed8;
}
QPushButton#saveSettingsButton[saved="true"] {
    color: #ffffff;
    background: #16a34a;
    border: 1px solid #15803d;
}
QPushButton#secondaryButton {
    color: #243044;
    background: #ffffff;
    border: 1px solid #cfd7e3;
}
QPushButton#secondaryButton:hover {
    background: #f2f5f9;
}
QPushButton:disabled {
    color: #8a94a6;
    background: #edf1f5;
    border: 1px solid #d7dee8;
}
QLineEdit, QSpinBox {
    min-height: 28px;
    border: 1px solid #cfd7e3;
    border-radius: 6px;
    padding: 4px 7px;
    background: #ffffff;
}
QSpinBox {
    min-height: 30px;
    padding: 4px 34px 4px 10px;
    color: #172033;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    background: #ffffff;
    selection-color: #172033;
    selection-background-color: #dbeafe;
}
QSpinBox:hover {
    border-color: #93b4e7;
    background: #fbfdff;
}
QSpinBox:focus {
    border-color: #2563eb;
    background: #ffffff;
}
QSpinBox::up-button,
QSpinBox::down-button {
    subcontrol-origin: border;
    width: 28px;
    right: 1px;
    border-left: 1px solid #e2e8f0;
    background: #f8fafc;
}
QSpinBox::up-button {
    subcontrol-position: top right;
    top: 1px;
    border-top-right-radius: 7px;
}
QSpinBox::down-button {
    subcontrol-position: bottom right;
    bottom: 1px;
    border-bottom-right-radius: 7px;
}
QSpinBox::up-button:hover,
QSpinBox::down-button:hover {
    background: #eef4ff;
    border-left-color: #bfcef4;
}
QSpinBox::up-button:pressed,
QSpinBox::down-button:pressed {
    background: #dbeafe;
    border-left-color: #93c5fd;
}
QSpinBox::up-arrow {
    image: url(app/ui/assets/chevron-up.svg);
    width: 12px;
    height: 12px;
}
QSpinBox::down-arrow {
    image: url(app/ui/assets/chevron-down.svg);
    width: 12px;
    height: 12px;
}
QComboBox {
    min-height: 30px;
    color: #172033;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 4px 34px 4px 10px;
    background: #ffffff;
    selection-background-color: #dbeafe;
}
QComboBox:hover {
    border-color: #93b4e7;
    background: #fbfdff;
}
QComboBox:focus {
    border-color: #2563eb;
    background: #ffffff;
}
QComboBox:disabled {
    color: #8a94a6;
    background: #edf1f5;
    border-color: #d7dee8;
}
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 30px;
    border-left: 1px solid #e2e8f0;
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
    background: #f8fafc;
}
QComboBox::drop-down:hover {
    background: #eef4ff;
    border-left-color: #bfcef4;
}
QComboBox::down-arrow {
    image: url(app/ui/assets/chevron-down.svg);
    width: 12px;
    height: 12px;
    margin-right: 10px;
}
QComboBox QLineEdit {
    min-height: 24px;
    color: #172033;
    border: none;
    border-radius: 0;
    padding: 0;
    background: transparent;
    selection-background-color: #dbeafe;
}
QComboBox QAbstractItemView {
    color: #172033;
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 4px;
    outline: none;
    selection-color: #172033;
    selection-background-color: #dbeafe;
}
QComboBox QAbstractItemView::item {
    min-height: 28px;
    padding: 6px 8px;
    border-radius: 6px;
}
QComboBox QAbstractItemView::item:hover {
    background: #eff6ff;
}
QListWidget {
    border: 1px solid #d4dbe6;
    border-radius: 8px;
    background: #ffffff;
}
"""
