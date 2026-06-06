"""
Settings tab — model selection, clipboard monitoring, hotkey config.
Settings persisted via QSettings (Windows Registry / INI fallback).
"""
import httpx
from pathlib import Path
from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QComboBox, QCheckBox, QSpinBox,
    QDoubleSpinBox, QKeySequenceEdit, QGroupBox,
)

from backend.config import OLLAMA_BASE_URL, EMBED_MODEL


class SettingsTab(QWidget):
    """Settings panel. Reads/writes QSettings on change."""

    def __init__(self):
        super().__init__()
        self.settings = QSettings("SparkReader", "Spark")
        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(32, 24, 32, 24)

        # ── Model group ──
        model_group = QGroupBox("模型设置")
        model_layout = QFormLayout(model_group)

        self.chat_model_combo = QComboBox()
        self.chat_model_combo.setMinimumWidth(200)
        self._populate_models()
        model_layout.addRow("聊天模型:", self.chat_model_combo)

        self.embed_model_combo = QComboBox()
        self.embed_model_combo.addItems([EMBED_MODEL, "nomic-embed-text", "all-minilm"])
        model_layout.addRow("嵌入模型:", self.embed_model_combo)

        layout.addWidget(model_group)

        # ── Clipboard group ──
        clip_group = QGroupBox("剪贴板监控")
        clip_layout = QFormLayout(clip_group)

        self.clip_enabled = QCheckBox("启用监控")
        clip_layout.addRow(self.clip_enabled)

        self.threshold_spin = QSpinBox()
        self.threshold_spin.setRange(0, 500)
        self.threshold_spin.setSuffix(" 字")
        self.threshold_spin.setToolTip("0 = 关闭自动解释")
        clip_layout.addRow("自动解释阈值:", self.threshold_spin)

        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(0.5, 10.0)
        self.interval_spin.setSingleStep(0.5)
        self.interval_spin.setSuffix(" 秒")
        clip_layout.addRow("轮询间隔:", self.interval_spin)

        layout.addWidget(clip_group)

        # ── Hotkey group ──
        hotkey_group = QGroupBox("快捷键")
        hotkey_layout = QFormLayout(hotkey_group)

        self.hotkey_edit = QKeySequenceEdit()
        hotkey_layout.addRow("唤起窗口:", self.hotkey_edit)

        self.auto_start = QCheckBox("开机自动启动")
        self.auto_start.setChecked(False)  # Default off per user preference
        self.auto_start.toggled.connect(self._toggle_auto_start)
        hotkey_layout.addRow(self.auto_start)

        layout.addWidget(hotkey_group)

        # ── About group ──
        about_group = QGroupBox("关于")
        about_layout = QVBoxLayout(about_group)
        about_layout.addWidget(QLabel("Spark v0.2 · 马列经典 AI 阅读助手"))
        about_layout.addWidget(QLabel("后端: Ollama + ChromaDB | GUI: PySide6"))
        layout.addWidget(about_group)

        layout.addStretch()

        # Connect signals to auto-save
        self.chat_model_combo.currentTextChanged.connect(self._save_settings)
        self.embed_model_combo.currentTextChanged.connect(self._save_settings)
        self.clip_enabled.toggled.connect(self._save_settings)
        self.threshold_spin.valueChanged.connect(self._save_settings)
        self.interval_spin.valueChanged.connect(self._save_settings)
        self.hotkey_edit.keySequenceChanged.connect(self._save_settings)
        self.auto_start.toggled.connect(self._save_settings)

    def _populate_models(self):
        """Fetch available models from Ollama and populate combo."""
        current = self.chat_model_combo.currentText()
        try:
            resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5.0)
            models = [m["name"] for m in resp.json().get("models", [])]
            self.chat_model_combo.clear()
            self.chat_model_combo.addItems(models)
        except Exception:
            self.chat_model_combo.clear()
            self.chat_model_combo.addItem("(Ollama 未连接)")

        # Restore selection if previously set
        if current:
            idx = self.chat_model_combo.findText(current)
            if idx >= 0:
                self.chat_model_combo.setCurrentIndex(idx)

    def _load_settings(self):
        """Load persisted settings into widgets."""
        self.chat_model_combo.setCurrentText(
            self.settings.value("chat_model", "qwen2.5:7b", type=str)
        )
        self.embed_model_combo.setCurrentText(
            self.settings.value("embed_model", EMBED_MODEL, type=str)
        )
        self.clip_enabled.setChecked(
            self.settings.value("clip_enabled", True, type=bool)
        )
        self.threshold_spin.setValue(
            self.settings.value("explain_threshold", 50, type=int)
        )
        self.interval_spin.setValue(
            self.settings.value("poll_interval", 2.0, type=float)
        )
        from PySide6.QtGui import QKeySequence
        seq = self.settings.value("hotkey", "Ctrl+Shift+S", type=str)
        self.hotkey_edit.setKeySequence(QKeySequence(seq))
        self.auto_start.setChecked(
            self.settings.value("auto_start", False, type=bool)
        )

    def _save_settings(self):
        """Persist current widget values."""
        self.settings.setValue("chat_model", self.chat_model_combo.currentText())
        self.settings.setValue("embed_model", self.embed_model_combo.currentText())
        self.settings.setValue("clip_enabled", self.clip_enabled.isChecked())
        self.settings.setValue("explain_threshold", self.threshold_spin.value())
        self.settings.setValue("poll_interval", self.interval_spin.value())
        self.settings.setValue("hotkey", self.hotkey_edit.keySequence().toString())
        self.settings.setValue("auto_start", self.auto_start.isChecked())

    def get_chat_model(self) -> str:
        return self.chat_model_combo.currentText()

    def get_clipboard_enabled(self) -> bool:
        return self.clip_enabled.isChecked()

    def _toggle_auto_start(self, enabled: bool):
        """Register or unregister Windows auto-start via registry."""
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, key_path,
                0, winreg.KEY_SET_VALUE,
            )
            if enabled:
                import sys
                exe = sys.executable
                script = Path(__file__).parent.parent / "gui" / "app.py"
                winreg.SetValueEx(key, "Spark", 0, winreg.REG_SZ, f'"{exe}" "{script}"')
            else:
                try:
                    winreg.DeleteValue(key, "Spark")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception:
            pass  # Non-Windows or permission error — silently ignore

    def get_explain_threshold(self) -> int:
        return self.threshold_spin.value()
