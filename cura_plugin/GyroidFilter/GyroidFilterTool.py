# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
# Tested by the author in a real Cura on Linux Mint (works well). Windows and Mac not tested yet.
import numpy

from UM.Event import Event, MouseEvent
from UM.Logger import Logger
from UM.Math.Vector import Vector
from UM.Mesh.MeshBuilder import MeshBuilder
from UM.Message import Message
from UM.Operations.AddSceneNodeOperation import AddSceneNodeOperation
from UM.Operations.GroupedOperation import GroupedOperation
from UM.Operations.RemoveSceneNodeOperation import RemoveSceneNodeOperation
from UM.Operations.TranslateOperation import TranslateOperation
from UM.Scene.Selection import Selection
from UM.Settings.SettingInstance import SettingInstance
from UM.Tool import Tool
from UM.Application import Application

from cura.CuraApplication import CuraApplication
from cura.Operations.SetParentOperation import SetParentOperation
from cura.Scene.BuildPlateDecorator import BuildPlateDecorator
from cura.Scene.CuraSceneNode import CuraSceneNode
from cura.Scene.SliceableObjectDecorator import SliceableObjectDecorator

from . import gyroid_core as core
from .picking import build_mesh, ray_first_triangle, selftest

REGION_NAME = "Gyroid region"
HELPER_SETTINGS = ("support_mesh", "infill_mesh", "cutting_mesh", "anti_overhang_mesh")


