# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for bCNC-QT
#
# Build:  pyinstaller bCNC-QT.spec
# Output: dist/bCNC-QT  (single directory)

import os
import glob as _glob

block_cipher = None

# --- Paths for bare-name imports ---
pathex = [
    os.path.abspath("bCNC"),
    os.path.abspath("bCNC/lib"),
    os.path.abspath("bCNC/controllers"),
    os.path.abspath("bCNC/plugins"),
]

# --- Hidden imports ---
# Controllers (loaded dynamically by Sender)
controllers = [
    "GRBL0", "GRBL1", "SMOOTHIE", "G2Core",
    "_GenericController", "_GenericGRBL",
]

# Plugins (loaded dynamically by tools_manager)
plugins = [
    "arcfit", "bowl", "box", "center", "closepath", "difference",
    "dragknife", "driller", "drillmark", "endmilloffset", "flatpath",
    "flatten", "function_plot", "halftone", "heightmap", "Helical_Descent",
    "hilbert", "intersection", "involuteGear", "jigsaw", "LaserCut",
    "linearize", "midi2cnc", "pyrograph", "Random", "scaling",
    "simpleArc", "simpleDrill", "simpleLine", "simpleRectangle",
    "simpleRotate", "simpleTranslate", "sketch", "slicemesh", "spiral",
    "spirograph", "stlSlicer", "text", "tile", "trochoidal_3D",
    "trochoidal", "trochoidPath", "zigzag",
]

# Bare-name modules from bCNC/ and bCNC/lib/
bare_modules = [
    "CNC", "Sender", "Helpers", "utils_core", "tools_base", "ToolsPage",
    "Camera", "CommandDispatcher", "EventBus", "FileManager",
    "MachineState", "PathGeometry", "Pendant", "SceneGraph",
    "ViewTransform",
    # lib/
    "bmath", "bpath", "bstl", "dxf", "imageToGcode", "involute",
    "log", "meshcut", "midiparser", "ply", "rexx", "spline",
    "svgcode", "ttf", "undo", "Unicode", "utils",
]

hiddenimports = controllers + plugins + bare_modules + [
    "serial.tools.list_ports",
    "numpy",
    "PIL",
    "svgelements",
    "shxparser",
]

# --- Data files ---
datas = [
    ("bCNC/bCNC.ini", "."),
    ("bCNC/icons", "icons"),
    ("bCNC/images", "images"),
    ("bCNC/locales", "locales"),
    ("bCNC/pendant", "pendant"),
    ("bCNC/controllers", "controllers"),
    ("bCNC/plugins", "plugins"),
]

# --- Excludes ---
# Only QtCore, QtGui, QtWidgets are used — exclude everything else
excludes = [
    "tkinter", "_tkinter",
    # Unused PySide6 modules (saves ~30-50 MB)
    "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngine", "PySide6.QtWebChannel",
    "PySide6.QtWebSockets",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic", "PySide6.Qt3DExtras", "PySide6.Qt3DAnimation",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.QtBluetooth", "PySide6.QtNfc",
    "PySide6.QtPositioning", "PySide6.QtLocation",
    "PySide6.QtSensors", "PySide6.QtSerialPort", "PySide6.QtSerialBus",
    "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtStateMachine",
    "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtQuickControls2",
    "PySide6.QtQml",
    "PySide6.QtSvg", "PySide6.QtSvgWidgets",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets",
    "PySide6.QtDBus", "PySide6.QtDesigner",
    "PySide6.QtHelp", "PySide6.QtTest", "PySide6.QtXml",
    "PySide6.QtNetwork",
    "PySide6.QtNetworkAuth",
    "PySide6.QtConcurrent",
    "PySide6.QtSpatialAudio",
    "PySide6.QtTextToSpeech",
    "PySide6.QtHttpServer",
]

# --- Analysis ---
a = Analysis(
    ["bCNC/qt/app.py"],
    pathex=pathex,
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Filter out unwanted Qt shared libraries that hooks pull in anyway
_qt_keep = {"QtCore", "QtGui", "QtWidgets", "QtDBus"}  # QtDBus needed on Linux
_qt_remove_prefixes = (
    "libQt6WebEngine", "libQt6Quick", "libQt6Qml", "libQt6Multimedia",
    "libQt63D", "libQt6Charts", "libQt6DataVis", "libQt6Pdf",
    "libQt6Svg", "libQt6Sensors", "libQt6Serial", "libQt6Bluetooth",
    "libQt6Nfc", "libQt6Location", "libQt6Positioning",
    "libQt6OpenGL", "libQt6Network", "libQt6Help", "libQt6Designer",
    "libQt6Test", "libQt6Concurrent", "libQt6RemoteObjects",
    "libQt6Scxml", "libQt6StateMachine", "libQt6Spatial",
    "libQt6TextToSpeech", "libQt6HttpServer",
    "Qt6WebEngine", "Qt6Quick", "Qt6Qml", "Qt6Multimedia",
    "Qt63D", "Qt6Charts", "Qt6DataVis", "Qt6Pdf",
    "Qt6Svg", "Qt6Sensors", "Qt6Serial", "Qt6Bluetooth",
    "Qt6Nfc", "Qt6Location", "Qt6Positioning",
    "Qt6OpenGL", "Qt6Network", "Qt6Help", "Qt6Designer",
    "Qt6Test", "Qt6Concurrent", "Qt6RemoteObjects",
    "Qt6Scxml", "Qt6StateMachine", "Qt6Spatial",
    "Qt6TextToSpeech", "Qt6HttpServer",
)
a.binaries = [
    b for b in a.binaries
    if not any(os.path.basename(b[0]).startswith(p) for p in _qt_remove_prefixes)
]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="bCNC-QT",
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    console=True,  # keep console for terminal output
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,
    upx=True,
    upx_exclude=[],
    name="bCNC-QT",
)
