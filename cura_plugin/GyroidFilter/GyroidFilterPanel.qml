// Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
// Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
import QtQuick 2.15
import QtQuick.Controls 2.15

import UM 1.7 as UM

Item
{
    id: base
    width: UM.Theme.getSize("setting_control").width * 2.4
    height: col.height + UM.Theme.getSize("default_margin").height * 2

    function prop(name, fallback) {
        var v = UM.ActiveTool.properties.getValue(name)
        return (v === undefined || v === null) ? fallback : v
    }
    function set(name, value) { UM.Controller.setProperty(name, value) }

    Column
    {
        id: col
        spacing: UM.Theme.getSize("default_lining").height
        anchors.margins: UM.Theme.getSize("default_margin").width
        width: parent.width - 2 * UM.Theme.getSize("default_margin").width
        x: UM.Theme.getSize("default_margin").width
        y: UM.Theme.getSize("default_margin").height

        Label { text: "Click a face or cylinder on the model"; font: UM.Theme.getFont("default_bold"); color: UM.Theme.getColor("text") }

        Label { text: "What to pick"; color: UM.Theme.getColor("text") }
        ComboBox
        {
            width: parent.width
            model: ["Automatic", "Flat face only", "Cylinder only"]
            currentIndex: ["auto", "plane", "cylinder"].indexOf(prop("Mode", "auto"))
            onActivated: set("Mode", ["auto", "plane", "cylinder"][index])
        }

        CheckBox
        {
            text: "Open all the way through the wall"
            checked: prop("DepthMode", "through") === "through"
            onClicked: set("DepthMode", checked ? "through" : "fixed")
        }
        Row
        {
            spacing: UM.Theme.getSize("default_margin").width
            visible: prop("DepthMode", "through") !== "through"
            Label { text: "Depth (mm)"; color: UM.Theme.getColor("text"); anchors.verticalCenter: parent.verticalCenter }
            TextField
            {
                width: UM.Theme.getSize("setting_control").width
                text: String(prop("DepthMm", 3))
                validator: DoubleValidator { bottom: 0.2; top: 100; decimals: 2; notation: DoubleValidator.StandardNotation }
                onEditingFinished: set("DepthMm", text.replace(",", "."))
            }
        }

        Row
        {
            spacing: UM.Theme.getSize("default_margin").width
            Label { text: "Gyroid density (%)"; color: UM.Theme.getColor("text"); anchors.verticalCenter: parent.verticalCenter }
            TextField
            {
                width: UM.Theme.getSize("setting_control").width
                text: String(prop("DensityPct", 25))
                validator: DoubleValidator { bottom: 5; top: 60; decimals: 1; notation: DoubleValidator.StandardNotation }
                onEditingFinished: set("DensityPct", text.replace(",", "."))
            }
        }
        Row
        {
            spacing: UM.Theme.getSize("default_margin").width
            Label { text: "Solid rim (mm)"; color: UM.Theme.getColor("text"); anchors.verticalCenter: parent.verticalCenter }
            TextField
            {
                width: UM.Theme.getSize("setting_control").width
                text: String(prop("MarginMm", 3))
                validator: DoubleValidator { bottom: 0; top: 50; decimals: 2; notation: DoubleValidator.StandardNotation }
                onEditingFinished: set("MarginMm", text.replace(",", "."))
            }
        }

        Button { text: "Re-apply to last pick"; onClicked: UM.ActiveTool.triggerAction("reapply") }
        Button { text: "Remove gyroid regions from selected model"; onClicked: UM.ActiveTool.triggerAction("removeRegions") }

        Label
        {
            width: parent.width
            wrapMode: Text.WordWrap
            text: prop("Status", "")
            color: UM.Theme.getColor("text")
        }
    }
}
