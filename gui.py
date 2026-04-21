import sys
import os
import math
import random
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QGraphicsDropShadowEffect, QTextEdit, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QColor, QFont, QPainterPath, QRadialGradient, QPen, QTextCursor

# ==============================================================================
# 3D PARTICLE SPHERE ENGINE
# ==============================================================================

class ParticlePoint:
    def __init__(self, x, y, z):
        self.base_x = x
        self.base_y = y
        self.base_z = z


class KoraSphereWidget(QWidget):
    """Renders a 3D particle sphere with energy core and bounding rings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(350, 350)
        self.setMaximumSize(350, 350)
        self.phase = 0.0
        self.rot_x = 0.0
        self.rot_y = 0.0
        self.state = "IDLE"

        # Fibonacci sphere — 1200 evenly distributed particles
        self.particles = []
        num_particles = 1200
        phi = math.pi * (3.0 - math.sqrt(5.0))
        for i in range(num_particles):
            y = 1 - (i / float(num_particles - 1)) * 2
            r = math.sqrt(1 - y * y)
            theta = phi * i
            self.particles.append(ParticlePoint(math.cos(theta) * r, y, math.sin(theta) * r))

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(16)

    def animate(self):
        self.phase += 0.1
        if self.state == "PROCESSING":
            self.rot_y -= 0.08
            self.rot_x += 0.04
        elif self.state == "SPEAKING":
            self.rot_y -= 0.04
            self.rot_x += 0.02
        else:
            self.rot_y -= 0.01
            self.rot_x += 0.005
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect().adjusted(2, 2, -2, -2))
        path = QPainterPath()
        path.addRoundedRect(rect, 30, 30)
        p.fillPath(path, QColor(8, 10, 14, 240))

        cx, cy = self.width() / 2, self.height() / 2
        sphere_radius = 100
        global_shake = 0

        if self.state == "SPEAKING":
            sphere_radius += math.sin(self.phase * 3.5) * 15
            global_shake = 8
        elif self.state == "LISTENING":
            sphere_radius += math.sin(self.phase * 1.0) * 8
        elif self.state == "PROCESSING":
            sphere_radius += math.sin(self.phase * 0.8) * 3
        else:
            sphere_radius += math.sin(self.phase * 0.3) * 3

        # Energy nebula core
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
        core_grad = QRadialGradient(cx, cy, sphere_radius * 1.5)
        core_grad.setColorAt(0, QColor(0, 100, 255, 60))
        core_grad.setColorAt(0.5, QColor(150, 40, 255, 30))
        core_grad.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(core_grad)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(int(cx - sphere_radius * 2), int(cy - sphere_radius * 2),
                      int(sphere_radius * 4), int(sphere_radius * 4))

        # Containment rings
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        ring_pen = QPen(QColor(0, 210, 255, 50))
        ring_pen.setWidthF(1.5)
        p.setPen(ring_pen)
        p.setBrush(Qt.GlobalColor.transparent)
        ring_radius = sphere_radius * 1.7
        p.drawEllipse(int(cx - ring_radius), int(cy - ring_radius),
                      int(ring_radius * 2), int(ring_radius * 2))

        ring_pen.setColor(QColor(200, 50, 255, 80))
        ring_pen.setWidthF(2.0)
        p.setPen(ring_pen)
        span = 60 * 16
        start_angle = int((math.degrees(self.phase * -0.5)) % 360 * 16)
        p.drawArc(int(cx - ring_radius * 0.9), int(cy - ring_radius * 0.9),
                  int(ring_radius * 1.8), int(ring_radius * 1.8), start_angle, span)
        p.drawArc(int(cx - ring_radius * 0.9), int(cy - ring_radius * 0.9),
                  int(ring_radius * 1.8), int(ring_radius * 1.8), start_angle + (180 * 16), span)

        # 3D particle renderer
        cos_x, sin_x = math.cos(self.rot_x), math.sin(self.rot_x)
        cos_y, sin_y = math.cos(self.rot_y), math.sin(self.rot_y)

        projected = []
        for pt in self.particles:
            jx = random.uniform(-global_shake, global_shake) if global_shake else 0
            jy = random.uniform(-global_shake, global_shake) if global_shake else 0
            jz = random.uniform(-global_shake, global_shake) if global_shake else 0

            sx = pt.base_x * sphere_radius + jx
            sy = pt.base_y * sphere_radius + jy
            sz = pt.base_z * sphere_radius + jz

            y1 = sy * cos_x - sz * sin_x
            z1 = sy * sin_x + sz * cos_x
            x2 = sx * cos_y + z1 * sin_y
            z2 = -sx * sin_y + z1 * cos_y

            projected.append((cx + x2, cy + y1, z2))

        projected.sort(key=lambda q: q[2])
        p.setPen(Qt.PenStyle.NoPen)
        for screen_x, screen_y, depth in projected:
            dr = max(0.01, min(1.0, (depth + sphere_radius) / (sphere_radius * 2)))
            alpha = int(50 + 205 * dr)
            p.setBrush(QColor(0, 210, 255, alpha))
            dot = 1.6 + dr * 1.5
            p.drawEllipse(QRectF(screen_x - dot / 2, screen_y - dot / 2, dot, dot))


# ==============================================================================
# MAIN DASHBOARD  (sphere + log panel side-by-side)
# ==============================================================================

class KoraDashboard(QMainWindow):
    status_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str, str)

    # Colour map for different senders in the log
    LOG_COLORS = {
        "USER":         "#ffffff",
        "KORA":         "#00d2ff",
        "SYSTEM":       "#888888",
        "SYSTEM ERROR": "#ff4444",
        "REMINDER":     "#ffaa00",
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle("KORA SPHERE CORE")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(80, 80, 860, 480)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(14)

        # ── Left: sphere ──
        left = QVBoxLayout()
        left.setSpacing(8)

        self.sphere_core = KoraSphereWidget()
        left.addWidget(self.sphere_core, alignment=Qt.AlignmentFlag.AlignCenter)

        self.status_label = QLabel("SYSTEM ONLINE")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont("Inter", 11, QFont.Weight.Bold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4)
        self.status_label.setFont(font)
        self.status_label.setStyleSheet("color: #00d2ff;")
        left.addWidget(self.status_label)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 0, 0, 200))
        shadow.setOffset(0, 12)
        self.sphere_core.setGraphicsEffect(shadow)

        root.addLayout(left)

        # ── Right: conversation log ──
        right = QVBoxLayout()
        right.setSpacing(6)

        log_title = QLabel("CONVERSATION LOG")
        log_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tf = QFont("Inter", 9, QFont.Weight.Bold)
        tf.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3)
        log_title.setFont(tf)
        log_title.setStyleSheet("color: #444a55;")
        right.addWidget(log_title)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.log_view.setStyleSheet("""
            QTextEdit {
                background-color: #0a0c10;
                border: 1px solid #1a1e28;
                border-radius: 12px;
                padding: 10px;
                color: #cccccc;
                font-family: 'Consolas', monospace;
                font-size: 12px;
            }
            QScrollBar:vertical {
                background: #0a0c10;
                width: 6px;
            }
            QScrollBar::handle:vertical {
                background: #1e2530;
                border-radius: 3px;
            }
        """)
        right.addWidget(self.log_view)

        root.addLayout(right, stretch=1)

        # Connect signals
        self.status_signal.connect(self.update_status)
        self.log_signal.connect(self.append_log)

        # Load past logs from DB on startup
        self._load_past_logs()

    def _load_past_logs(self):
        """Populate the log panel with stored conversation history."""
        try:
            from storage import load_all_logs
            entries = load_all_logs()
            if not entries:
                return
            self.log_view.append(
                '<span style="color:#333a44;">── Past conversation loaded ──</span>'
            )
            for timestamp, role, content in entries:
                # Skip the injected memory-context prefix when displaying
                display_content = content
                if content.startswith("[Relevant memory:") and "\n\nUser says:" in content:
                    display_content = content.split("\n\nUser says:", 1)[1].strip()

                display_role = role.upper()
                color = self.LOG_COLORS.get(display_role, "#aaaaaa")
                ts = str(timestamp)[:16]  # "YYYY-MM-DD HH:MM"
                self.log_view.append(
                    f'<span style="color:#333a44;">[{ts}]</span> '
                    f'<span style="color:{color};font-weight:bold;">{display_role}:</span> '
                    f'<span style="color:#cccccc;">{display_content}</span>'
                )
            self.log_view.append(
                '<span style="color:#333a44;">── New session ──</span>'
            )
            # Scroll to bottom
            self.log_view.moveCursor(QTextCursor.MoveOperation.End)
        except Exception as e:
            print(f"[GUI] Could not load past logs: {e}")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            print("\n[KORA]: Emergency Abort triggered via ESC. Terminating.")
            os._exit(0)

    def update_status(self, text):
        raw = text.upper()
        self.status_label.setText(raw)
        if "LISTENING" in raw:
            self.sphere_core.state = "LISTENING"
        elif "PROCESSING" in raw:
            self.sphere_core.state = "PROCESSING"
        elif "SPEAKING" in raw:
            self.sphere_core.state = "SPEAKING"
        else:
            self.sphere_core.state = "IDLE"

    def append_log(self, sender, message):
        """Add a new line to the live log panel."""
        color = self.LOG_COLORS.get(sender.upper(), "#aaaaaa")

        # Strip injected memory prefix before displaying
        display_message = message
        if message.startswith("[Relevant memory:") and "\n\nUser says:" in message:
            display_message = message.split("\n\nUser says:", 1)[1].strip()

        self.log_view.append(
            f'<span style="color:{color};font-weight:bold;">{sender.upper()}:</span> '
            f'<span style="color:#cccccc;">{display_message}</span>'
        )
        self.log_view.moveCursor(QTextCursor.MoveOperation.End)
