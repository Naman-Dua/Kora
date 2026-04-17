import sys
import math
import random
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QTextEdit, QFrame)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QDateTime, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QRadialGradient, QLinearGradient, QFont, QPainterPath

from monitor import get_system_vitals


# ==============================================================================
# CUSTOM RENDERED AESTHETIC WIDGETS
# ==============================================================================

class GlassPanel(QFrame):
    """ Custom panel drawing a highly aesthetic, semi-transparent frosted glass backing """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = QRectF(self.rect().adjusted(2, 2, -2, -2))
        path = QPainterPath()
        path.addRoundedRect(rect, 20, 20)
        
        # Deep space / neon glassmorphism gradient
        grad = QLinearGradient(0, 0, self.width(), self.height())
        grad.setColorAt(0, QColor(36, 20, 68, 180))    # Deep purple
        grad.setColorAt(1, QColor(10, 14, 23, 200))    # Void black
        p.fillPath(path, grad)
        
        # Soft glowing bright cyan/magenta edge
        border_grad = QLinearGradient(0, 0, self.width(), self.height())
        border_grad.setColorAt(0, QColor(0, 210, 255, 80))
        border_grad.setColorAt(1, QColor(200, 50, 255, 40))
        pen = QPen(border_grad, 2)
        p.setPen(pen)
        p.drawPath(path)


