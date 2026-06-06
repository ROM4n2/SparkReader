"""
Main application window with tab navigation.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QLabel,
)

from gui.settings_tab import SettingsTab
from gui.chat_tab import ChatTab
from gui.reader_tab import ReaderTab


class MainWindow(QMainWindow):
    """Spark main window with 4 tabs. Phase 1 delivers Chat + Settings."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Spark - 马列经典 AI 阅读助手")
        self.setMinimumSize(900, 600)
        self.resize(1100, 720)

        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.West)
        self.tabs.setTabShape(QTabWidget.TabShape.Rounded)
        self.setCentralWidget(self.tabs)

        # Phase 1+2 tabs
        self.chat_tab = ChatTab(settings_getter=self.get_settings)
        self.reader_tab = ReaderTab()
        self.settings_tab = SettingsTab()

        self.tabs.addTab(self.chat_tab, "💬 问答")
        self.tabs.addTab(self.reader_tab, "📖 阅读")
        self.tabs.addTab(self._make_placeholder("📚 文档库", "文档管理将在 Phase 3 实现"), "📚 文档库")
        self.tabs.addTab(self.settings_tab, "⚙️ 设置")

    def _make_placeholder(self, title: str, message: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        label = QLabel(message)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: #888888; font-size: 16px;")
        layout.addWidget(label)
        return widget

    def get_settings(self) -> SettingsTab:
        return self.settings_tab

    def closeEvent(self, event):
        self.chat_tab.close_client()
        self.reader_tab.close_client()
        super().closeEvent(event)
