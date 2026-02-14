# Qt Serial Monitor - QTimer-based replacement for Tk.after() polling
#
# Replaces monitorSerial() / self.after(MONITOR_AFTER, ...) with a
# QTimer that drains Sender.log queue and updates the UI via signals.

import sys
import time
import traceback
from queue import Empty

from PySide6.QtCore import QTimer

from CNC import CNC
from Sender import NOT_CONNECTED, STATECOLOR, STATECOLORDEF, Sender


MONITOR_INTERVAL_MS = 200  # match original MONITOR_AFTER


class SerialMonitor:
    """QTimer-based serial monitor that bridges Sender queues to Qt signals.

    Periodically drains the Sender.log queue and emits appropriate
    Qt signals for each message type.  Also checks position updates,
    probe updates, and run progress.
    """

    def __init__(self, sender, signals):
        """
        Args:
            sender: The Sender instance (owns log/queue/pendant queues).
            signals: An AppSignals instance for emitting updates.
        """
        self.sender = sender
        self.signals = signals

        self._insertCount = 0

        self._timer = QTimer()
        self._timer.setInterval(MONITOR_INTERVAL_MS)
        self._timer.timeout.connect(self._poll)

    def start(self):
        """Start the monitoring timer."""
        self._timer.start()

    def stop(self):
        """Stop the monitoring timer."""
        self._timer.stop()

    def _poll(self):
        """Single timer tick — drain queues and emit signals."""
        try:
            self._drain_log()
            self._check_pendant()
            self._check_pendant_file()
            self._update_position()
            self._update_g_state()
            self._update_probe()
            self._update_generic()
            self._update_run_progress()
        except Exception:
            typ, val, tb = sys.exc_info()
            traceback.print_exception(typ, val, tb)

    # ------------------------------------------------------------------
    # Drain the Sender.log queue
    # ------------------------------------------------------------------
    def _drain_log(self):
        t = time.time()
        while self.sender.log.qsize() > 0 and time.time() - t < 0.1:
            try:
                msg, line = self.sender.log.get_nowait()
                line = str(line).rstrip("\n")
            except Empty:
                break

            if msg == Sender.MSG_BUFFER:
                self.signals.serial_buffer.emit(line)

            elif msg == Sender.MSG_SEND:
                self.signals.serial_send.emit(line)

            elif msg == Sender.MSG_RECEIVE:
                self.signals.serial_receive.emit(line)
                if self._insertCount:
                    self._insertCount += 1
                elif line and line[0] in ("[", "$"):
                    self._insertCount = 1

            elif msg == Sender.MSG_OK:
                self.signals.serial_ok.emit(line)
                self._insertCount = 0

            elif msg == Sender.MSG_ERROR:
                self.signals.serial_error.emit(line)
                self._insertCount = 0

            elif msg == Sender.MSG_RUNEND:
                self.signals.serial_run_end.emit(line)
                self.signals.status_message.emit(line)

            elif msg == Sender.MSG_CLEAR:
                self.signals.serial_clear.emit()

    # ------------------------------------------------------------------
    # Check pendant queue
    # ------------------------------------------------------------------
    def _check_pendant(self):
        try:
            cmd = self.sender.pendant.get_nowait()
            self.sender.executeCommand(cmd)
        except Empty:
            pass

    def _check_pendant_file(self):
        uploaded = getattr(self.sender, '_pendantFileUploaded', None)
        if uploaded is not None:
            self.sender.load(uploaded)
            self.sender._pendantFileUploaded = None

    # ------------------------------------------------------------------
    # Position / state updates
    # ------------------------------------------------------------------
    def _update_position(self):
        if not self.sender._posUpdate:
            return

        state = CNC.vars["state"]
        try:
            CNC.vars["color"] = STATECOLOR[state]
        except KeyError:
            if self.sender._alarm:
                CNC.vars["color"] = STATECOLOR["Alarm"]
            else:
                CNC.vars["color"] = STATECOLORDEF

        self.sender._pause = "Hold" in state
        self.signals.state_changed.emit(state, CNC.vars["color"])
        self.signals.position_updated.emit(
            CNC.vars["wx"], CNC.vars["wy"], CNC.vars["wz"],
            CNC.vars["mx"], CNC.vars["my"], CNC.vars["mz"],
        )
        self.sender._posUpdate = False

    def _update_g_state(self):
        if self.sender._gUpdate:
            self.signals.g_state_updated.emit()
            self.sender._gUpdate = False

    def _update_probe(self):
        if self.sender._probeUpdate:
            self.signals.probe_updated.emit()
            self.sender._probeUpdate = False

    def _update_generic(self):
        if self.sender._update:
            update_name = self.sender._update
            self.sender._update = None
            self.signals.generic_update.emit(update_name)

    # ------------------------------------------------------------------
    # Run progress
    # ------------------------------------------------------------------
    def _update_run_progress(self):
        if not self.sender.running:
            return

        completed = self.sender._runLines - self.sender.queue.qsize()
        total = self.sender._gcount
        self.signals.run_progress.emit(completed, total)

        fill = Sender.getBufferFill(self.sender)
        self.signals.buffer_fill.emit(fill)

        if self.sender._gcount >= self.sender._runLines:
            self.sender.runEnded()
