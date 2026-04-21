import sys
import os
import math
import random
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QGraphicsDropShadowEffect, QTextEdit,
    QLineEdit, QPushButton, QSizePolicy, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRectF, QEvent
from PyQt6.QtGui import QPainter, QColor, QFont, QPainterPath, QRadialGradient, QPen, QTextCursor

# ══════════════════════════════════════════════════════════════════════════════
#  3D PARTICLE SPHERE
# ══════════════════════════════════════════════════════════════════════════════

class ParticlePoint:
    def __init__(self, x, y, z):
        self.base_x = x
        self.base_y = y
        self.base_z = z


class KoraSphereWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(320, 320)
        self.phase  = 0.0
        self.rot_x  = 0.0
        self.rot_y  = 0.0
        self.state  = "IDLE"

        self.particles = []
        n   = 1200
        phi = math.pi * (3.0 - math.sqrt(5.0))
        for i in range(n):
            y = 1 - (i / float(n - 1)) * 2
            r = math.sqrt(max(0, 1 - y * y))
            t = phi * i
            self.particles.append(ParticlePoint(math.cos(t) * r, y, math.sin(t) * r))

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(16)

    def _tick(self):
        self.phase += 0.1
        speed = {"PROCESSING": (0.08, 0.04), "SPEAKING": (0.04, 0.02)}.get(
            self.state, (0.01, 0.005)
        )
        self.rot_y -= speed[0]
        self.rot_x += speed[1]
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect().adjusted(2, 2, -2, -2))
        path = QPainterPath()
        path.addRoundedRect(rect, 28, 28)
        p.fillPath(path, QColor(8, 10, 14, 245))

        cx = cy = 160
        sr = 95

        if self.state == "SPEAKING":
            sr += math.sin(self.phase * 3.5) * 14
            shake = 7
        elif self.state == "LISTENING":
            sr += math.sin(self.phase * 1.0) * 7
            shake = 0
        elif self.state == "PROCESSING":
            sr += math.sin(self.phase * 0.8) * 3
            shake = 0
        else:
            sr += math.sin(self.phase * 0.3) * 3
            shake = 0

        # Nebula core
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
        g = QRadialGradient(cx, cy, sr * 1.5)
        g.setColorAt(0,   QColor(0,   100, 255, 60))
        g.setColorAt(0.5, QColor(150,  40, 255, 30))
        g.setColorAt(1,   QColor(0,     0,   0,  0))
        p.setBrush(g)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(int(cx - sr*2), int(cy - sr*2), int(sr*4), int(sr*4))

        # Containment rings
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        rr = sr * 1.65
        pen = QPen(QColor(0, 210, 255, 45))
        pen.setWidthF(1.4)
        p.setPen(pen)
        p.setBrush(Qt.GlobalColor.transparent)
        p.drawEllipse(int(cx-rr), int(cy-rr), int(rr*2), int(rr*2))
        pen.setColor(QColor(200, 50, 255, 75))
        pen.setWidthF(1.8)
        p.setPen(pen)
        ang = int((math.degrees(self.phase * -0.5)) % 360 * 16)
        p.drawArc(int(cx-rr*.88), int(cy-rr*.88), int(rr*1.76), int(rr*1.76), ang, 60*16)
        p.drawArc(int(cx-rr*.88), int(cy-rr*.88), int(rr*1.76), int(rr*1.76), ang+180*16, 60*16)

        # Particles
        cx_f = cx
        cy_f = cy
        cos_x, sin_x = math.cos(self.rot_x), math.sin(self.rot_x)
        cos_y, sin_y = math.cos(self.rot_y), math.sin(self.rot_y)
        proj = []
        for pt in self.particles:
            jx = random.uniform(-shake, shake) if shake else 0
            jy = random.uniform(-shake, shake) if shake else 0
            jz = random.uniform(-shake, shake) if shake else 0
            sx = pt.base_x * sr + jx
            sy = pt.base_y * sr + jy
            sz = pt.base_z * sr + jz
            y1 = sy * cos_x - sz * sin_x
            z1 = sy * sin_x + sz * cos_x
            x2 = sx * cos_y + z1 * sin_y
            z2 = -sx * sin_y + z1 * cos_y
            proj.append((cx_f + x2, cy_f + y1, z2))

        proj.sort(key=lambda q: q[2])
        p.setPen(Qt.PenStyle.NoPen)
        for sx, sy, dz in proj:
            dr   = max(0.01, min(1.0, (dz + sr) / (sr * 2)))
            alpha = int(50 + 205 * dr)
            p.setBrush(QColor(0, 210, 255, alpha))
            dot = 1.5 + dr * 1.4
            p.drawEllipse(QRectF(sx - dot/2, sy - dot/2, dot, dot))


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

