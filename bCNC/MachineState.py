# MachineState - Observable wrapper around CNC.vars
#
# Provides a clean API for reading/writing machine state with
# change notification support. During the migration period, this
# acts as a facade: CNC.vars remains the backing store so existing
# code continues to work unchanged. New code should prefer using
# MachineState methods.

import threading
from collections import defaultdict


class _BatchContext:
    """Context manager for batched MachineState updates."""

    def __init__(self, state):
        self._state = state

    def __enter__(self):
        with self._state._lock:
            self._state._batch_depth += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        with self._state._lock:
            self._state._batch_depth -= 1
            should_flush = self._state._batch_depth == 0
            if should_flush:
                changes = dict(self._state._batch_changes)
                self._state._batch_changes.clear()
                all_notifications = []
                for key, value in changes.items():
                    observers = list(
                        self._state._observers.get(key, []))
                    observers += list(
                        self._state._observers.get("*", []))
                    all_notifications.append((key, value, observers))
            else:
                all_notifications = []

            for key, value, observers in all_notifications:
                self._state._notify(key, value, None, observers)


class MachineState:
    """Observable wrapper around CNC.vars.

    Provides:
    - Thread-safe writes with change notification
    - Grouped/batch updates (set multiple vars, notify once)
    - Observer pattern for reacting to state changes

    The backing store is CNC.vars itself, so existing code that
    reads CNC.vars directly continues to work. Over time, reads
    can migrate to use this class's get() method.
    """

    def __init__(self, cnc_vars):
        """Initialize with a reference to the CNC.vars dict.

        Args:
            cnc_vars: The CNC.vars dictionary (class attribute of CNC).
        """
        self._vars = cnc_vars
        self._lock = threading.Lock()
        self._observers = defaultdict(list)
        self._batch_depth = 0
        self._batch_changes = {}

    def get(self, key, default=None):
        """Read a state variable.

        Args:
            key: Variable name (e.g. "wx", "state", "running").
            default: Value to return if key doesn't exist.
        """
        return self._vars.get(key, default)

    def set(self, key, value):
        """Set a state variable with change notification.

        If the value actually changed, observers for that key are
        notified. During a batch(), notifications are deferred.

        Args:
            key: Variable name.
            value: New value.
        """
        with self._lock:
            old = self._vars.get(key)
            self._vars[key] = value
            if old != value:
                if self._batch_depth > 0:
                    self._batch_changes[key] = value
                else:
                    observers = list(self._observers.get(key, []))
                    observers += list(self._observers.get("*", []))

        # Notify outside the lock to prevent deadlocks
        if old != value and self._batch_depth == 0:
            self._notify(key, value, old, observers)

    def update(self, mapping):
        """Set multiple variables at once, notifying for each change.

        Args:
            mapping: Dict of {key: value} pairs.
        """
        with self.batch():
            for key, value in mapping.items():
                self.set(key, value)

    def batch(self):
        """Context manager for batching multiple sets into one notification round.

        Usage:
            with state.batch():
                state.set("wx", 10.0)
                state.set("wy", 20.0)
            # observers notified here for all changed keys
        """
        return _BatchContext(self)

    def observe(self, key, callback):
        """Register an observer for a state variable.

        Args:
            key: Variable name to watch, or "*" for all changes.
            callback: Called as callback(key, new_value, old_value).
        """
        with self._lock:
            if callback not in self._observers[key]:
                self._observers[key].append(callback)

    def unobserve(self, key, callback):
        """Remove an observer.

        Args:
            key: Variable name or "*".
            callback: Previously registered callback.
        """
        with self._lock:
            try:
                self._observers[key].remove(callback)
            except ValueError:
                pass

    def _notify(self, key, new_value, old_value, observers):
        """Invoke observer callbacks outside the lock."""
        for callback in observers:
            try:
                callback(key, new_value, old_value)
            except Exception:
                pass

    def __getitem__(self, key):
        """Dict-style read access for backward compatibility."""
        return self._vars[key]

    def __setitem__(self, key, value):
        """Dict-style write access with change notification."""
        self.set(key, value)

    def __contains__(self, key):
        return key in self._vars

    def keys(self):
        return self._vars.keys()
