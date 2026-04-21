import sys
import os
from PyQt6.QtWidgets import QApplication, QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QWidget
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QFont, QColor, QPainter, QPainterPath, QLinearGradient


class ModeSelectDialog(QDialog):
    """
    Startup prompt — user picks Voice, Text, or Both before Kora launches.
    Sets KORA_INPUT_MODE env var which main.py reads.
    """

    def __init__(self):
        super().__init__()
        self.selected_mode = None

        self.setWindowTitle("KORA")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(520, 340)

        # Centre on screen
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width()  - self.width())  // 2,
            (screen.height() - self.height()) // 2,
        )

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = QWidget()
        card.setObjectName("card")
        card.setStyleSheet("""
            QWidget#card {
                background-color: #090b10;
                border: 1px solid #1a2035;
                border-radius: 20px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 36, 40, 36)
        card_layout.setSpacing(24)

        # ── Title ─────────────────────────────────────────────────────────────
        title = QLabel("KORA")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tf = QFont("Inter", 22, QFont.Weight.Bold)
        tf.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 10)
        title.setFont(tf)
        title.setStyleSheet("color: #00d2ff; background: transparent;")
        card_layout.addWidget(title)

        sub = QLabel("How would you like to interact?")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sf = QFont("Inter", 11)
        sub.setFont(sf)
        sub.setStyleSheet("color: #445566; background: transparent;")
        card_layout.addWidget(sub)

        # ── Mode buttons ──────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(14)

        self.btn_voice = self._make_mode_btn(
            "🎙", "Voice Only",
            "Speak to Kora.\nMicrophone is always\nlistening.",
            "#003a6e", "#0055aa",
        )
        self.btn_text = self._make_mode_btn(
            "⌨", "Text Only",
            "Type your messages.\nMicrophone stays\noff.",
            "#2a1a00", "#7a4400",
        )
        self.btn_both = self._make_mode_btn(
            "✦", "Voice + Text",
            "Speak OR type.\nBoth work at the\nsame time.",
            "#1a0035", "#5500aa",
        )

        self.btn_voice.clicked.connect(lambda: self._choose("voice"))
        self.btn_text.clicked.connect( lambda: self._choose("text"))
        self.btn_both.clicked.connect( lambda: self._choose("both"))

        btn_row.addWidget(self.btn_voice)
        btn_row.addWidget(self.btn_text)
        btn_row.addWidget(self.btn_both)
        card_layout.addLayout(btn_row)

        # ── Quit link ─────────────────────────────────────────────────────────
        quit_btn = QPushButton("× Exit")
        quit_btn.setFlat(True)
        quit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        quit_btn.setStyleSheet("""
            QPushButton {
                color: #222c3a;
                font-size: 11px;
                background: transparent;
                border: none;
            }
            QPushButton:hover { color: #ff4444; }
        """)
        quit_btn.clicked.connect(lambda: sys.exit(0))
        card_layout.addWidget(quit_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        root.addWidget(card)

    def _make_mode_btn(self, icon, label, description, bg_color, hover_color):
        btn = QPushButton()
        btn.setFixedSize(130, 150)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        # Build a rich label inside the button
        inner = QVBoxLayout(btn)
        inner.setContentsMargins(10, 16, 10, 16)
        inner.setSpacing(6)

        icon_lbl = QLabel(icon)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setFont(QFont("Segoe UI Emoji", 26))
        icon_lbl.setStyleSheet("background: transparent; color: white;")

        name_lbl = QLabel(label)
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nf = QFont("Inter", 10, QFont.Weight.Bold)
        name_lbl.setFont(nf)
        name_lbl.setStyleSheet("background: transparent; color: #ddeeff;")

        desc_lbl = QLabel(description)
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        df = QFont("Inter", 8)
        desc_lbl.setFont(df)
        desc_lbl.setStyleSheet("background: transparent; color: #445566;")
        desc_lbl.setWordWrap(True)

        inner.addWidget(icon_lbl)
        inner.addWidget(name_lbl)
        inner.addWidget(desc_lbl)

        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_color};
                border: 1px solid #1a2035;
                border-radius: 14px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
                border: 1px solid #334466;
            }}
            QPushButton:pressed {{
                background-color: {bg_color};
            }}
        """)
        return btn

    def _choose(self, mode):
        self.selected_mode = mode
        self.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            sys.exit(0)


def ask_mode() -> str:
    """
    Show the mode selector and return 'voice', 'text', or 'both'.
    Call this before creating KoraDashboard.
    """
    app = QApplication.instance() or QApplication(sys.argv)
    dlg = ModeSelectDialog()
    if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_mode:
        return dlg.selected_mode
    sys.exit(0)


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    mode = ask_mode()
    print(f"Selected mode: {mode}")
    sys.exit(0)
