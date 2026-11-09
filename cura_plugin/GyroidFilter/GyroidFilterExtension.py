# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
# Tested by the author in a real Cura on Linux Mint (works well). Windows and Mac not tested yet.
"""Cura hides its left toolbar until a model is loaded, so an empty Cura shows no trace of the plug-in.
This adds an Extensions menu entry and tells the user once where the tool is."""
from UM.Application import Application
from UM.Extension import Extension
from UM.Logger import Logger
from UM.Message import Message

HELP = "Load a model, click it, then pick the Gyroid Filter tool in the left toolbar. Click a flat face or a cylinder on the model."
PREF = "gyroid_filter/intro_shown"


class GyroidFilterExtension(Extension):
    def __init__(self):
        super().__init__()
        self.setMenuName("Gyroid Filter")
        self.addMenuItem("Where is the tool?", self._show_help)
        try:
            prefs = Application.getInstance().getPreferences()
            prefs.addPreference(PREF, False)
            if not prefs.getValue(PREF):
                prefs.setValue(PREF, True)
                Application.getInstance().callLater(self._show_help)
        except Exception as e:      # a missing message must never stop Cura starting
            Logger.log("w", "GyroidFilter: intro message skipped: %r" % (e,))

    def _show_help(self):
        Message(HELP, title="Gyroid Filter installed", lifetime=20).show()
