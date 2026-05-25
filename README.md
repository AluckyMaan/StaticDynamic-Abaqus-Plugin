# StaticDynamic Abaqus Plugin

[中文说明](README.zh-CN.md)

Current version: `0.2.0`

StaticDynamic is an Abaqus/CAE Python plugin for soil static-dynamic analysis with viscous-spring artificial boundaries.

The current implementation focuses on a practical CAE workflow:

- identify 3D five-face artificial boundaries or 2D three-edge artificial boundaries
- compute viscous-spring boundary parameters from soil material properties, with
  boundary-node grouping for layered soil models
- apply visual `SpringDashpotToGround` features in Abaqus/CAE
- weight nodal spring-dashpot coefficients by tributary area or length
- run geostatic equilibrium, read boundary reaction forces, and apply equivalent reaction-balance nodal loads
- provide a GUI workflow for node-set generation, boundary application, and optional dynamic analysis setup

## Status

This project is under active development. The 3D five-face viscous-spring boundary workflow has been tested on a regular homogeneous soil model. Layered soil boundary grouping is implemented for common horizontal layered models by reading adjacent boundary element materials. Full seismic wave input for layered free fields remains planned work.

## Supported Environment

- Abaqus/CAE 2021-style Python plugin workflow
- Abaqus kernel Python 2.7 compatibility style
- Windows plugin directory workflow

## Installation

Copy this repository folder into an Abaqus plugin search path, for example:

```text
C:\Users\<USER>\abaqus_plugins\StaticDynamic_v1
```

Restart Abaqus/CAE. The plugin should appear as `StaticDynamic v0.2.0` in the plugin menu.

## Basic Workflow

1. Open or create a soil model in Abaqus/CAE.
2. Ensure the soil part has elastic and density material properties.
3. Open the StaticDynamic plugin dialog.
4. Set model name, soil part, soil instance, and vertical axis (`X`, `Y`, or `Z`).
5. Choose one of the workflows:
   - node set only
   - geostatic equilibrium plus viscous-spring boundary
   - full dynamic workflow
6. Run the plugin.
7. Inspect generated assembly sets and visual `SpringDashpotToGround` features.
8. Open the geostatic ODB and check the final-frame displacement field `U`.

## Geostatic Balance Input

The plugin does not compute geostatic balance internally. Complete geostatic
balance first, verify that the final displacement field `U` is acceptable, and
then provide the balanced reaction source to this plugin:

- `ODB`: read boundary node `RF` from the specified step in a balanced ODB.
  The plugin checks the final-frame displacement field `U` before conversion;
  the default tolerance is `1.0e-4`.
- `CSV`: read boundary node reactions from a CSV file with columns
  `nodeLabel, RF1, RF2, RF3` or the same four columns without a header.
  CSV input cannot verify displacement balance, so the user must ensure the
  source model is already balanced.

This keeps staged construction, contact, excavation, tunnels, piles, and other
complex soil-structure balance workflows outside the boundary-conversion plugin.

When `Node Information` is enabled, the plugin exports `BoundaryInfo.csv` with
node coordinates, boundary face name, material fractions, and tributary area or
length. This file can be used to build or audit external geostatic reaction CSVs.

## Boundary Logic

For a 3D soil domain with a free top surface, artificial boundaries are applied to:

- bottom face
- two X-side faces
- two horizontal-side faces normal to the other horizontal axis

For a 2D planar model, artificial boundaries are applied to:

- bottom edge
- left edge
- right edge

Top free surfaces are not treated as artificial boundaries. After a run, the
viewport is automatically oriented so the selected vertical axis is displayed
upright; this changes only the view, not the model coordinates.

## Nodal Weighting

The plugin computes nodal tributary area for 3D boundary faces and tributary length for 2D boundary edges. Nodal coefficients are applied as:

```text
K_node = A_node * K_boundary
C_node = A_node * C_boundary
```

For 2D models, `A_node` is interpreted as tributary length.

## References

The implementation is based on the common viscous-spring artificial boundary approach used in soil-structure interaction analysis, including the static-dynamic unified artificial boundary ideas associated with Liu Jingbo and coauthors.

Do not treat this repository as a substitute for validating boundary parameters for your own model. Always compare against benchmark cases before production use.

## Repository Contents

```text
StaticDynamic.py              Core Abaqus kernel logic
staticDynamic_Form.py         Abaqus/CAE GUI dialog
staticDynamicDB.py            Data and file helpers
staticDynamic_plugin.py       Plugin entry point
staticDynamic_ToolBar.py      Compatibility placeholder
icons/                        Plugin icons
docs/                         Theory and workflow notes
examples/                     Example notes and validation summaries
```

## License

MIT License.
