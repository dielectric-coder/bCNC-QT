# Qt signal definitions for bCNC
#
# Centralized signal hub replacing Tkinter virtual events.
# All inter-component communication goes through these signals.

from PySide6.QtCore import QObject, Signal


class AppSignals(QObject):
    """Central signal hub for the application.

    Replaces Tkinter's event_generate/bind system.
    All signals are emitted on the main thread via QTimer-based
    polling of the Sender's queues.
    """

    # Connection
    connect_requested = Signal()           # <<Connect>>
    connection_changed = Signal(bool)      # connected: True/False

    # File operations
    new_file = Signal()                    # <<New>>
    open_file = Signal()                   # <<Open>>
    save_file = Signal()                   # <<Save>>
    save_as_file = Signal()                # <<SaveAs>>
    import_file = Signal()                 # <<Import>>
    reload_file = Signal()                 # <<Reload>>
    file_loaded = Signal(str)              # filename

    # Execution
    run_requested = Signal()               # <<Run>>
    stop_requested = Signal()              # <<Stop>>
    pause_requested = Signal()             # <<Pause>>
    resume_requested = Signal()            # <<Resume>>
    feed_hold = Signal()                   # <<FeedHold>>

    # Machine state updates (emitted from serial monitor)
    state_changed = Signal(str, str)       # state, color
    position_updated = Signal(              # work + machine pos
        float, float, float,               # wx, wy, wz
        float, float, float,               # mx, my, mz
    )
    g_state_updated = Signal()             # $G response parsed
    probe_updated = Signal()               # probe data received
    generic_update = Signal(str)            # %update <name> dispatch

    # Serial messages (from log queue)
    serial_buffer = Signal(str)            # MSG_BUFFER
    serial_send = Signal(str)              # MSG_SEND
    serial_receive = Signal(str)           # MSG_RECEIVE
    serial_ok = Signal(str)                # MSG_OK
    serial_error = Signal(str)             # MSG_ERROR
    serial_run_end = Signal(str)           # MSG_RUNEND
    serial_clear = Signal()                # MSG_CLEAR

    # Run progress
    run_progress = Signal(int, int)        # completed_lines, total_lines
    buffer_fill = Signal(float)            # percentage 0-100

    # Canvas
    draw_requested = Signal()              # <<Draw>>
    draw_probe = Signal()                  # <<DrawProbe>>
    draw_orient = Signal()                 # <<DrawOrient>>
    orient_add_marker_mode = Signal()      # request canvas enter add-marker mode
    orient_marker_added = Signal(float, float, float, float)  # (xm, ym, x, y)
    orient_marker_selected = Signal(int)   # marker index clicked on canvas
    view_changed = Signal(int)             # view index
    canvas_block_clicked = Signal(int, bool)  # (block_id, ctrl_held)

    # Selection
    selection_changed = Signal()           # <<ListboxSelect>>

    # Editor
    modified = Signal()                    # <<Modified>>

    # Autolevel
    autolevel_scan = Signal()              # <<AutolevelScan>>
    autolevel_scan_margins = Signal()      # <<AutolevelScanMargins>>
    autolevel_apply = Signal()             # <<Autolevel>>
    autolevel_set_zero = Signal()          # <<AutolevelZero>>
    autolevel_clear = Signal()             # <<AutolevelClear>>
    autolevel_get_margins = Signal()       # <<AutolevelMargins>>

    # Status bar
    status_message = Signal(str)           # <<Status>>
    canvas_coords = Signal(float, float, float)  # <<Coords>>

    # UI callbacks from Sender (thread-safe wrappers)
    ui_disable = Signal()                  # disable widgets during run
    ui_enable = Signal()                   # re-enable widgets after run
    ui_show_info = Signal(str, str)        # (title, message) info dialog