class KoraDashboard(QMainWindow):
    status_signal      = pyqtSignal(str)
    log_signal         = pyqtSignal(str, str)
    text_input_signal  = pyqtSignal(str)

    LOG_COLORS = {
        "USER":         "#ffffff",
        "KORA":         "#00d2ff",
        "SYSTEM":       "#555e6e",
        "SYSTEM ERROR": "#ff4444",
        "REMINDER":     "#ffaa00",
    }

    def __init__(self, input_mode: str = "both"):
        super().__init__()
        self.input_mode = input_mode   # "voice" | "text" | "both"
        super().__init__()
        self.setWindowTitle("KORA")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(60, 60, 940, 560)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # ── LEFT PANEL: sphere + status ───────────────────────────────────────
        left = QWidget()
        left.setFixedWidth(340)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        self.sphere_core = KoraSphereWidget()
        left_layout.addWidget(self.sphere_core, alignment=Qt.AlignmentFlag.AlignCenter)

        self.status_label = QLabel("SYSTEM ONLINE")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sf = QFont("Inter", 10, QFont.Weight.Bold)
        sf.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4)
        self.status_label.setFont(sf)
        self.status_label.setStyleSheet("color: #00d2ff; background: transparent;")
        left_layout.addWidget(self.status_label)

        # Mode indicator
        mode_icons = {"voice": "🎙  VOICE MODE", "text": "⌨  TEXT MODE", "both": "🎙  VOICE + TEXT  ⌨"}
        self.mode_label = QLabel(mode_icons.get(input_mode, "🎙 + ⌨"))
        self.mode_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mf = QFont("Inter", 8)
        self.mode_label.setFont(mf)
        self.mode_label.setStyleSheet("color: #334455; background: transparent;")
        left_layout.addWidget(self.mode_label)
        left_layout.addStretch()

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(45)
        shadow.setColor(QColor(0, 0, 0, 210))
        shadow.setOffset(0, 12)
        self.sphere_core.setGraphicsEffect(shadow)

        root.addWidget(left)

        # ── RIGHT PANEL: log + text input ─────────────────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        # Log title
        log_title = QLabel("CONVERSATION")
        log_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tf = QFont("Inter", 8, QFont.Weight.Bold)
        tf.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3)
        log_title.setFont(tf)
        log_title.setStyleSheet("color: #2a3040; background: transparent;")
        right_layout.addWidget(log_title)

        # Chat log
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.log_view.setStyleSheet("""
            QTextEdit {
                background-color: #080a0e;
                border: 1px solid #141820;
                border-radius: 14px;
                padding: 12px 14px;
                color: #c8cdd6;
                font-family: 'Segoe UI', 'Inter', sans-serif;
                font-size: 13px;
                line-height: 1.6;
            }
            QScrollBar:vertical {
                background: #080a0e; width: 5px;
            }
            QScrollBar::handle:vertical {
                background: #1e2530; border-radius: 2px;
            }
        """)
        right_layout.addWidget(self.log_view)

        # ── Text input row ────────────────────────────────────────────────────
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Type a message and press Enter  (or just speak)...")
        self.text_input.setStyleSheet("""
            QLineEdit {
                background-color: #0d1018;
                border: 1px solid #1e2840;
                border-radius: 10px;
                padding: 10px 14px;
                color: #e0e4ee;
                font-family: 'Segoe UI', 'Inter', sans-serif;
                font-size: 13px;
                selection-background-color: #1a3a6a;
            }
            QLineEdit:focus {
                border: 1px solid #0057aa;
                background-color: #0f1420;
            }
        """)
        self.text_input.returnPressed.connect(self._submit_text)
        input_row.addWidget(self.text_input)

        self.send_btn = QPushButton("Send")
        self.send_btn.setFixedWidth(70)
        self.send_btn.setFixedHeight(40)
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #0044aa;
                border: none;
                border-radius: 10px;
                color: #ffffff;
                font-family: 'Inter', sans-serif;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover  { background-color: #0055cc; }
            QPushButton:pressed { background-color: #003388; }
            QPushButton:disabled { background-color: #111825; color: #333; }
        """)
        self.send_btn.clicked.connect(self._submit_text)
        input_row.addWidget(self.send_btn)

        right_layout.addLayout(input_row)

        # Hint label under input
        hint_text = {
            "voice": "🎙 speak to Kora",
            "text":  "⌨ type and press Enter",
            "both":  "⌨ type  ·  🎙 speak  ·  both work at the same time",
        }.get(input_mode, "")
        hint = QLabel(hint_text)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: #1e2535; font-size: 10px; background: transparent;")
        right_layout.addWidget(hint)

        # Hide text input entirely in voice-only mode
        if input_mode == "voice":
            self.text_input.hide()
            self.send_btn.hide()

        root.addWidget(right, stretch=1)

        # Connect signals
        self.status_signal.connect(self.update_status)
        self.log_signal.connect(self.append_log)

        # Load past conversation from DB
        self._load_past_logs()

    # ── Internal: submit typed text ───────────────────────────────────────────

    def _submit_text(self):
        """Called when user presses Enter or clicks Send."""
        text = self.text_input.text().strip()
        if not text:
            return
        self.text_input.clear()
        self.send_btn.setEnabled(False)   # Disable until Kora replies
        self.text_input_signal.emit(text) # Send to main.py logic thread

    def re_enable_input(self):
        """Re-enable the send button after Kora has replied."""
        self.send_btn.setEnabled(True)
        self.text_input.setFocus()

    # ── Signals ───────────────────────────────────────────────────────────────

    def update_status(self, text):
        raw = text.upper()
        self.status_label.setText(raw)
        if   "LISTENING"   in raw: self.sphere_core.state = "LISTENING"
        elif "PROCESSING"  in raw: self.sphere_core.state = "PROCESSING"
        elif "SPEAKING"    in raw: self.sphere_core.state = "SPEAKING"
        else:                      self.sphere_core.state = "IDLE"

    def append_log(self, sender, message):
        color   = self.LOG_COLORS.get(sender.upper(), "#aaaaaa")
        # Strip injected memory prefix
        display = message
        if message.startswith("[Relevant memory:") and "\n\nUser says:" in message:
            display = message.split("\n\nUser says:", 1)[1].strip()
        self.log_view.append(
            f'<span style="color:{color};font-weight:600;">{sender.upper()}:</span>'
            f'&nbsp;<span style="color:#c8cdd6;">{display}</span>'
        )
        self.log_view.moveCursor(QTextCursor.MoveOperation.End)

    # ── Past log loader ───────────────────────────────────────────────────────

    def _load_past_logs(self):
        try:
            from storage import load_all_logs
            entries = load_all_logs()
            if not entries:
                return
            self.log_view.append(
                '<span style="color:#1a2030;font-size:11px;">─── past conversation ───</span>'
            )
            for timestamp, role, content in entries:
                display = content
                if content.startswith("[Relevant memory:") and "\n\nUser says:" in content:
                    display = content.split("\n\nUser says:", 1)[1].strip()
                color = self.LOG_COLORS.get(role.upper(), "#888")
                ts    = str(timestamp)[:16]
                self.log_view.append(
                    f'<span style="color:#1e2535;">[{ts}]</span> '
                    f'<span style="color:{color};font-weight:600;">{role.upper()}:</span>'
                    f'&nbsp;<span style="color:#9098a8;">{display}</span>'
                )
            self.log_view.append(
                '<span style="color:#1a2030;font-size:11px;">─── new session ───</span>'
            )
            self.log_view.moveCursor(QTextCursor.MoveOperation.End)
        except Exception as e:
            print(f"[GUI] Could not load past logs: {e}")

    # ── Keyboard shortcuts ────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            print("\n[KORA]: ESC abort.")
            os._exit(0)