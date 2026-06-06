"""
Spark GUI entry point.
Handles QApplication, system tray, and global hotkey.
"""
import sys
import os

# Ensure backend is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QMessageBox

from gui.main_window import MainWindow


def run():
    """Launch the Spark GUI application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Spark")
    app.setOrganizationName("SparkReader")

    # Load theme
    theme_path = Path(__file__).parent / "resources" / "theme.qss"
    if theme_path.exists():
        with open(theme_path, encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    # Check Ollama availability before showing window
    from backend.ollama_client import OllamaClient
    try:
        client = OllamaClient()
        # Quick health check via embed (lighter than chat)
        client.embed("ping")
        client.close()
    except Exception:
        reply = QMessageBox.question(
            None, "Ollama 未运行",
            "无法连接到 Ollama。请确保 Ollama 正在运行。\n\n是否继续启动？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.No:
            sys.exit(1)

    window = MainWindow()

    # System tray
    tray = QSystemTrayIcon(QIcon(), app)
    tray.setToolTip("Spark - 马列经典 AI 阅读助手")
    tray_menu = QMenu()
    show_action = tray_menu.addAction("显示窗口")
    show_action.triggered.connect(window.show)
    show_action.triggered.connect(window.raise_)
    quit_action = tray_menu.addAction("退出")
    quit_action.triggered.connect(app.quit)
    tray.setContextMenu(tray_menu)
    tray.show()

    # Global hotkey: Ctrl+Shift+S to toggle window
    hotkey = QShortcut(QKeySequence("Ctrl+Shift+S"), window)
    hotkey.activated.connect(lambda: _toggle_window(window))

    # Override close event to minimize to tray
    def close_event(event):
        event.ignore()
        window.hide()
        tray.showMessage("Spark", "已最小化到系统托盘", QSystemTrayIcon.MessageIcon.Information, 2000)

    window.closeEvent = close_event  # type: ignore

    window.show()
    sys.exit(app.exec())


def _toggle_window(window):
    """Toggle main window visibility."""
    if window.isVisible():
        window.hide()
    else:
        window.show()
        window.raise_()
        window.activateWindow()


if __name__ == "__main__":
    run()
