# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Runs the Cura plug-in's own code against stand-in UM/cura modules (NOT a real Cura).

This only proves our logic and our use of numpy are consistent: click -> triangle -> face/cylinder ->
region -> a 'Gyroid region' child node carrying the cutting-mesh settings.  It cannot prove that Cura's
real API behaves the way these stand-ins assume; that needs a real Cura (see README, 'Known limitations')."""
import math, os, sys, types, unittest
import numpy
import helpers as H

PLUGIN_PARENT = os.path.join(H.ROOT, "cura_plugin")


class Sig:
    def emit(self, *a, **k): pass
    def connect(self, f): pass


def install_stubs():
    def mod(name, **attrs):
        m = types.ModuleType(name); m.__dict__.update(attrs); sys.modules[name] = m; return m

    class Vec:
        def __init__(self, x=0, y=0, z=0): self.d = numpy.array([x, y, z], float)
        def getData(self): return self.d

    class Ray:
        def __init__(self, o, d): self.origin, self.direction = Vec(*o), Vec(*d)

    class Camera:
        ray = None
        def getRay(self, x, y): return Camera.ray

    class Node:
        def __init__(self):
            self.name = ""; self.children = []; self.parent = None; self.decos = {}; self.mesh = None; self.pos = None
            self.stack = Stack()
        def setName(self, n): self.name = n
        def getName(self): return self.name
        def setSelectable(self, b): pass
        def setCalculateBoundingBox(self, b): pass
        def setMeshData(self, m): self.mesh = m
        def calculateBoundingBoxMesh(self): pass
        def addDecorator(self, d): pass
        def callDecoration(self, n): return self.stack if n == "getStack" else None
        def getParent(self): return self.parent
        def getChildren(self): return self.children
        def getWorldTransformation(self): return types.SimpleNamespace(getData=lambda: numpy.eye(4))
        def getMeshDataTransformed(self): return self.mesh_world

    class Stack:
        def __init__(self): self.top = Top()
        def getTop(self): return self.top
        def getSettingDefinition(self, key): return key if key not in ("bogus",) else None
        def getProperty(self, k, p): return False

    class Top:
        def __init__(self): self.inst = {}
        def addInstance(self, i): self.inst[i.key] = i.value

    class Inst:
        def __init__(self, definition, container): self.key, self.value = definition, None
        def setProperty(self, p, v): self.value = v
        def resetState(self): pass

    class Op:
        def __init__(self, *a, **k): self.a = a
        def push(self): self.redo()
        def redo(self): pass

    class Add(Op):
        def redo(self): self.a[1].children.append(self.a[0]); self.a[0].parent = self.a[1]
    class SetParent(Op):
        def redo(self):
            n, p = self.a
            if n.parent: n.parent.children.remove(n)
            p.children.append(n); n.parent = p
    class Remove(Op):
        def redo(self): self.a[0].parent.children.remove(self.a[0]); self.a[0].parent = None
    class Translate(Op):
        def __init__(self, n, v, set_position=False): self.n, self.v = n, v
        def redo(self): self.n.pos = self.v.getData()
    class Grouped(Op):
        def __init__(self): self.ops = []
        def addOperation(self, o): self.ops.append(o)
        def redo(self):
            for o in self.ops: o.redo()

    class Builder:
        def setVertices(self, v): self.v = v
        def setIndices(self, i): self.i = i
        def calculateNormals(self): pass
        def build(self): return types.SimpleNamespace(v=self.v, i=self.i)

    class Tool:
        def __init__(self): self._c = Controller()
        def getController(self): return self._c
        def setExposedProperties(self, *a): pass
        def event(self, e): pass
        propertyChanged = Sig()

    class Controller:
        scene = None
        def getToolsEnabled(self): return True
        def getScene(self): return Controller.scene

    class Scene:
        def __init__(self): self.root = Node(); self.picked = None; self.cam = Camera()
        def getRoot(self): return self.root
        def findObject(self, i): return self.picked
        def getActiveCamera(self): return self.cam
        sceneChanged = Sig()

    class App:
        _i = None
        @classmethod
        def getInstance(cls):
            if cls._i is None: cls._i = cls()
            return cls._i
        def getRenderer(self): return types.SimpleNamespace(getRenderPass=lambda n: types.SimpleNamespace(getIdAtPosition=lambda x, y: 1))
        def getMultiBuildPlateModel(self): return types.SimpleNamespace(activeBuildPlate=0)
        def getController(self): return Controller()
        def getPreferences(self): return App.prefs
        def callLater(self, fn): fn()
    class Prefs:
        def __init__(self): self.v = {}
        def addPreference(self, k, d): self.v.setdefault(k, d)
        def getValue(self, k): return self.v.get(k)
        def setValue(self, k, x): self.v[k] = x
    App.prefs = Prefs()
    class Ext:
        def __init__(self): self.menu = []
        def setMenuName(self, n): self.name = n
        def addMenuItem(self, t, cb): self.menu.append((t, cb))
    class Msg:
        shown = []
        def __init__(self, text, **kw): self.text = text
        def show(self): Msg.shown.append(self.text)
    types.Msg = Msg; types.App = App

    class Event_: MousePressEvent = 1
    class MouseEvent_: LeftButton = 1
    class Logger:
        logs = []
        @staticmethod
        def log(lvl, msg): Logger.logs.append((lvl, msg))
        @staticmethod
        def logException(*a): Logger.logs.append(("x", str(a)))

    mod("UM"); mod("cura"); mod("cura.Operations"); mod("cura.Scene"); mod("UM.Operations"); mod("UM.Scene"); mod("UM.Math"); mod("UM.Mesh"); mod("UM.Settings")
    mod("UM.Event", Event=Event_, MouseEvent=MouseEvent_)
    mod("UM.Logger", Logger=Logger); mod("UM.Math.Vector", Vector=Vec); mod("UM.Mesh.MeshBuilder", MeshBuilder=Builder)
    mod("UM.Message", Message=Msg); mod("UM.Extension", Extension=Ext)
    mod("UM.Operations.AddSceneNodeOperation", AddSceneNodeOperation=Add)
    mod("UM.Operations.GroupedOperation", GroupedOperation=Grouped)
    mod("UM.Operations.RemoveSceneNodeOperation", RemoveSceneNodeOperation=Remove)
    mod("UM.Operations.TranslateOperation", TranslateOperation=Translate)
    mod("UM.Scene.Selection", Selection=types.SimpleNamespace(getSelectedObject=lambda i: None))
    mod("UM.Settings.SettingInstance", SettingInstance=Inst)
    mod("UM.Tool", Tool=Tool); mod("UM.Application", Application=App)
    mod("UM.i18n", i18nCatalog=lambda n: types.SimpleNamespace(i18nc=lambda c, t: t))
    mod("cura.CuraApplication", CuraApplication=App)
    mod("cura.Operations.SetParentOperation", SetParentOperation=SetParent)
    mod("cura.Scene.BuildPlateDecorator", BuildPlateDecorator=lambda p: None)
    mod("cura.Scene.CuraSceneNode", CuraSceneNode=Node)
    mod("cura.Scene.SliceableObjectDecorator", SliceableObjectDecorator=lambda: None)
    return Node, Scene, Controller, Ray, Logger


class CuraPluginWithStandIns(unittest.TestCase):
    def test_click_creates_a_cutting_mesh_with_gyroid_settings(self):
        Node, Scene, Controller, Ray, Logger = install_stubs()
        sys.path.insert(0, PLUGIN_PARENT)
        try:
            import GyroidFilter, GyroidFilter.GyroidFilterTool as GT
            self.assertIn("tool", GyroidFilter.getMetaData())
            self.assertTrue(any("self-test PASS" in m for _, m in Logger.logs) is False)   # not yet constructed
            tool = GT.GyroidFilterTool()
            self.assertTrue(any("self-test PASS" in m for _, m in Logger.logs), Logger.logs)
            scene = Scene(); Controller.scene = scene
            m = H.cartridge_mesh()
            model = Node(); model.name = "cartridge"
            verts = numpy.array([v for t in m.tris for v in (m.verts[t[0]], m.verts[t[1]], m.verts[t[2]])], float)
            model.mesh_world = types.SimpleNamespace(getVertices=lambda: verts, getIndices=lambda: None)
            scene.root.children.append(model); model.parent = scene.root
            scene.picked = model
            Camera = scene.cam
            type(Camera).ray = Ray((120, 0, 30), (-1, 0, 0))            # straight at the outer wall
            ev = types.SimpleNamespace(type=1, buttons=[1], x=0.0, y=0.0)
            tool.event(ev)
            kids = [c for c in model.children if c.name == "Gyroid region"]
            self.assertEqual(len(kids), 1, tool.getStatus())
            s = kids[0].stack.top.inst
            self.assertEqual((s["cutting_mesh"], s["infill_pattern"], s["wall_line_count"], s["top_layers"], s["bottom_layers"]),
                             (True, "gyroid", 0, 0, 0))
            self.assertEqual(s["infill_sparse_density"], 25.0)
            self.assertIn("outer cylinder", tool.getStatus())
            # re-apply with other settings replaces the region instead of adding a second one
            tool.setDensityPct(40); tool.setMarginMm(0); tool.reapply()
            kids = [c for c in model.children if c.name == "Gyroid region"]
            self.assertEqual(len(kids), 1); self.assertEqual(kids[0].stack.top.inst["infill_sparse_density"], 40.0)
            # the region sits on the wall: node position = centre of the region, mesh centred on its own origin
            self.assertAlmostEqual(float(numpy.abs(kids[0].mesh.v.mean(axis=0)).max()), 0.0, delta=0.6)
            # a click that misses the model says so
            type(Camera).ray = Ray((120, 0, 300), (-1, 0, 0))
            tool.event(ev); self.assertIn("did not hit", tool.getStatus())
        finally:
            sys.path.remove(PLUGIN_PARENT)

    def test_extensions_menu_entry_and_one_time_message(self):
        install_stubs()
        for k in [k for k in sys.modules if k == "GyroidFilter" or k.startswith("GyroidFilter.")]:
            del sys.modules[k]                                    # re-import against this test's stand-ins
        sys.path.insert(0, PLUGIN_PARENT)
        try:
            import GyroidFilter
            reg = GyroidFilter.register(None)
            self.assertIn("extension", reg)                       # Cura hides the toolbar until a model is loaded
            ext = reg["extension"]
            self.assertEqual(ext.menu[0][0], "Where is the tool?")
            self.assertEqual(len(types.Msg.shown), 1)             # shown once at first start ...
            GyroidFilter.register(None)
            self.assertEqual(len(types.Msg.shown), 1)             # ... and not again
            ext.menu[0][1]()
            self.assertEqual(len(types.Msg.shown), 2)             # the menu entry shows it on demand
        finally:
            sys.path.remove(PLUGIN_PARENT)

    def test_plugin_ships_no_svg_icons(self):
        # Cura inserts its own fill attribute into tool-icon SVGs; an SVG that already has one crashed Cura at start-up
        found = [f for d, _, fs in os.walk(PLUGIN_PARENT) for f in fs if f.lower().endswith(".svg")]
        self.assertEqual(found, [])
        self.assertNotIn(".svg", open(os.path.join(PLUGIN_PARENT, "GyroidFilter", "__init__.py")).read())

    def test_ray_picking_helpers(self):
        sys.path.insert(0, PLUGIN_PARENT)
        try:
            from GyroidFilter import picking
            tri = numpy.array([[[0, 0, 0], [1, 0, 0], [0, 1, 0]], [[0, 0, 1], [1, 0, 1], [0, 1, 1]]], float)
            self.assertEqual(picking.ray_first_triangle(tri, (0.2, 0.2, 5), (0, 0, -1)), 1)
            self.assertIsNone(picking.ray_first_triangle(tri, (3, 3, 5), (0, 0, -1)))
        finally:
            sys.path.remove(PLUGIN_PARENT)


if __name__ == "__main__":
    unittest.main()
