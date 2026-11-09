# Changelog

Semantic versioning. Newest first.

## 0.1.0-wip: 2026-11-09

**Logged 2026-11-09 19:56 (Europe/London), after the build above:**
- Cura plug-in tested by the author in a real Cura on Linux Mint: it works well. This is the first run in a real Cura; the earlier entries that say "not tested" for the Cura plug-in are superseded for Linux only. Windows and Mac Cura are still untested.
- Cura versions, the exact steps, and the cutting-mesh results were not recorded in the report, so they are not claimed here.

First public work-in-progress build. Project started 2026-11-09 09:55.

**Added**
- Core (`src/gyroid_filter`): STL and 3MF loading, flat-face and cylinder detection (including partial arcs and finely tessellated cylinders), wall-thickness probe, open-cell region solids for flat faces (whole, rectangle or oval window, rim) and cylinders (axial window, arc, rim), closed-solid check.
- Web app (stdlib server, vendored three.js): open model, click to pick, live preview, regions list, exports (PrusaSlicer 3MF, OrcaSlicer 3MF, Region STLs zip), Cura plug-in installer tab that reads the files back and reads Cura's log.
- Cura plug-in (`cura_plugin/GyroidFilter`): *Gyroid Filter* tool with panel, creates a cutting mesh with gyroid open-cell settings, re-apply, remove, start-up self-test in the log.
- Cura installer hardening, checked against the bugs found in earlier Cura plug-ins (Hybrid Supports, SlicerSwap, Forge-X, Bambu LAN, LoK Walls): installs in Cura's own `plugins/<ID>/<ID>/` layout and records the plug-in in `packages.json` so it shows under Marketplace > Manage (an old flat copy is migrated); a `packages.json` that cannot be read is never overwritten and other plug-ins' records are kept; the log check needs the self-test line and no crash text after it, and says it cannot prove Cura stayed open; an Extensions menu entry and a one-time start-up message, because Cura hides its toolbar until a model is loaded; no SVG icon is shipped (an SVG that already had a `fill` attribute crashed Cura at start-up) and a test guards that; paths and log text are HTML-escaped in the installer tab.
- Launchers for Linux, Windows and Mac; example cartridge; tests; PDF manual; GitHub Pages site; release workflow.

**Tested for real:** PrusaSlicer 2.7.2 slicing of the exported 3MF (G-code read back); web app in headless Chrome; Linux launcher; server API incl. security checks; geometry unit tests.

**Not tested:** OrcaSlicer opening the Orca 3MF; Cura on Windows and Mac (on Linux Mint it works well in a real Cura, per the author's log); Windows and Mac launchers; any real printing or filtering; a real 7th-gen Core i3.
