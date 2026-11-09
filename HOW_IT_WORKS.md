# How Gyroid Filter works

## In one paragraph

You click a surface. The app finds the whole flat face or cylinder that click belongs to, measures how thick the material is under it, and builds a closed 3D "region" volume under that surface. The region is not part of your model: it is handed to the slicer as a **modifier** (PrusaSlicer, OrcaSlicer) or **cutting mesh** (Cura), carrying settings that print the overlapping part as gyroid with no walls and no skin. The slicer does all the real work.

## What it reads

- The STL or 3MF you open (geometry only). Nothing is uploaded anywhere: the app is a small web server that listens **only on your own computer** (`127.0.0.1`) on a random port, and only answers requests carrying a secret token made at start-up.
- For the Cura tab: the list of Cura settings folders in your home directory (to offer *Install*) and the last lines of `cura.log` mentioning GyroidFilter.

## What it changes

- Exports are new files that you save from the browser. Your original model file is never touched.
- *Install* in the Cura tab copies the plug-in folder to `…/cura/<version>/plugins/GyroidFilter/` and reads it back to check. *Uninstall* removes only that folder.
- In Cura, the plug-in adds child nodes named "Gyroid region" under the model you clicked. Removing them (button, or Cura's normal delete) puts the model back as it was.

## What it never does

- It does not rewrite or post-process G-code.
- It does not change your slicer's profiles or settings files.
- It does not connect to the internet.

## Steps in detail

1. **Topology.** Triangles that share an edge are linked. Vertices that coincide (to 0.0001 mm) are welded.
2. **Flat face.** From the clicked triangle, neighbours are added while their normal is within 1° of the first and their corners within 0.05 mm of its plane.
3. **Cylinder.** Around the click, triangles are gathered until their normals have turned about 30°. The cylinder axis is the one direction all those normals are perpendicular to (smallest eigenvector of their covariance); a circle is fitted in the plane across the axis; then every connected triangle whose corners lie on that circle and whose normal is perpendicular to the axis is added. The length and the covered angle (full circle or an arc) come from the result. Whether material is inside (outer surface) or outside (hole) comes from which way the normals point.
4. **Auto** prefers the cylinder if it covers more triangles than the flat patch, because a finely tessellated cylinder looks flat over a few facets.
5. **Thickness.** Up to three rays from the surface into the material; the median distance to the far side is the wall thickness.
6. **Region.** A flat face becomes a prism (the face's triangles pushed to the chosen depth, clipped to the window if any). A cylinder becomes a ring segment between two radii. Both stick out 0.3 mm beyond the surface so they cut cleanly through the skin. The app checks each region is a closed solid and shows ✓ or a warning.
7. **Export.** The region is added to the model as a second volume with the open-cell settings (see the table in the README).

## Why open-cell gyroid helps a filter

Gyroid infill is a continuous wavy sheet that splits space into two interlocking channels. With no walls or skin, those channels reach the outside, so air can flow through a wall of it while the strands hold granules back. Pore size is set by density and nozzle width; the app does not predict it.