class CircularGauge(QWidget):
    """ A sleek, sci-fi holographic circular read-out gauge """
    def __init__(self, title, color, parent=None):
        super().__init__(parent)
        self.title = title
        self.color = color
        self.value = 0
        self.setMinimumSize(140, 140)
        
    def setValue(self, val):
        self.value = val
        self.update()
        
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect().adjusted(15, 15, -15, -15)
        
        # Faint background tracking ring
        pen = QPen(QColor(255, 255, 255, 15))
        pen.setWidth(6)
        p.setPen(pen)
        p.drawArc(rect, 0, 360 * 16)
        
        # Active data arc representing metrics
        pen.setColor(self.color)
        pen.setWidth(8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        span = int((self.value / 100.0) * -360 * 16) # draw backwards for aesthetic
        p.drawArc(rect, 90 * 16, span)
        
        # Center Number Value
        p.setPen(QColor(255, 255, 255, 240))
        font = QFont("Segoe UI", 18, QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(self.rect().adjusted(0, -10, 0, 0), Qt.AlignmentFlag.AlignCenter, f"{self.value}%")
        
        # Bottom Title
        p.setPen(self.color)
        font = QFont("Consolas", 10, QFont.Weight.Bold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3)
        p.setFont(font)
        p.drawText(self.rect().adjusted(0, 40, 0, 0), Qt.AlignmentFlag.AlignCenter, self.title)


class AuraOrbWidget(QWidget):
    """ The breathing orb core, refined for peak visual smoothness """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(450, 450)
        self.phase = 0.0
        self.particles = []
        for _ in range(70):
            self.particles.append([
                random.uniform(0, 360), random.uniform(0.3, 1.0), 
                random.uniform(60, 180), random.uniform(1.5, 4),
                random.choice([QColor(0, 210, 255, 200), QColor(200, 50, 255, 150), QColor(255, 255, 255, 150)])
            ])
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(16)

    def animate(self):
        self.phase += 0.03
        for p in self.particles: p[0] = (p[0] + p[1]) % 360
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2
        breathe = math.sin(self.phase) * 12 
        
        # Deep backdrop aura
        outer_grad = QRadialGradient(cx, cy, 180 + breathe)
        outer_grad.setColorAt(0, QColor(90, 20, 200, 40))  
        outer_grad.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(outer_grad)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(int(cx - 200 - breathe), int(cy - 200 - breathe), int(400 + breathe*2), int(400 + breathe*2))
        
        # Hot inner core
        core_grad = QRadialGradient(cx, cy, 80 - breathe * 0.5)
        core_grad.setColorAt(0, QColor(0, 255, 255, 200)) 
        core_grad.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(core_grad)
        p.drawEllipse(int(cx - 110 + breathe*0.5), int(cy - 110 + breathe*0.5), int(220 - breathe), int(220 - breathe))
        
        # Jagged Neural Waveform
        eq_pen = QPen(QColor(0, 255, 255, 150))
        eq_pen.setWidthF(2.5)
        p.setPen(eq_pen)
        p.setBrush(Qt.GlobalColor.transparent)
        path = QPainterPath()
        points = 60
        width = 180
        start_x = cx - width/2
        step = width / points
        
        path.moveTo(start_x, cy)
        for i in range(1, points):
            x = start_x + (i * step)
            y_offset = (math.sin(self.phase * 5.0 + i * 1.5) + math.cos(self.phase * 7.0 - i * 0.5)) * 20
            dampen = math.sin((i / points) * math.pi)
            y = cy + (y_offset * dampen)
            path.lineTo(x, y)
        path.lineTo(start_x + width, cy)
        p.drawPath(path)

        # Ambient floating particles
        p.setPen(Qt.PenStyle.NoPen)
        for pt in self.particles:
            r = pt[2] + math.cos(self.phase * 0.5 + pt[1]) * 10 
            px = cx + math.cos(math.radians(pt[0])) * r
            py = cy + math.sin(math.radians(pt[0])) * r
            p.setBrush(pt[4])
            p.drawEllipse(int(px - pt[3]/2), int(py - pt[3]/2), int(pt[3]), int(pt[3]))
            
        # Outer containment glass ring
        p.setBrush(Qt.GlobalColor.transparent)
        ring_pen = QPen(QColor(0, 255, 255, 40))
        ring_pen.setWidthF(1.5)
        p.setPen(ring_pen)
        p.drawEllipse(int(cx - 150), int(cy - 150), 300, 300)


# ==============================================================================
# MAIN DASHBOARD INTERFACE
# ==============================================================================

class AuraDashboard(QMainWindow):
    status_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str, str) # sender, message

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AURA CORE COMMAND")
        
        # Completely translucent, borderless glass window
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(50, 50, 1100, 650)
        
        # Aggressive aesthetic stylesheet for elements not utilizing custom painting
        self.setStyleSheet("""
            QTextEdit { 
                background-color: transparent; 
                color: #e6edf3; 
                font-family: 'Consolas';
                font-size: 13px;
                border: none;
            }
            QScrollBar:vertical {
                border: none; background: rgba(0,0,0,0); width: 8px; margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0, 210, 255, 80); border-radius: 4px; min-height: 20px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)

        # Main Layout inside the invisible window bounds
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(25)

        # --- LEFT: Visual Orb Core inside Glass Panel ---
        self.left_panel = GlassPanel()
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(20, 40, 20, 40)
        
        self.orb = AuraOrbWidget()
        
        self.status_label = QLabel("SYSTEM STANDBY")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont("Segoe UI", 18, QFont.Weight.Bold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 8)
        self.status_label.setFont(font)
        self.status_label.setStyleSheet("color: #FFFFFF;")
        
        left_layout.addWidget(self.orb, alignment=Qt.AlignmentFlag.AlignCenter)
        left_layout.addStretch()
        left_layout.addWidget(self.status_label)
        main_layout.addWidget(self.left_panel, stretch=5)

        # --- RIGHT: Split Telemetry and Terminal over Glass ---
        right_container = QVBoxLayout()
        right_container.setSpacing(25)

        # Top Right: Translucent Terminal
        self.terminal_panel = GlassPanel()
        term_layout = QVBoxLayout(self.terminal_panel)
        
        hdr = QLabel("DATA STREAM // COMMS")
        hdr_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        hdr_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4)
        hdr.setFont(hdr_font)
        hdr.setStyleSheet("color: #00d2ff;")
        
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        self.log_signal.connect(self.append_log)
        
        term_layout.addWidget(hdr)
        term_layout.addWidget(self.terminal)
        right_container.addWidget(self.terminal_panel, stretch=6)

        # Bottom Right: Holographic Telemetry Gauges
        self.telemetry_panel = GlassPanel()
        tel_layout = QHBoxLayout(self.telemetry_panel)
        
        self.cpu_gauge = CircularGauge("CPU CORE", QColor(0, 210, 255, 200))
        self.ram_gauge = CircularGauge("RAM LOAD", QColor(200, 50, 255, 200))
        self.bat_gauge = CircularGauge("POWER", QColor(0, 255, 100, 200))
        
        tel_layout.addWidget(self.cpu_gauge)
        tel_layout.addWidget(self.ram_gauge)
        tel_layout.addWidget(self.bat_gauge)
        right_container.addWidget(self.telemetry_panel, stretch=4)
        
        main_layout.addLayout(right_container, stretch=4)

        # Core wiring
        self.status_signal.connect(self.update_status)
        self.tel_timer = QTimer(self)
        self.tel_timer.timeout.connect(self.update_telemetry)
        self.tel_timer.start(1500)

    def append_log(self, sender, message):
        time_str = QDateTime.currentDateTime().toString("HH:mm:ss")
        if sender == "USER":
            color = "#ff3399" # Hot pink text for users
        elif sender == "AURA":
            color = "#00d2ff" # Bright Cyan text for AI
        else:
            color = "#6e7681" # Cool gray for system

        html = f"<div style='margin-bottom:8px;'><span style='color: #6e7681;'>[{time_str}]</span> <b style='color: {color};'>[{sender}]</b> <br/><span style='color: #e6edf3;'>{message}</span></div>"
        self.terminal.append(html)
        
        # Auto-scroll to bottom
        scrollbar = self.terminal.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def update_status(self, text):
        self.status_label.setText(text.upper())

    def update_telemetry(self):
        vitals = get_system_vitals()
        self.cpu_gauge.setValue(int(vitals.get("cpu", 0)))
        self.ram_gauge.setValue(int(vitals.get("ram", 0)))
        
        bat = vitals.get("battery", "AC Power")
        if isinstance(bat, (int, float)):
             self.bat_gauge.setValue(int(bat))
        else:
             self.bat_gauge.setValue(100)