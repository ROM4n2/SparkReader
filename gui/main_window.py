"""
Main application window with tab navigation.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QLabel,
)

from gui.settings_tab import SettingsTab


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

        # Phase 1 tabs
        self.chat_tab = self._make_placeholder("💬 问答", "聊天功能即将上线")
        self.settings_tab = SettingsTab()

        self.tabs.addTab(self.chat_tab, "💬 问答")
        self.tabs.addTab(self._make_placeholder("📖 阅读", "阅读器将在 Phase 2 实现"), "📖 阅读")
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