class GyroidFilterTool(Tool):
    def __init__(self):
        super().__init__()
        self._controller = self.getController()
        self._selection_pass = None
        self._mode = "auto"
        self._depth_mode = "through"
        self._depth_mm = 3.0
        self._density = 25.0
        self._margin = 3.0
        self._status = "Select a model, then click a flat face or a cylinder on it."
        self._cache = {}          # id(node) -> (key, mesh, topo, tri_points)
        self._last = None         # (node, triangle index) of the last pick
        self._last_region = None  # node created by the last pick
        self.setExposedProperties("Mode", "DepthMode", "DepthMm", "DensityPct", "MarginMm", "Status")
        try:
            Logger.log("i", "GyroidFilter: core self-test %s" % selftest(core))
        except Exception as e:  # never stop Cura from starting
            Logger.log("e", "GyroidFilter: core self-test crashed: %r" % (e,))

    # ---- exposed properties (QML) ----
    def getMode(self): return self._mode
    def setMode(self, v): self._mode = str(v); self.propertyChanged.emit()
    def getDepthMode(self): return self._depth_mode
    def setDepthMode(self, v): self._depth_mode = str(v); self.propertyChanged.emit()
    def getDepthMm(self): return self._depth_mm
    def setDepthMm(self, v): self._depth_mm = max(0.2, float(v)); self.propertyChanged.emit()
    def getDensityPct(self): return self._density
    def setDensityPct(self, v): self._density = core.settings.clamp_density(v); self.propertyChanged.emit()
    def getMarginMm(self): return self._margin
    def setMarginMm(self, v): self._margin = max(0.0, float(v)); self.propertyChanged.emit()
    def getStatus(self): return self._status

    def _say(self, text, warn=False):
        self._status = text
        self.propertyChanged.emit()
        Logger.log("w" if warn else "i", "GyroidFilter: " + text)

    # ---- events ----
    def event(self, event):
        super().event(event)
        if (event.type == Event.MousePressEvent and MouseEvent.LeftButton in event.buttons
                and self._controller.getToolsEnabled()):
            if self._selection_pass is None:
                self._selection_pass = Application.getInstance().getRenderer().getRenderPass("selection")
            scene = self._controller.getScene()
            node = scene.findObject(self._selection_pass.getIdAtPosition(event.x, event.y))
            if not node or node.getName() == REGION_NAME:
                return
            stack = node.callDecoration("getStack")
            if stack and any(stack.getProperty(k, "value") for k in HELPER_SETTINGS):
                return
            ray = scene.getActiveCamera().getRay(event.x, event.y)
            try:
                self._apply(node, ray.origin.getData(), ray.direction.getData())
            except Exception as e:
                Logger.logException("e", "GyroidFilter failed")
                self._say("Something went wrong: %s" % e, warn=True)

    # ---- actions (QML buttons) ----
    def reapply(self):
        if not self._last:
            self._say("Nothing to re-apply yet: click a face first.", warn=True)
            return
        node, tri = self._last
        if self._last_region is not None:
            RemoveSceneNodeOperation(self._last_region).push()
            self._last_region = None
        self._apply(node, None, None, tri=tri)

    def removeRegions(self):
        node = Selection.getSelectedObject(0)
        if node is None:
            self._say("Select a model first.", warn=True)
            return
        if node.getName() == REGION_NAME and node.getParent() is not None:
            node = node.getParent()
        n = 0
        for child in list(node.getChildren()):
            if child.getName() == REGION_NAME:
                RemoveSceneNodeOperation(child).push()
                n += 1
        self._last_region = None
        self._say("Removed %d gyroid region(s)." % n)

    # ---- the work ----
    def _mesh_for(self, node):
        md = node.getMeshDataTransformed()
        key = (id(md), tuple(numpy.round(node.getWorldTransformation().getData().ravel(), 4)))
        hit = self._cache.get(id(node))
        if hit and hit[0] == key:
            return hit[1], hit[2], hit[3]
        mesh, tri_points = build_mesh(md.getVertices(), md.getIndices(), core)
        topo = core.regions.Topology(mesh)
        self._cache = {id(node): (key, mesh, topo, tri_points)}
        return mesh, topo, tri_points

    def _apply(self, node, origin, direction, tri=None):
        mesh, topo, tri_points = self._mesh_for(node)
        if tri is None:
            tri = ray_first_triangle(tri_points, origin, direction)
            if tri is None:
                self._say("The click did not hit the model surface.", warn=True)
                return
        R = core.regions
        sel = R.pick(mesh, topo, tri, self._mode)
        if self._depth_mode == "through":
            th = R.wall_thickness(mesh, sel)
            depth = (th if th else self._depth_mm) + R.OVERSHOOT_MM
        else:
            depth = self._depth_mm
        try:
            if sel["kind"] == "plane":
                window = {"shape": "rect", "margin_mm": self._margin} if self._margin > 0 else None
                region, _ = R.plane_region(mesh, sel, depth, window)
                what = "flat face (%d triangles)" % len(sel["tris"])
            else:
                region, _ = R.cylinder_region(sel, depth, margin_mm=self._margin)
                what = "%s cylinder, radius %.2f mm" % ("hole" if sel["concave"] else "outer", sel["radius"])
        except ValueError as e:
            self._say("Not applied: %s" % e, warn=True)
            return
        self._last = (node, tri)
        self._last_region = self._add_region(node, region)
        self._say("Open-cell gyroid on %s, %.1f mm deep. Slice to see it (Print Settings > Mesh Fixes shows nothing; look at layer view)." % (what, depth))

    def _add_region(self, parent, region):
        v = numpy.asarray(region.verts, dtype=numpy.float64)
        centre = (v.min(axis=0) + v.max(axis=0)) / 2.0
        builder = MeshBuilder()
        builder.setVertices(numpy.asarray(v - centre, dtype=numpy.float32))
        builder.setIndices(numpy.asarray(region.tris, dtype=numpy.int32))
        builder.calculateNormals()

        node = CuraSceneNode()
        node.setName(REGION_NAME)
        node.setSelectable(True)
        node.setCalculateBoundingBox(True)
        node.setMeshData(builder.build())
        node.calculateBoundingBoxMesh()
        active_build_plate = CuraApplication.getInstance().getMultiBuildPlateModel().activeBuildPlate
        node.addDecorator(BuildPlateDecorator(active_build_plate))
        node.addDecorator(SliceableObjectDecorator())

        stack = node.callDecoration("getStack")
        top = stack.getTop()
        for key, value in core.settings.cura_settings(self._density).items():
            if value is None:
                continue
            definition = stack.getSettingDefinition(key)
            if definition is None:
                Logger.log("w", "GyroidFilter: setting %s unknown in this Cura" % key)
                continue
            inst = SettingInstance(definition, top)
            inst.setProperty("value", value)
            inst.resetState()
            top.addInstance(inst)

        op = GroupedOperation()
        op.addOperation(AddSceneNodeOperation(node, self._controller.getScene().getRoot()))
        op.addOperation(SetParentOperation(node, parent))
        op.addOperation(TranslateOperation(node, Vector(*[float(c) for c in centre]), set_position=True))
        op.push()
        CuraApplication.getInstance().getController().getScene().sceneChanged.emit(node)
        return node
