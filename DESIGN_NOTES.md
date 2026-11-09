# Design notes and research

Everything learned while building Gyroid Filter 0.1.0-wip, so nobody (including future me) has to redo it. Facts marked **verified** were checked by running something; **from source** means read in a slicer's source code but not run; **unknown** means exactly that.

## The request

A plug-in for Cura, PrusaSlicer and OrcaSlicer that lets you **select a face or cylinder** and make part or all of it **open-cell gyroid**, for **fillable carbon filters**.

## Findings

### The slicer-native way: a volume with its own settings

All three slicers can print one region of a part with different infill/wall settings, using a second overlapping volume:

| Slicer | Name | Per-volume settings |
|---|---|---|
| PrusaSlicer | modifier | yes: any per-object setting (pattern, density, perimeters, skin…) |
| OrcaSlicer | modifier part | yes, same idea with Orca's setting names |
| Cura | **cutting mesh** (`cutting_mesh`) | yes: the overlap is printed with the cutting mesh's own settings |

Cura's own description of `cutting_mesh` (from `fdmprinter.def.json`): limit the volume of this mesh to within other meshes, to print some areas with different settings. The related `infill_mesh` only replaces *infill* and its description suggests keeping one wall and no skin, so the part's own walls would stay on the surface; that is why the plug-in uses the cutting mesh and not the infill mesh. **From source / description, not run.**

### Why the region must have zero walls and zero skin

If the region kept walls or skin, the surface you picked would stay closed. Inside the region the app sets walls = 0, top/bottom layers = 0, minimum solid thickness = 0 and "small area becomes solid" = 0. **Verified in PrusaSlicer 2.7.2**: sliced G-code shows only `Internal infill` in the wall bands, no `Perimeter`/`External perimeter`/`Solid infill`; the infill segment directions are many-valued even though the test's global pattern was straight lines, so the gyroid override is in effect.

### PrusaSlicer 3MF layout (verified)

One `<object>` holding every volume's triangles back to back; `Metadata/Slic3r_PE_model.config` lists `<volume firstid lastid>` ranges with `volume_type` = `ModelPart` or `ParameterModifier` and one `<metadata type="volume" key=… value=…/>` per setting. The item transform places the object. PrusaSlicer 2.7.2 reads this and slices it.

### OrcaSlicer 3MF layout (from source, **not run**)

Read from `src/libslic3r/Format/bbs_3mf.cpp` (OrcaSlicer main):

- Orca reads **only** `Metadata/model_settings.config` for part settings; the line that would read PrusaSlicer's `Slic3r_PE_model.config` is commented out. So a PrusaSlicer-style 3MF opens in Orca with the modifier merged into the body as solid geometry. The two flavours must differ.
- Volumes are built from **sub-objects** (`_generate_volumes_new`): each part is its own `<object>` with a mesh, and one assembly `<object>` lists them as `<component objectid=…>`. `<part id=… subtype="modifier_part">` in `model_settings.config` points at the sub-object id.
- Subtype strings: `normal_part`, `negative_part`, `modifier_part`, `support_blocker`, `support_enforcer`.
- Every other `<metadata key value>` of a part goes to `config.set_deserialize(key, value)`, i.e. Orca's own setting names (`sparse_infill_pattern` etc.); all names used were checked to exist in Orca's `PrintConfig.cpp`.
- A file without the `Application` = Orca/Bambu tag is treated as "from another vendor"; the model settings file is still read. The exporter deliberately does not claim to be Orca-made.
- **Unknown:** whether Orca 2.3.x really shows the modifier with those settings when this exact file is opened. First thing to test when an Orca is at hand. Fallback shipped: Region STLs + the settings table.

### Cura plug-in (from source, **not run**)

- Pattern copied from Cura's own `SupportEraser` tool: `Tool` subclass, scene node with `SettingOverrideDecorator` (made by `CuraSceneNode`), `SettingInstance` per setting, `GroupedOperation` of `AddSceneNodeOperation` + `SetParentOperation` + `TranslateOperation`.
- Tool panel: `"tool_panel": "GyroidFilterPanel.qml"` in `getMetaData`; QML talks to the tool through `UM.ActiveTool.properties.getValue(name)`, `UM.Controller.setProperty(name, value)` (calls `set<Name>`), and `UM.ActiveTool.triggerAction("method")` (calls the method).
- Picking: the selection render pass tells which model was clicked; `Camera.getRay(x, y)` gives the ray; the plug-in intersects it with that model's world-space triangles (numpy, Möller–Trumbore) to learn the *triangle*, which the render pass alone cannot say.
- Plug-in API: `plugin.json` has `"api": 8` and `supported_sdk_versions`; Uranium accepts a plug-in whose major version equals Cura's and whose minor is not higher.
- The geometry core is copied into the plug-in by `tools/build_cura_plugin.py` (single source of truth in `src/gyroid_filter/`); a test fails if the copy is stale.
- Start-up self-test writes `GyroidFilter: core self-test PASS` to Cura's log. The installer window reads it back, so "installed" is never reported on a guess.

### Gyroid facts used

Gyroid is available as an infill pattern in all three (`gyroid`, `fill_pattern`, `sparse_infill_pattern`). It is open in both directions (no enclosed pockets) which is why it suits flow-through. Pore size depends on density and line width; **not measured here**.

## Decisions, with the rejected alternatives

