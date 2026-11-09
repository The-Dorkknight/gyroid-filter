# Contributing

Thanks for helping. This is a small work-in-progress project.

- Reports of what happened in a **real OrcaSlicer** or a **real Cura** are the most valuable thing right now. Please include the slicer name and version, your OS, and (for Cura) the `GyroidFilter` lines of `cura.log`.
- Contributions fall under the same licence as the project (PolyForm Noncommercial 1.0.0, see [LICENSE.md](LICENSE.md)). By sending a change you agree it may be distributed under it.
- Keep it light: standard library only in `src/gyroid_filter`, so it runs on an old laptop. numpy may speed things up but must stay optional.
- After changing `mesh.py`, `regions.py` or `settings.py` run `python3 tools/build_cura_plugin.py` (the plug-in carries a copy) and the tests in [DESIGN_NOTES.md](DESIGN_NOTES.md#how-to-test-a-change).
- Do not state in docs anything that was not tested; say "not tested" instead.
