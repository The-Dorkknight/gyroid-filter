# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""One neutral description of 'open-cell gyroid' and its translation to each slicer's setting names.

Open cell means: no walls, no top/bottom skin and no 'small area becomes solid' rule inside the
region, so the gyroid strands are the surface and air (or carbon granules) can pass through."""

DEFAULT_DENSITY_PCT = 25


def clamp_density(pct):
    return max(5.0, min(60.0, float(pct)))


def _fmt(pct):
    p = clamp_density(pct)
    return ("%g" % p)


def prusa_config(density_pct=DEFAULT_DENSITY_PCT):
    """Per-volume overrides for a PrusaSlicer 'modifier' (keys verified against PrusaSlicer 2.7.2)."""
    return [
        ("fill_pattern", "gyroid"),
        ("fill_density", _fmt(density_pct) + "%"),
        ("perimeters", "0"),
        ("top_solid_layers", "0"),
        ("bottom_solid_layers", "0"),
        ("top_solid_min_thickness", "0"),
        ("bottom_solid_min_thickness", "0"),
        ("solid_infill_below_area", "0"),
        ("thin_walls", "0"),
        ("gap_fill_enabled", "0"),
    ]


def orca_config(density_pct=DEFAULT_DENSITY_PCT):
    """Per-part overrides for an OrcaSlicer 'modifier_part' (keys checked against Orca's source)."""
    return [
        ("sparse_infill_pattern", "gyroid"),
        ("sparse_infill_density", _fmt(density_pct) + "%"),
        ("wall_loops", "0"),
        ("top_shell_layers", "0"),
        ("bottom_shell_layers", "0"),
        ("top_shell_thickness", "0"),
        ("bottom_shell_thickness", "0"),
        ("minimum_sparse_infill_area", "0"),
        ("detect_thin_wall", "0"),
    ]


def cura_settings(density_pct=DEFAULT_DENSITY_PCT):
    """Settings for a Cura 'cutting mesh' (the mesh is printed with these instead of the model's)."""
    return {
        "cutting_mesh": True,
        "infill_pattern": "gyroid",
        "infill_sparse_density": clamp_density(density_pct),
        "wall_line_count": 0,
        "top_layers": 0,
        "bottom_layers": 0,
        "min_infill_area": 0,
        "fill_outline_gaps": False,
        "infill_line_width": None,        # filled in by the plug-in only if the user sets it
    }