| Decision | Why | Rejected |
|---|---|---|
| Modifier / cutting-mesh volumes carrying settings | Slicer does the work; works with each slicer's own profile; no G-code surgery; survives slicer updates | **G-code post-processing**: cannot know which extrusions belong to a face; would have to delete walls and invent gyroid |
| Companion app + 3MF for Prusa/Orca | They have no plug-in API that can pick faces | A fake "plug-in" that is really a post-processing script: cannot pick |
| Real plug-in for Cura | Cura has a plug-in API with tools, picking and per-model settings | Same 3MF route for Cura: Cura's 3MF per-model-settings format was not investigated; the plug-in is the better fit anyway |
| Web UI (stdlib server + vendored three.js) | tkinter was a disaster on Bazzite; works the same on Linux/Windows/Mac; real 3D picking | tkinter software renderer: slow on old CPUs; PyQt: heavy |
| Pure-Python core, numpy optional | Runs on a 7th-gen i3 with nothing installed | numpy hard requirement |
| "Through the wall" by default | A filter wall that is open on one side only does not pass air | Fixed depth by default (still available) |
| Region sticks out 0.3 mm beyond the surface | A region that ends exactly on the surface can leave a skin film from rounding | Exactly flush |
| Auto prefers the cylinder if it covers more triangles | Fine STL tessellation (under 1° per facet) makes a cylinder look flat over a few facets | Auto = plane unless the flat patch is tiny (this was the first version and it failed at 3000 segments) |

## Tried and dropped / bugs found on the way

- Known Cura plug-in traps from earlier projects, checked here: (1) a tool-icon SVG with its own `fill` crashes Cura at start-up while the log still says "Loaded plugin": we ship no SVG and use Cura's built-in `MeshType` icon; (2) a flat copy into `plugins/` loads but is missing from Marketplace > Manage: now `plugins/<ID>/<ID>/` plus a `packages.json` record; (3) Cura hides the left toolbar until a model is loaded: Extensions menu entry and a one-time message; (4) "Loaded plugin" is weak proof: the check needs our self-test line with no crash text after it. All tested against a fake Cura folder and stand-in modules, **not a real Cura**; the `packages.json` record format is copied from the earlier plug-ins' notes, not re-verified here.
- First cylinder detector grew a patch of 400 triangles around the click; on a 12,500-segment cylinder that patch covered under 6° and the fit was rejected. Now the patch grows until the normals have turned ~30°.
- The web server did not read POST bodies it did not need, which broke the next request on the same keep-alive connection (`{}GET` seen as the method). It now always drains the body; a test uses one connection for the whole flow.
- Negative zero (`-0.00000`) in a 3MF transform: harmless, fixed for tidiness.

## Measurements

Test machine: 2 cores, modern CPU, Python 3.13, one thread. **Not a 7th-gen Core i3**; expect a few times slower there. Benchmark: `tools/benchmark.py` (an example cartridge made with more facets).

| Triangles | numpy | load STL | topology | pick | thickness | region | peak memory |
|---|---|---|---|---|---|---|---|
| 48,000 | yes | 0.1 s | 0.1 s | <0.1 s | <0.1 s | <0.1 s | 89 MB |
| 48,000 | no | 0.1 s | 0.1 s | <0.1 s | 0.1 s | <0.1 s | 89 MB |
| 200,000 | yes | 0.5 s | 0.3 s | 0.1 s | 0.1 s | <0.1 s | 275 MB (includes building the test mesh) |
| 200,000 | no | 0.5 s | 0.3 s | 0.1 s | 0.3 s | <0.1 s | 275 MB |

Server-side memory alone: about 810 bytes per triangle (200,000 triangles ≈ 200 MB); the loader refuses a model needing more than 60 % of free RAM (estimate 900 bytes per triangle) and says how to reduce it. The browser also needs memory for drawing.

Slicing the 3MF in PrusaSlicer 2.7.2 for the cartridge took a few seconds (not timed carefully).

## Unknown / untested

- OrcaSlicer opening the Orca-flavour 3MF.
- Cura on Windows and Mac (on Linux Mint it works well in a real Cura, per the author's log). The icon reuses Cura's built-in `MeshType` icon and may look wrong.
- Windows and Mac launchers; Windows/Mac Cura folder detection.
- Pore size versus density and nozzle; air flow; whether carbon granules of a given size stay in; print quality of an open gyroid face on a bottom surface (first layer on the bed).
- Newer PrusaSlicer versions: setting names are from 2.7.2; a newer version may rename or retype some (e.g. enum values).
- A real 7th-gen Core i3.

## Ideas

- **Mesh gyroid mode**: generate an actual gyroid solid (TPMS) as geometry, so pore size is exact and independent of the slicer. Heavy on triangles; needs marching cubes in C++.
- A **pore calibration coupon**: small test squares at several densities with your nozzle.
- A **housing and lid generator** (fill port, screw lid, gasket seat).
- Cones and free-form surfaces (pick by painting).
- SuperSlicer should read the PrusaSlicer-flavour 3MF; untested.
- A real window drawn on the face instead of sliders.

## How to test a change

```
python3 tools/build_cura_plugin.py      # after touching src/gyroid_filter/{mesh,regions,settings}.py
cd tests && python3 -W ignore -m unittest discover -p "test_*.py"
python3 tools/screenshots.py            # needs playwright + Chrome; fails on any JavaScript error
```
`tests/test_prusaslicer.py` is skipped unless the `prusa-slicer` command exists (`sudo apt install prusa-slicer`).
