# Tkinter-free utilities extracted from Utils.py
#
# This module contains configuration helpers, metadata, paths, and other
# utility functions that do NOT depend on tkinter.  Qt code imports this
# directly (``import utils_core as Utils``) so it can run without tkinter
# installed.  The original Utils.py re-exports everything here via
# ``from utils_core import *`` and adds tkinter-specific code on top.
#
# Author: Vasilis Vlachoudis
#  Email: Vasilis.Vlachoudis@cern.ch
#   Date: 16-Apr-2015

__all__ = [
    # Metadata
    "__author__", "__email__", "__version__", "__date__", "__prg__",
    "__platform_fingerprint__", "__title__", "__www__", "__contribute__",
    "__credits__", "__translations__",
    # Paths
    "prgpath", "iniSystem", "iniUser", "hisFile",
    # Translation
    "_", "N_",
    # Constants / globals
    "LANGUAGES", "icons", "images", "config", "language",
    "_errorReport", "errors", "_maxRecent", "_FONT_SECTION",
    # Classes
    "Config",
    # Functions
    "delIcons", "loadConfiguration", "saveConfiguration",
    "cleanConfiguration", "addSection",
    "getStr", "getUtf", "getInt", "getFloat", "getBool",
    "setBool", "setStr", "setUtf", "setInt", "setFloat",
    "addRecent", "getRecent", "comports",
    # Re-exported stdlib
    "glob", "os", "sys", "traceback", "configparser",
    # Re-exported third-party
    "serial", "say",
]

import gettext
import glob
import os
import sys
import traceback
import configparser

from lib.log import say

try:
    import serial
except Exception:
    serial = None

__author__ = "Vasilis Vlachoudis"
__email__ = "vvlachoudis@gmail.com"
__version__ = "0.10.0"
__date__ = "24 June 2022"
__prg__ = "bCNC"


__platform_fingerprint__ = "({} py{}.{}.{})".format(
    sys.platform,
    sys.version_info.major,
    sys.version_info.minor,
    sys.version_info.micro,
)
__title__ = f"{__prg__} {__version__} {__platform_fingerprint__}"

__prg__ = "bCNC"
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    # PyInstaller bundle: data files are extracted to sys._MEIPASS
    prgpath = sys._MEIPASS
else:
    prgpath = os.path.abspath(os.path.dirname(__file__))
iniSystem = os.path.join(prgpath, f"{__prg__}.ini")
iniUser = os.path.expanduser(f"~/.{__prg__}")
hisFile = os.path.expanduser(f"~/.{__prg__}.history")


_ = gettext.translation(
    "bCNC", os.path.join(prgpath, "locales"), fallback=True
).gettext


def N_(message):
    return message


__www__ = "https://github.com/vlachoudis/bCNC"
__contribute__ = (
    "@effer Filippo Rivato\n"
    "@carlosgs Carlos Garcia Saura\n"
    "@dguerizec\n"
    "@buschhardt\n"
    "@MARIOBASZ\n"
    "@harvie Tomas Mudrunka"
)
__credits__ = (
    "@1bigpig\n"
    "@chamnit Sonny Jeon\n"
    "@harvie Tomas Mudrunka\n"
    "@onekk Carlo\n"
    "@SteveMoto\n"
    "@willadams William Adams"
)
__translations__ = (
    "Dutch - @hypothermic\n"
    "French - @ThierryM\n"
    "German - @feistus, @SteveMoto\n"
    "Italian - @onekk\n"
    "Japanese - @stm32f1\n"
    "Korean - @jjayd\n"
    "Portuguese - @moacirbmn \n"
    "Russian - @minithc\n"
    "Simplified Chinese - @Bluermen\n"
    "Spanish - @carlosgs\n"
    "Traditional Chinese - @Engineer2Designer"
)

LANGUAGES = {
    "": "<system>",
    "de": "Deutsch",
    "en": "English",
    "es": "Espa\u00f1ol",
    "fr": "Fran\u00e7ais",
    "it": "Italiano",
    "ja": "Japanese",
    "kr": "Korean",
    "nl": "Nederlands",
    "pt_BR": "Brazilian - Portuguese",
    "ru": "Russian",
    "zh_cn": "Simplified Chinese",
    "zh_tw": "Traditional Chinese",
}

icons = {}
images = {}
config = configparser.ConfigParser(interpolation=None)
language = ""

_errorReport = True
errors = []
_maxRecent = 10

_FONT_SECTION = "Font"


# New class to provide config for everyone
# FIXME: create single instance of this and pass it to all parts of application
class Config:
    def greet(self, who=__prg__):
        print(f"Config class loaded in {who}")


