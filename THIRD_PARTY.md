# Third-party material

The licence in [LICENSE.md](LICENSE.md) covers only Matthew Armstrong's own code. Everything below keeps its own licence. Nothing here implies any affiliation with or endorsement by these projects.

| What | How it is used | Licence |
|---|---|---|
| [three.js](https://threejs.org/) (r187, with its `OrbitControls`) | Bundled, minified, in `src/gyroid_filter/web/vendor/three-bundle.js` (made with [esbuild](https://esbuild.github.io/), MIT). Licence text: `src/gyroid_filter/web/vendor/THREE-LICENSE.txt` | MIT |
| [Cura](https://github.com/Ultimaker/Cura) and [Uranium](https://github.com/Ultimaker/Uranium) | Not included. The plug-in is written against their plug-in API; the `SupportEraser` tool was read as the model for the tool pattern, no code copied | LGPL-3.0 |
| [PrusaSlicer](https://github.com/prusa3d/PrusaSlicer) | Not included. Used only to test that its 3MF layout opens and slices (2.7.2 from the Ubuntu package) | AGPL-3.0 |
| [OrcaSlicer](https://github.com/SoftFever/OrcaSlicer) | Not included. Its 3MF importer and setting names were read to write a compatible file; no code copied | AGPL-3.0 |
| [PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0) | The licence text in `LICENSE.md` | (the text of the licence itself) |

Setting names and file layouts are facts about those programs' file formats, listed so the files can be read by them.
