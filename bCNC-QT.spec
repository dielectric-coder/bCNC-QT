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
excludes = ["tkinter", "_tkinter"]

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

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="bCNC-QT",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # keep console for terminal output
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="bCNC-QT",
)
