# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Write a 3MF that PrusaSlicer or OrcaSlicer opens with the open-cell region already in place
as a modifier volume carrying the gyroid settings."""
import io
import zipfile
from xml.sax.saxutils import quoteattr

from .settings import prusa_config, orca_config

IDENT = "1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"
NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
CONTENT_TYPES = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                 '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
                 ' <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
                 ' <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n'
                 ' <Default Extension="config" ContentType="text/xml"/>\n'
                 '</Types>\n')
RELS = ('<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        ' <Relationship Target="/3D/3dmodel.model" Id="rel0" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n'
        '</Relationships>\n')


def _mesh_xml(verts, tris, pad="  "):
    out = [pad + "<mesh>", pad + " <vertices>"]
    out += ['%s  <vertex x="%.5f" y="%.5f" z="%.5f"/>' % (pad, x, y, z) for x, y, z in verts]
    out += [pad + " </vertices>", pad + " <triangles>"]
    out += ['%s  <triangle v1="%d" v2="%d" v3="%d"/>' % (pad, a, b, c) for a, b, c in tris]
    out += [pad + " </triangles>", pad + "</mesh>"]
    return "\n".join(out)


def placement(mesh, bed_xy):
    """Translation that puts the part's footprint centre on the bed centre and its base at Z=0."""
    lo, hi = mesh.bbox()
    return (bed_xy[0] - (lo[0] + hi[0]) / 2, bed_xy[1] - (lo[1] + hi[1]) / 2, -lo[2])


def _transform(t):
    return "1 0 0 0 1 0 0 0 1 %.5f %.5f %.5f" % tuple(v + 0.0 for v in t)   # +0.0 turns -0.0 into 0.0


def write_prusa(mesh, regions, bed_xy=(125.0, 105.0), name=None):
    """regions: list of (label, Mesh, density_pct). One object; body + modifiers as volumes."""
    name = name or mesh.name
    verts, tris, spans = [], [], []
    for label, m, kind, dens in [(name, mesh, "ModelPart", None)] + [(l, r, "ParameterModifier", d) for l, r, d in regions]:
        off = len(verts)
        first = len(tris)
        verts += m.verts
        tris += [(a + off, b + off, c + off) for a, b, c in m.tris]
        spans.append((label, kind, first, len(tris) - 1, dens))
    model = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<model unit="millimeter" xml:lang="en-US" xmlns="%s" xmlns:slic3rpe="http://schemas.slic3r.org/3mf/2017/06">' % NS,
             ' <metadata name="slic3rpe:Version3mf">1</metadata>',
             ' <metadata name="Title">%s</metadata>' % name.replace("&", "&amp;").replace("<", "&lt;"),
             ' <resources>', '  <object id="1" type="model">', _mesh_xml(verts, tris, "   "), '  </object>',
             ' </resources>',
             ' <build>', '  <item objectid="1" transform="%s" printable="1"/>' % _transform(placement(mesh, bed_xy)),
             ' </build>', '</model>']
    cfg = ['<?xml version="1.0" encoding="UTF-8"?>', '<config>',
           ' <object id="1" instances_count="1">',
           '  <metadata type="object" key="name" value=%s/>' % quoteattr(name)]
    for label, kind, first, last, dens in spans:
        cfg.append('  <volume firstid="%d" lastid="%d">' % (first, last))
        cfg.append('   <metadata type="volume" key="name" value=%s/>' % quoteattr(label))
        cfg.append('   <metadata type="volume" key="volume_type" value="%s"/>' % kind)
        cfg.append('   <metadata type="volume" key="matrix" value="%s"/>' % IDENT)
        if kind == "ParameterModifier":
            for k, v in prusa_config(dens):
                cfg.append('   <metadata type="volume" key="%s" value=%s/>' % (k, quoteattr(v)))
        cfg.append('  </volume>')
    cfg += [' </object>', '</config>']
    return _zip({"3D/3dmodel.model": "\n".join(model), "Metadata/Slic3r_PE_model.config": "\n".join(cfg)})


def write_orca(mesh, regions, bed_xy=(128.0, 128.0), name=None):
    """OrcaSlicer/Bambu layout: every volume is its own object, one assembly object holds them."""
    name = name or mesh.name
    parts = [(name, mesh, "normal_part", None)] + [(l, r, "modifier_part", d) for l, r, d in regions]
    asm = len(parts) + 1
    model = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<model unit="millimeter" xml:lang="en-US" xmlns="%s">' % NS,
             ' <metadata name="Title">%s</metadata>' % name.replace("&", "&amp;").replace("<", "&lt;"),
             ' <resources>']
    for i, (label, m, kind, dens) in enumerate(parts, 1):
        model += ['  <object id="%d" type="model">' % i, _mesh_xml(m.verts, m.tris, "   "), '  </object>']
    model += ['  <object id="%d" type="model">' % asm, '   <components>']
    model += ['    <component objectid="%d"/>' % i for i in range(1, len(parts) + 1)]
    model += ['   </components>', '  </object>', ' </resources>', ' <build>',
              '  <item objectid="%d" transform="%s" printable="1"/>' % (asm, _transform(placement(mesh, bed_xy))),
              ' </build>', '</model>']
    cfg = ['<?xml version="1.0" encoding="UTF-8"?>', '<config>', ' <object id="%d">' % asm,
           '  <metadata key="name" value=%s/>' % quoteattr(name)]
    for i, (label, m, kind, dens) in enumerate(parts, 1):
        cfg.append('  <part id="%d" subtype="%s">' % (i, kind))
        cfg.append('   <metadata key="name" value=%s/>' % quoteattr(label))
        cfg.append('   <metadata key="matrix" value="%s"/>' % IDENT)
        if kind == "modifier_part":
            for k, v in orca_config(dens):
                cfg.append('   <metadata key="%s" value=%s/>' % (k, quoteattr(v)))
        cfg.append('  </part>')
    cfg += [' </object>', '</config>']
    return _zip({"3D/3dmodel.model": "\n".join(model), "Metadata/model_settings.config": "\n".join(cfg)})


def _zip(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        for k, v in files.items():
            z.writestr(k, v)
    return buf.getvalue()
