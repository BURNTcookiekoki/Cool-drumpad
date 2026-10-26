
import sys
import time
import threading
import serial
import serial.tools.list_ports
import pygame
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QGridLayout, QVBoxLayout,
    QPushButton, QLabel, QFileDialog, QComboBox, QMessageBox
)
from PySide6.QtCore import QTimer

pygame.mixer.init()

class DrumApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Custom ESP32 Drum Machine")
        self.resize(600, 500)

        self.sounds = [None] * 9
        self.recording = False
        self.looping = False
        self.pattern = []
        self.start_time = 0
        self.loop_start = 0
        self.loop_length = 0
        self.last_loop_event = -1
        self.serial_port = None
        self.lock = threading.Lock()

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        self.status = QLabel("Connect your ESP32 to begin")
        layout.addWidget(self.status)

        self.ports = QComboBox()
        self.refresh_ports()
        layout.addWidget(self.ports)

        connect = QPushButton("Connect ESP32")
        connect.clicked.connect(self.connect_esp32)
        layout.addWidget(connect)

        grid = QGridLayout()
        layout.addLayout(grid)

        for i in range(9):
            column = i % 3
            row = i // 3

            pad = QPushButton(f"PAD {i + 1}\nLoad sound")
            pad.setMinimumHeight(85)
            pad.clicked.connect(lambda checked=False, n=i: self.load_sound(n))
            pad.setStyleSheet("font-size: 16px;")
            grid.addWidget(pad, row, column)

            hit = QPushButton(f"Play {i + 1}")
            hit.clicked.connect(lambda checked=False, n=i: self.hit(n))
            grid.addWidget(hit, row + 3, column)

        controls = QGridLayout()
        layout.addLayout(controls)

        self.record_button = QPushButton("Record")
        self.record_button.clicked.connect(self.toggle_record)
        controls.addWidget(self.record_button, 0, 0)

        self.loop_button = QPushButton("Loop")
        self.loop_button.clicked.connect(self.toggle_loop)
        controls.addWidget(self.loop_button, 0, 1)

        discard = QPushButton("Discard")
        discard.clicked.connect(self.discard)
        controls.addWidget(discard, 0, 2)

        self.timer = QTimer()
        self.timer.timeout.connect(self.check_loop)
        self.timer.start(5)

    def refresh_ports(self):
        self.ports.clear()
        for port in serial.tools.list_ports.comports():
            self.ports.addItem(port.device)

    def connect_esp32(self):
        try:
            port = self.ports.currentText()
            if not port:
                self.refresh_ports()
                return
            self.serial_port = serial.Serial(port, 115200, timeout=0.1)
            threading.Thread(target=self.read_serial, daemon=True).start()
            self.status.setText(f"Connected to {port}")
        except Exception as e:
            QMessageBox.critical(self, "Connection error", str(e))

    def read_serial(self):
        while self.serial_port and self.serial_port.is_open:
            try:
                command = self.serial_port.readline().decode(
                    "utf-8", errors="ignore"
                ).strip().upper()
                if command.startswith("PAD"):
                    try:
                        n = int(command[3:]) - 1
                        if 0 <= n < 9:
                            self.hit(n)
                    except ValueError:
                        pass
                elif command == "RECORD":
                    QTimer.singleShot(0, self.toggle_record)
                elif command == "LOOP":
                    QTimer.singleShot(0, self.toggle_loop)
                elif command == "DISCARD":
                    QTimer.singleShot(0, self.discard)
            except Exception:
                time.sleep(0.05)

    def load_sound(self, n):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose drum sound", "", "WAV audio (*.wav)"
        )
        if path:
            try:
                self.sounds[n] = pygame.mixer.Sound(path)
                self.status.setText(f"Loaded sound for pad {n + 1}")
            except Exception as e:
                QMessageBox.warning(self, "Audio error", str(e))

    def hit(self, n, should_record=True):
        if self.sounds[n]:
            self.sounds[n].play()

        if self.recording and should_record:
            self.pattern.append(
                (time.monotonic() - self.start_time, n)
            )

    def toggle_record(self):
        if not self.recording:
            self.pattern = []
            self.looping = False
            self.recording = True
            self.start_time = time.monotonic()
            self.record_button.setText("Stop Recording")
            self.status.setText("Recording drum hits...")
        else:
            self.recording = False
            self.record_button.setText("Record")
            if self.pattern:
                self.loop_length = max(
                    0.25, time.monotonic() - self.start_time
                )
            self.status.setText(
                f"Recording stopped — {len(self.pattern)} hits"
            )

    def toggle_loop(self):
        if self.recording:
            self.toggle_record()

        if not self.pattern:
            self.status.setText("Record a pattern first")
            return

        self.looping = not self.looping
        self.loop_button.setText("Stop Loop" if self.looping else "Loop")
        self.loop_start = time.monotonic()
        self.last_loop_event = -1
        self.status.setText("Loop playing" if self.looping else "Loop stopped")

    def check_loop(self):
        if not self.looping or not self.pattern or self.loop_length <= 0:
            return

        elapsed = time.monotonic() - self.loop_start
        cycle = int(elapsed / self.loop_length)
        position = elapsed % self.loop_length

        # Reset event tracking at the start of each loop.
        if cycle != self.last_loop_event:
            self.last_loop_event = cycle
            self._played_events = set()

        for i, (event_time, pad) in enumerate(self.pattern):
            key = (cycle, i)
            if event_time <= position and key not in self._played_events:
                self.hit(pad, should_record=False)
                self._played_events.add(key)

    def discard(self):
        self.pattern = []
        self.looping = False
        self.recording = False
        self.loop_length = 0
        self.record_button.setText("Record")
        self.loop_button.setText("Loop")
        self.status.setText("Recording discarded")

    def closeEvent(self, event):
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        pygame.mixer.quit()
        event.accept()

app = QApplication(sys.argv)
window = DrumApp()
window.show()
sys.exit(app.exec())
