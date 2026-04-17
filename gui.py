import sys
import math
import random
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QRadialGradient, QFont, QPainterPath

class AuraHUD(QMainWindow):
    status_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        # Frameless, transparent floating window
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(100, 100, 600, 600)  # Larger canvas to capture the soft glow

        self.phase = 0.0  # Drives the breathing/pulsing animation
        self.status_text = "AURA AWAKENING"
        self.status_signal.connect(self.update_status)
        
        # Initialize an organic particle system
        self.particles = []
        for _ in range(50):
            # [current_angle, rotation_speed, orbit_radius, particle_size, color]
            self.particles.append([
                random.uniform(0, 360), 
                random.uniform(0.3, 1.5), 
                random.uniform(80, 220),
                random.uniform(2, 5),
                random.choice([QColor(0, 210, 255, 180),  # Cyan
                               QColor(200, 50, 255, 150), # Magenta
                               QColor(255, 255, 255, 100)]) # Soft White
            ])

        # Core heartbeat timer (approx 60fps)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(16)

    def update_status(self, text):
        self.status_text = text.upper()

    def animate(self):
        self.phase += 0.04
        # Increment particle angles
        for p in self.particles:
            p[0] = (p[0] + p[1]) % 360
            
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        cx, cy = self.width() / 2, self.height() / 2
        
        # Base Breathing calculation using sine
        breathe = math.sin(self.phase) * 15  # Fluctuate orbital radius softly
        
        # --- Layer 1: Deep Outer Aura (Violet/Magenta Glow) ---
        outer_grad = QRadialGradient(cx, cy, 180 + breathe)
        outer_grad.setColorAt(0, QColor(138, 43, 226, 50))  # Deep violet
        outer_grad.setColorAt(0.5, QColor(200, 50, 255, 20))
        outer_grad.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(outer_grad)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(int(cx - 200 - breathe), int(cy - 200 - breathe), int(400 + breathe*2), int(400 + breathe*2))
        
        # --- Layer 2: Core Energy Reactor (Cyan/Ice Glow) ---
        core_grad = QRadialGradient(cx, cy, 100 - breathe * 0.5)
        core_grad.setColorAt(0, QColor(0, 255, 255, 180)) 
        core_grad.setColorAt(0.6, QColor(0, 150, 255, 80))
        core_grad.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(core_grad)
        p.drawEllipse(int(cx - 120 + breathe*0.5), int(cy - 120 + breathe*0.5), int(240 - breathe), int(240 - breathe))
        
        # --- Layer 3: Orbiting Particles ---
        for pt in self.particles:
            angle_rad = math.radians(pt[0])
            r = pt[2] + math.cos(self.phase + pt[1]) * 8 # Give particles a slight organic wobble
            px = cx + math.cos(angle_rad) * r
            py = cy + math.sin(angle_rad) * r
            p.setBrush(pt[4])
            p.drawEllipse(int(px - pt[3]/2), int(py - pt[3]/2), int(pt[3]), int(pt[3]))
            
        # --- Layer 4: Minimal Orbital Rings ---
        p.setBrush(Qt.GlobalColor.transparent)
        
        # Faint outer track
        ring_pen = QPen(QColor(0, 255, 255, 50))
        ring_pen.setWidthF(1.0)
        p.setPen(ring_pen)
        p.drawEllipse(int(cx - 160), int(cy - 160), 320, 320)
        
        # Rotating inner arcs
        ring_pen.setColor(QColor(200, 100, 255, 140))
        ring_pen.setWidth(2)
        p.setPen(ring_pen)
        
        span = 60 * 16 # Qt arc spans are 1/16th of a degree
        start_angle = int((math.degrees(self.phase * 0.3)) % 360 * 16)
        p.drawArc(int(cx - 140), int(cy - 140), 280, 280, start_angle, span)
        p.drawArc(int(cx - 140), int(cy - 140), 280, 280, start_angle + (180*16), span)

        # --- Layer 5: Sleek Typography ---
        p.setPen(QColor(255, 255, 255, 230))
        font = QFont("Segoe UI", 11)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 5) # Wide, cinematic letter spacing
        p.setFont(font)
        
        # Center the status text at the bottom
        fm = p.fontMetrics()
        text_width = fm.horizontalAdvance(self.status_text)
        p.drawText(int(cx - text_width/2), int(cy + 220), self.status_text)