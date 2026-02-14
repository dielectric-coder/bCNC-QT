# Qt Terminal Panel - Serial communication log and command entry
#
# Replaces the Tkinter TerminalPage with a QWidget containing
# a log view (QListWidget) and command entry (QLineEdit).

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QLineEdit,
    QLabel, QPushButton,
)


class TerminalPanel(QWidget):
    """Serial terminal panel with log display and command input.

    Shows sent/received serial messages with color coding and
    provides a command line for MDI input.
    """

    MAX_LOG_LINES = 1000
    TRIM_TO = 500

    def __init__(self, sender, signals, parent=None):
        super().__init__(parent)
        self.sender = sender
        self.signals = signals
        self._history = list(sender.history)
        self._history_pos = None
        self._insertCount = 0

        # --- Buffer list (pending commands) ---
        self._buffer = QListWidget()
        self._buffer.setMaximumHeight(80)

        # --- Terminal log ---
        self._log = QListWidget()
        self._log.setAlternatingRowColors(True)

        # --- Command entry ---
        cmd_layout = QHBoxLayout()
        cmd_layout.setContentsMargins(0, 0, 0, 0)
        self._cmd_label = QLabel("Command:")
        self._cmd_input = QLineEdit()
        self._cmd_input.setPlaceholderText(
            "G-code or macro (RESET, HOME, RUN, ...)")
        self._cmd_input.returnPressed.connect(self._on_command)
        self._send_btn = QPushButton("Send")
        self._send_btn.clicked.connect(self._on_command)
        cmd_layout.addWidget(self._cmd_label)
        cmd_layout.addWidget(self._cmd_input, 1)
        cmd_layout.addWidget(self._send_btn)

        # --- Layout ---
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(QLabel("Buffer:"))
        layout.addWidget(self._buffer)
        layout.addWidget(QLabel("Terminal:"))
        layout.addWidget(self._log, 1)
        layout.addLayout(cmd_layout)

        # --- Wire signals ---
        signals.serial_buffer.connect(self._on_buffer)
        signals.serial_send.connect(self._on_send)
        signals.serial_receive.connect(self._on_receive)
        signals.serial_ok.connect(self._on_ok)
        signals.serial_error.connect(self._on_error)
        signals.serial_run_end.connect(self._on_run_end)
        signals.serial_clear.connect(self._on_clear)

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------
    def _on_buffer(self, line):
        self._buffer.addItem(line)

    def _on_send(self, line):
        item = QListWidgetItem(line)
        item.setForeground(QColor("blue"))
        self._log.addItem(item)
        self._trim_log()

    def _on_receive(self, line):
        self._log.addItem(line)
        if self._insertCount:
            self._insertCount += 1
        elif line and line[0] in ("[", "$"):
            self._insertCount = 1
        self._trim_log()

    def _on_ok(self, line):
        # Move top buffer item into log, then add OK line
        if self._buffer.count() > 0:
            buf_item = self._buffer.takeItem(0)
            colored = QListWidgetItem(buf_item.text())
            colored.setForeground(QColor("blue"))
            if self._insertCount:
                pos = self._log.count() - self._insertCount
                self._insertCount = 0
            else:
                pos = self._log.count()
            self._log.insertItem(pos, colored)
        self._log.addItem(line)
        self._log.scrollToBottom()
        self._trim_log()

    def _on_error(self, line):
        # Move top buffer item into log, then add error line
        if self._buffer.count() > 0:
            buf_item = self._buffer.takeItem(0)
            colored = QListWidgetItem(buf_item.text())
            colored.setForeground(QColor("blue"))
            if self._insertCount:
                pos = self._log.count() - self._insertCount
                self._insertCount = 0
            else:
                pos = self._log.count()
            self._log.insertItem(pos, colored)
        err_item = QListWidgetItem(line)
        err_item.setForeground(QColor("red"))
        self._log.addItem(err_item)
        self._log.scrollToBottom()
        self._trim_log()

    def _on_run_end(self, line):
        item = QListWidgetItem(line)
        item.setForeground(QColor("magenta"))
        self._log.addItem(item)
        self._log.scrollToBottom()

    def _on_clear(self):
        self._buffer.clear()

    # ------------------------------------------------------------------
    # Command entry
    # ------------------------------------------------------------------
    def _on_command(self):
        line = self._cmd_input.text().strip()
        if not line:
            return
        self._cmd_input.clear()

        # Add to history
        self._history.append(line)
        if len(self._history) > 500:
            self._history = self._history[-500:]
        self._history_pos = None

        # Try to execute as gcode first, then as command
        try:
            if not self.sender.executeGcode(line):
                self.sender.executeCommand(line)
        except Exception as e:
            item = QListWidgetItem(f"Error: {e}")
            item.setForeground(QColor("red"))
            self._log.addItem(item)

    def keyPressEvent(self, event):
        """Handle Up/Down arrow for command history."""
        if self._cmd_input.hasFocus():
            if event.key() == Qt.Key.Key_Up:
                self._history_up()
                return
            elif event.key() == Qt.Key.Key_Down:
                self._history_down()
                return
        super().keyPressEvent(event)

    def _history_up(self):
        if not self._history:
            return
        if self._history_pos is None:
            self._history_pos = len(self._history) - 1
        elif self._history_pos > 0:
            self._history_pos -= 1
        self._cmd_input.setText(self._history[self._history_pos])

    def _history_down(self):
        if self._history_pos is None:
            return
        if self._history_pos < len(self._history) - 1:
            self._history_pos += 1
            self._cmd_input.setText(self._history[self._history_pos])
        else:
            self._history_pos = None
            self._cmd_input.clear()

    def _trim_log(self):
        """Trim log to avoid unbounded memory use."""
        if self._log.count() > self.MAX_LOG_LINES:
            for _ in range(self._log.count() - self.TRIM_TO):
                self._log.takeItem(0)
