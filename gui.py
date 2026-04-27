import sys
import os
import math
import random
import time
from html import escape
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QGraphicsDropShadowEffect, QTextEdit,
    QLineEdit, QPushButton, QSizePolicy, QFrame,
    QSystemTrayIcon, QMenu, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRectF, QEvent, QPoint, QEasingCurve, QPropertyAnimation
from PyQt6.QtGui import QPainter, QColor, QFont, QPainterPath, QRadialGradient, QPen, QTextCursor, QIcon, QAction, QPixmap, QBrush, QLinearGradient
from themes import get_active_theme

# ══════════════════════════════════════════════════════════════════════════════
#  PREMIUM PARTICLE SPHERE
# ══════════════════════════════════════════════════════════════════════════════

class ParticlePoint:
    def __init__(self, x, y, z):
        self.base_x = x
        self.base_y = y
        self.base_z = z
        self.noise_offset = random.random() * 100
        self.size_mult = 1.0 + random.random() * 0.5


class KoraSphereWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(360, 360)
        self.phase  = 0.0
        self.rot_x  = 0.0
        self.rot_y  = 0.0
        self.state  = "IDLE"
        self.vibration = 0.0
        
        # Sentiment-based colors
        theme = get_active_theme()
        self.base_color = QColor(theme["accent"])
        self.current_color = QColor(self.base_color)
        self.target_color = QColor(self.base_color)
        self.color_lerp = 1.0 # 0.0 to 1.0 transition

        self.particles = []
        n   = 1500  # More particles for premium feel
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
        self.phase += 0.05
        
        # State-based rotation speeds
        if self.state == "PROCESSING":
            speed_y, speed_x = 0.12, 0.06
            self.vibration = 2.0
        elif self.state == "SPEAKING":
            speed_y, speed_x = 0.06, 0.03
            self.vibration = 4.0 * abs(math.sin(self.phase * 5.0))
        elif self.state == "LISTENING":
            speed_y, speed_x = 0.02, 0.01
            self.vibration = 1.5 * abs(math.sin(self.phase * 2.0))
        else:
            speed_y, speed_x = 0.015, 0.008
            self.vibration = 0.0

        self.rot_y -= speed_y
        self.rot_x += speed_x
        
        # Color lerping
        if self.color_lerp < 1.0:
            self.color_lerp += 0.02
            r = int(self.current_color.red() + (self.target_color.red() - self.current_color.red()) * self.color_lerp)
            g = int(self.current_color.green() + (self.target_color.green() - self.current_color.green()) * self.color_lerp)
            b = int(self.current_color.blue() + (self.target_color.blue() - self.current_color.blue()) * self.color_lerp)
            self.current_color = QColor(r, g, b)
            if self.color_lerp >= 1.0:
                self.current_color = QColor(self.target_color)

        self.update()

    def set_mood(self, mood):
        """Sets the visual mood of the sphere."""
        moods = {
            "IDLE":      self.base_color,
            "POSITIVE":  QColor("#ff00ff"), # Pink/Magenta
            "NEGATIVE":  QColor("#ff4444"), # Red
            "URGENT":    QColor("#ffaa00"), # Orange/Amber
            "PROCESSING": QColor("#00ffaa"), # Cyan/Green
        }
        new_color = moods.get(mood.upper(), self.base_color)
        if new_color != self.target_color:
            self.current_color = QColor(self.target_color)
            self.target_color = QColor(new_color)
            self.color_lerp = 0.0

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = 180, 180
        sr = 110 # Core radius
        accent = self.current_color
        
        # 1. Background Glow (Nebula)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Screen)
        for i in range(3):
            glow_r = sr * (2.2 + i * 0.4 + math.sin(self.phase + i) * 0.1)
            g = QRadialGradient(cx, cy, glow_r)
            alpha = int(40 // (i + 1))
            g.setColorAt(0, QColor(accent.red(), accent.green(), accent.blue(), alpha))
            g.setColorAt(1, QColor(0, 0, 0, 0))
            p.setBrush(g)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(int(cx - glow_r), int(cy - glow_r), int(glow_r * 2), int(glow_r * 2))

        # 2. Containment Rings (More intricate)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        for i in range(2):
            ring_r = sr * (1.6 + i * 0.1)
            ring_color = QColor(accent.red(), accent.green(), accent.blue(), 30 - i * 10)
            pen = QPen(ring_color)
            pen.setWidthF(1.2)
            p.setPen(pen)
            p.drawEllipse(int(cx - ring_r), int(cy - ring_r), int(ring_r * 2), int(ring_r * 2))
            
            # Rotating arcs
            pen.setColor(QColor(accent.red(), accent.green(), accent.blue(), 120))
            pen.setWidthF(2.0)
            p.setPen(pen)
            rot_dir = 1 if i % 2 == 0 else -1
            ang = int((math.degrees(self.phase * 0.8 * rot_dir)) % 360 * 16)
            arc_len = 45 * 16
            p.drawArc(int(cx - ring_r), int(cy - ring_r), int(ring_r * 2), int(ring_r * 2), ang, arc_len)
            p.drawArc(int(cx - ring_r), int(cy - ring_r), int(ring_r * 2), int(ring_r * 2), ang + 180 * 16, arc_len)

        # 3. 3D Particles
        cos_x, sin_x = math.cos(self.rot_x), math.sin(self.rot_x)
        cos_y, sin_y = math.cos(self.rot_y), math.sin(self.rot_y)
        
        # Pre-calc dynamic radius for breathing effect
        if self.state == "SPEAKING":
            dynamic_sr = sr + math.sin(self.phase * 8.0) * 8
        elif self.state == "LISTENING":
            dynamic_sr = sr + math.sin(self.phase * 2.5) * 5
        else:
            dynamic_sr = sr + math.sin(self.phase * 0.5) * 2

        proj = []
        for pt in self.particles:
            # Add micro-vibration noise
            nx = (math.sin(self.phase * 10 + pt.noise_offset) * self.vibration)
            ny = (math.cos(self.phase * 12 + pt.noise_offset) * self.vibration)
            
            sx = pt.base_x * dynamic_sr + nx
            sy = pt.base_y * dynamic_sr + ny
            sz = pt.base_z * dynamic_sr
            
            # Rotate X
            y1 = sy * cos_x - sz * sin_x
            z1 = sy * sin_x + sz * cos_x
            # Rotate Y
            x2 = sx * cos_y + z1 * sin_y
            z2 = -sx * sin_y + z1 * cos_y
            
            proj.append((cx + x2, cy + y1, z2, pt.size_mult))

        proj.sort(key=lambda q: q[2])
        p.setPen(Qt.PenStyle.NoPen)
        for px, py, dz, sm in proj:
            # Depth-based alpha and size
            depth_factor = (dz + sr) / (sr * 2) # 0 to 1
            alpha = int(40 + 215 * depth_factor)
            dot_size = (1.2 + depth_factor * 1.8) * sm
            
            # Color shifts slightly for depth
            p.setBrush(QColor(accent.red(), accent.green(), accent.blue(), alpha))
            p.drawEllipse(QRectF(px - dot_size/2, py - dot_size/2, dot_size, dot_size))


# ══════════════════════════════════════════════════════════════════════════════
#  MODERN LOG VIEW (Rich Chat)
# ══════════════════════════════════════════════════════════════════════════════

class KoraDashboard(QMainWindow):
    status_signal      = pyqtSignal(str)
    log_signal         = pyqtSignal(str, str)
    text_input_signal  = pyqtSignal(str)
    mood_signal        = pyqtSignal(str)
    telemetry_signal   = pyqtSignal(dict)
    re_enable_input_signal = pyqtSignal()

    LOG_COLORS = {
        "USER":         "#ffffff",
        "KORA":         "#00d2ff",
        "SYSTEM":       "#5c6b8c",
        "SYSTEM ERROR": "#ff5555",
        "REMINDER":     "#ffbb33",
    }

    def __init__(self, input_mode: str = "both"):
        super().__init__()
        self.input_mode = input_mode
        self.setWindowTitle("KORA")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(60, 60, 1000, 660) # Slightly larger
        self._drag_pos = QPoint()
        self.theme = get_active_theme()

        # Main background frame
        self.main_frame = QFrame(self)
        self.main_frame.setObjectName("MainFrame")
        self.main_frame.setGeometry(0, 0, 1000, 660)
        
        # Subtle gradient background for the whole app
        accent_dim = QColor(self.theme['accent']).darker(400)
        self.main_frame.setStyleSheet(f"""
            #MainFrame {{
                background-color: {self.theme['main_bg']};
                border: 1px solid {self.theme['border']};
                border-radius: 32px;
            }}
        """)

        layout_container = QVBoxLayout(self.main_frame)
        layout_container.setContentsMargins(0, 0, 0, 0)
        layout_container.setSpacing(0)

        # ── HEADER ────────────────────────────────────────────────────────────
        self.header = QFrame()
        self.header.setFixedHeight(60)
        self.header.setObjectName("Header")
        self.header.setStyleSheet(f"""
            #Header {{
                background: rgba(15, 20, 35, 120);
                border-bottom: 1px solid {self.theme['border']};
                border-top-left-radius: 32px;
                border-top-right-radius: 32px;
            }}
        """)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(30, 0, 20, 0)

        title_label = QLabel("KORA AI")
        tf = QFont("Outfit", 12, QFont.Weight.Bold)
        tf.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4)
        title_label.setFont(tf)
        title_label.setStyleSheet(f"color: {self.theme['accent']};")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        self.min_btn = QPushButton("—")
        self.min_btn.setFixedSize(32, 32)
        self.min_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.min_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 10);
                color: #8899aa;
                font-weight: bold;
                border-radius: 16px;
                border: none;
            }
            QPushButton:hover { background: rgba(255, 255, 255, 20); color: white; }
        """)
        self.min_btn.clicked.connect(self.hide)
        header_layout.addWidget(self.min_btn)

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(32, 32)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255, 255, 255, 10);
                color: #8899aa;
                font-weight: bold;
                border-radius: 16px;
                border: none;
            }
            QPushButton:hover { background: #551122; color: #ff5577; }
        """)
        self.close_btn.clicked.connect(self._close_app)
        header_layout.addWidget(self.close_btn)

        layout_container.addWidget(self.header)

        # ── CONTENT ───────────────────────────────────────────────────────────
        content_wrap = QWidget()
        root = QHBoxLayout(content_wrap)
        root.setContentsMargins(25, 20, 25, 25)
        root.setSpacing(25)

        # ── LEFT: Sphere + Info ───────────────────────────────────────────────
        left = QWidget()
        left.setFixedWidth(380)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(15)

        self.sphere_core = KoraSphereWidget()
        left_layout.addWidget(self.sphere_core, alignment=Qt.AlignmentFlag.AlignCenter)

        self.status_label = QLabel("SYSTEM ONLINE")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sf = QFont("Outfit", 14, QFont.Weight.Bold)
        sf.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 6)
        self.status_label.setFont(sf)
        self.status_label.setStyleSheet(f"color: {self.theme['accent']}; background: transparent;")
        left_layout.addWidget(self.status_label)

        self.mode_label = QLabel(self._get_mode_text())
        self.mode_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mf = QFont("Outfit", 10)
        self.mode_label.setFont(mf)
        self.mode_label.setStyleSheet("color: #6a7b9c; background: transparent;")
        left_layout.addWidget(self.mode_label)
        
        left_layout.addStretch()
        
        # Telemetry panel
        tel_frame = QFrame()
        tel_frame.setFixedHeight(120)
        tel_frame.setStyleSheet(f"""
            QFrame {{
                background: rgba(10, 15, 30, 150);
                border: 1px solid {self.theme['border']};
                border-radius: 20px;
            }}
        """)
        tel_layout = QVBoxLayout(tel_frame)
        tel_layout.setContentsMargins(20, 15, 20, 15)
        
        tel_title = QLabel("SYSTEM METRICS")
        tel_title.setFont(QFont("Outfit", 9, QFont.Weight.Bold))
        tel_title.setStyleSheet("color: #445577;")
        tel_layout.addWidget(tel_title)
        
        grid = QHBoxLayout()
        self.metric_commands = QLabel("CMD: 0")
        self.metric_events = QLabel("EVT: 0")
        self.metric_errors = QLabel("ERR: 0")
        for m in (self.metric_commands, self.metric_events, self.metric_errors):
            m.setStyleSheet("color: #8899aa; font-family: 'Inter'; font-size: 11px;")
            grid.addWidget(m)
        tel_layout.addLayout(grid)
        
        self.metric_last = QLabel("LAST EVENT: -")
        self.metric_last.setStyleSheet("color: #5a6b8c; font-size: 10px;")
        tel_layout.addWidget(self.metric_last)
        
        left_layout.addWidget(tel_frame)

        root.addWidget(left)

        # ── RIGHT: Chat ───────────────────────────────────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(15)

        # Log View
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet(f"""
            QTextEdit {{
                background-color: {self.theme['log_bg']};
                border: 1px solid {self.theme['border']};
                border-radius: 24px;
                padding: 20px;
                color: #e0e6f0;
                font-family: 'Inter', sans-serif;
                font-size: 14px;
                selection-background-color: {self.theme['accent']};
                selection-color: #000;
            }}
            QScrollBar:vertical {{
                background: transparent; width: 6px;
                margin: 10px 4px 10px 0;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255, 255, 255, 20); border-radius: 3px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {self.theme['accent']};
            }}
        """)
        right_layout.addWidget(self.log_view)

        # Input Area
        input_row = QHBoxLayout()
        input_row.setSpacing(12)

        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Message Kora...")
        self.text_input.setFixedHeight(50)
        self.text_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #0a0f1e;
                border: 1px solid {self.theme['border']};
                border-radius: 15px;
                padding: 0 20px;
                color: #ffffff;
                font-family: 'Inter', sans-serif;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 1px solid {self.theme['accent']};
                background-color: #0d1428;
            }}
        """)
        self.text_input.returnPressed.connect(self._submit_text)
        input_row.addWidget(self.text_input)

        self.send_btn = QPushButton("➤")
        self.send_btn.setFixedSize(50, 50)
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {self.theme['accent']}, stop:1 #0099cc);
                border: none;
                border-radius: 15px;
                color: #000;
                font-size: 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{ 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #55eeff, stop:1 {self.theme['accent']});
            }}
            QPushButton:disabled {{ background: #1a2233; color: #445566; }}
        """)
        self.send_btn.clicked.connect(self._submit_text)
        input_row.addWidget(self.send_btn)

        right_layout.addLayout(input_row)

        if input_mode == "voice":
            self.text_input.hide()
            self.send_btn.hide()

        root.addWidget(right, stretch=1)
        layout_container.addWidget(content_wrap)

        # Tray & Signals
        self._init_tray()
        self.status_signal.connect(self.update_status)
        self.log_signal.connect(self.append_log)
        self.mood_signal.connect(self.sphere_core.set_mood)
        self.telemetry_signal.connect(self.update_telemetry)
        self.re_enable_input_signal.connect(self._re_enable_input_on_main_thread)

        self._load_past_logs()
        self._load_telemetry_snapshot()

    def _get_mode_text(self):
        modes = {
            "voice": "🎙 VOICE ACTIVE", 
            "text": "⌨ TEXT ACTIVE", 
            "both": "🎙 VOICE + ⌨ TEXT ACTIVE"
        }
        return modes.get(self.input_mode, "SYSTEM ACTIVE")

    def _init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(self.theme['accent']))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(8, 8, 48, 48)
        painter.end()
        self.tray_icon.setIcon(QIcon(pixmap))
        menu = QMenu()
        show_action = QAction("Open Kora", self)
        show_action.triggered.connect(self.showNormal)
        menu.addAction(show_action)
        exit_action = QAction("Shutdown", self)
        exit_action.triggered.connect(self._close_app)
        menu.addAction(exit_action)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.show()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible(): self.hide()
            else: self.showNormal(); self.activateWindow()

    def _close_app(self):
        os._exit(0)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def _submit_text(self):
        text = self.text_input.text().strip()
        if not text: return
        self.text_input.clear()
        self.send_btn.setEnabled(False)
        self.text_input_signal.emit(text)

    def re_enable_input(self):
        self.re_enable_input_signal.emit()

    def _re_enable_input_on_main_thread(self):
        self.send_btn.setEnabled(True)
        self.text_input.setFocus()

    def update_status(self, text):
        raw = text.upper()
        self.status_label.setText(raw)
        if   "LISTENING"   in raw: self.sphere_core.state = "LISTENING"
        elif "PROCESSING"  in raw: self.sphere_core.state = "PROCESSING"
        elif "SPEAKING"    in raw: self.sphere_core.state = "SPEAKING"
        else:                      self.sphere_core.state = "IDLE"

    def append_log(self, sender, message):
        color = self.LOG_COLORS.get(sender.upper(), "#aaaaaa")
        accent = self.theme['accent']
        
        # Determine bubble style
        is_user = sender.upper() == "USER"
        
        align = "right" if is_user else "left"
        bg_color = "rgba(40, 50, 80, 100)" if is_user else "rgba(20, 25, 45, 180)"
        border_color = accent if not is_user else "rgba(255, 255, 255, 40)"
        
        # Clean relevant memory prefix from LLM replies for cleaner UI
        display = message
        if message.startswith("[Relevant memory:") and "\n\nUser says:" in message:
            display = message.split("\n\nUser says:", 1)[1].strip()
        
        safe_sender = escape(str(sender).upper())
        safe_display = escape(str(display)).replace("\n", "<br/>")
        
        # Premium Bubble HTML
        html = f"""
        <div style="margin: 12px 0; text-align: {align};">
            <span style="color: {color}; font-weight: bold; font-size: 10px; margin-bottom: 4px; display: inline-block;">{safe_sender}</span>
            <div style="
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 18px;
                padding: 12px 18px;
                display: inline-block;
                max-width: 80%;
                text-align: left;
                color: #f0f4f8;
                font-size: 14px;
                line-height: 1.5;
            ">
                {safe_display}
            </div>
        </div>
        """
        self.log_view.append(html)
        self.log_view.moveCursor(QTextCursor.MoveOperation.End)

    def _load_past_logs(self):
        try:
            from storage import load_all_logs
            entries = load_all_logs()
            if not entries: return
            self.log_view.append('<div style="color: #3a4b6c; font-size: 10px; text-align: center; margin: 20px 0;">─── ARCHIVED SESSIONS ───</div>')
            for ts, role, content in entries:
                self.append_log(role, content)
            self.log_view.append('<div style="color: #3a4b6c; font-size: 10px; text-align: center; margin: 20px 0;">─── NEW SESSION ───</div>')
        except Exception as e:
            print(f"[GUI] Log restore error: {e}")

    def _load_telemetry_snapshot(self):
        try:
            from storage import load_telemetry_summary
            self.update_telemetry(load_telemetry_summary())
        except Exception: pass

    def update_telemetry(self, summary):
        if not isinstance(summary, dict): return
        self.metric_commands.setText(f"COMMANDS: {summary.get('total_commands', 0)}")
        self.metric_events.setText(f"EVENTS: {summary.get('total_events', 0)}")
        self.metric_errors.setText(f"ERRORS: {summary.get('total_errors', 0)}")
        last = summary.get('last_event') or '-'
        if last != '-': last = last.split(' ')[1][:5]
        self.metric_last.setText(f"LAST ACTIVITY: {last}")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
