# EventBus - Toolkit-independent publish/subscribe event system
#
# Provides decoupled communication between components without
# requiring Tkinter virtual events. During the migration period,
# both this EventBus and Tkinter events can coexist.

import threading
from collections import defaultdict


class EventBus:
    """Simple publish/subscribe event bus.

    Thread-safe event dispatching for decoupling UI from backend.
    Subscribers are called synchronously on the emitting thread.
    For UI updates from background threads, combine with a
    toolkit-specific dispatcher (Tk.after, QTimer, etc.).
    """

    def __init__(self):
        self._subscribers = defaultdict(list)
        self._lock = threading.Lock()

    def on(self, event_name, callback):
        """Subscribe to an event.

        Args:
            event_name: String identifier for the event.
            callback: Callable to invoke when event fires.
                      Receives (*args, **kwargs) passed to emit().
        """
        with self._lock:
            if callback not in self._subscribers[event_name]:
                self._subscribers[event_name].append(callback)

    def off(self, event_name, callback):
        """Unsubscribe from an event.

        Args:
            event_name: String identifier for the event.
            callback: The previously registered callable.
        """
        with self._lock:
            try:
                self._subscribers[event_name].remove(callback)
            except ValueError:
                pass

    def emit(self, event_name, *args, **kwargs):
        """Emit an event, calling all subscribers.

        Args:
            event_name: String identifier for the event.
            *args, **kwargs: Passed to each subscriber callback.
        """
        with self._lock:
            callbacks = list(self._subscribers[event_name])
        for callback in callbacks:
            callback(*args, **kwargs)

    def clear(self, event_name=None):
        """Remove all subscribers, optionally for a specific event."""
        with self._lock:
            if event_name is None:
                self._subscribers.clear()
            else:
                self._subscribers.pop(event_name, None)


# Singleton instance shared across the application
bus = EventBus()