# -----------------------------------------------------------------------------
def delIcons():
    global icons
    if len(icons) > 0:
        for i in icons.values():
            del i
        icons = {}  # needed otherwise it complains on deleting the icons

    global images
    if len(images) > 0:
        for i in images.values():
            del i
        images = {}  # needed otherwise it complains on deleting the icons


# -----------------------------------------------------------------------------
# Load configuration
# -----------------------------------------------------------------------------
def loadConfiguration(systemOnly=False):
    global config, _errorReport, language
    if systemOnly:
        config.read(iniSystem)
    else:
        config.read([iniSystem, iniUser])
        _errorReport = getInt("Connection", "errorreport", 1)

        language = getStr(__prg__, "language")
        if language and language != "en":
            # replace language
            lang = gettext.translation(
                __prg__,
                os.path.join(prgpath, "locales"),
                languages=[language]
            )
            lang.install()


# -----------------------------------------------------------------------------
# Save configuration file
# -----------------------------------------------------------------------------
def saveConfiguration():
    global config
    cleanConfiguration()
    with open(iniUser, "w") as f:
        config.write(f)
    delIcons()


# ----------------------------------------------------------------------
# Remove items that are the same as in the default ini
# ----------------------------------------------------------------------
def cleanConfiguration():
    global config
    newconfig = config  # Remember config
    config = configparser.ConfigParser()

    loadConfiguration(True)

    # Compare items
    for section in config.sections():
        for item, value in config.items(section):
            try:
                new = newconfig.get(section, item)
                if value == new:
                    newconfig.remove_option(section, item)
            except configparser.NoOptionError:
                pass
    config = newconfig


# -----------------------------------------------------------------------------
# add section if it doesn't exist
# -----------------------------------------------------------------------------
def addSection(section):
    global config
    if not config.has_section(section):
        config.add_section(section)


# -----------------------------------------------------------------------------
def getStr(section, name, default=""):
    global config
    try:
        return config.get(section, name)
    except Exception:
        return default


# -----------------------------------------------------------------------------
def getUtf(section, name, default=""):
    global config
    try:
        return config.get(section, name)
    except Exception:
        return default


# -----------------------------------------------------------------------------
def getInt(section, name, default=0):
    global config
    try:
        return int(config.get(section, name))
    except Exception:
        return default


# -----------------------------------------------------------------------------
def getFloat(section, name, default=0.0):
    global config
    try:
        return float(config.get(section, name))
    except Exception:
        return default


# -----------------------------------------------------------------------------
def getBool(section, name, default=False):
    global config
    try:
        return bool(int(config.get(section, name)))
    except Exception:
        return default


# -----------------------------------------------------------------------------
def setBool(section, name, value):
    global config
    config.set(section, name, str(int(value)))


# -----------------------------------------------------------------------------
def setStr(section, name, value):
    global config
    config.set(section, name, str(value))


# -----------------------------------------------------------------------------
def setUtf(section, name, value):
    global config
    try:
        s = str(value)
    except Exception:
        s = value
    config.set(section, name, s)


setInt = setStr
setFloat = setStr


# -----------------------------------------------------------------------------
# Add Recent
# -----------------------------------------------------------------------------
def addRecent(filename):
    try:
        sfn = str(os.path.abspath(filename))
    except UnicodeEncodeError:
        sfn = filename

    last = _maxRecent - 1
    for i in range(_maxRecent):
        rfn = getRecent(i)
        if rfn is None:
            last = i - 1
            break
        if rfn == sfn:
            if i == 0:
                return
            last = i - 1
            break

    # Shift everything by one
    for i in range(last, -1, -1):
        config.set("File", f"recent.{i + 1}", getRecent(i))
    config.set("File", "recent.0", sfn)


# -----------------------------------------------------------------------------
def getRecent(recent):
    try:
        return config.get("File", f"recent.{int(recent)}")
    except configparser.NoOptionError:
        return None


# -----------------------------------------------------------------------------
# Return all comports when serial.tools.list_ports is not available!
# -----------------------------------------------------------------------------
def comports(include_links=True):
    locations = ["/dev/ttyACM", "/dev/ttyUSB", "/dev/ttyS", "com"]

    comports = []
    for prefix in locations:
        for i in range(32):
            device = f"{prefix}{i}"
            try:
                os.stat(device)
                comports.append((device, None, None))
            except OSError:
                pass

            # Detects windows XP serial ports
            try:
                s = serial.Serial(device)
                s.close()
                comports.append((device, None, None))
            except Exception:
                pass
    return comports
