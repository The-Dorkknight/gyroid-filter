# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
# Tested by the author in a real Cura on Linux Mint (works well). Windows and Mac not tested yet.
from . import GyroidFilterTool
from . import GyroidFilterExtension

from UM.i18n import i18nCatalog
i18n_catalog = i18nCatalog("cura")


def getMetaData():
    return {
        "tool": {
            "name": i18n_catalog.i18nc("@label", "Gyroid Filter"),
            "description": i18n_catalog.i18nc("@info:tooltip", "Make a clicked face or cylinder open-cell gyroid (fillable carbon filter)"),
            "icon": "MeshType",
            "tool_panel": "GyroidFilterPanel.qml",
            "weight": 5,
        },
    }


def register(app):
    return {"tool": GyroidFilterTool.GyroidFilterTool(), "extension": GyroidFilterExtension.GyroidFilterExtension()}
