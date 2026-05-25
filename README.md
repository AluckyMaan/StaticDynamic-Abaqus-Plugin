# StaticDynamic Abaqus Plugin

StaticDynamic is an Abaqus/CAE Python plugin for soil static-dynamic analysis with viscous-spring artificial boundaries.

The current implementation focuses on a practical CAE workflow:

- identify 3D five-face artificial boundaries or 2D three-edge artificial boundaries
- compute viscous-spring boundary parameters from soil material properties
- apply visual `SpringDashpotToGround` features in Abaqus/CAE
- weight nodal spring-dashpot coefficients by tributary area or length
- run geostatic equilibrium, read boundary reaction forces, and apply equivalent reaction-balance nodal loads
- provide a GUI workflow for node-set generation, boundary application, and optional dynamic analysis setup

## Status

This project is under active development. The 3D five-face viscous-spring boundary workflow has been tested on a regular homogeneous soil model. Multi-layer soil parameter grouping and full seismic wave input for layered free fields are planned work.

## Supported Environment

- Abaqus/CAE 2021-style Python plugin workflow
- Abaqus kernel Python 2.7 compatibility style
- Windows plugin directory workflow

## Installation

Copy this repository folder into an Abaqus plugin search path, for example:

```text
C:\Users\<USER>\abaqus_plugins\StaticDynamic_v1
```

Restart Abaqus/CAE. The plugin should appear as `StaticDynamic v1` in the plugin menu.

## Basic Workflow

1. Open or create a soil model in Abaqus/CAE.
2. Ensure the soil part has elastic and density material properties.
3. Open the StaticDynamic plugin dialog.
4. Set model name, soil part, soil instance, and vertical axis.
5. Choose one of the workflows:
   - node set only
   - geostatic equilibrium plus viscous-spring boundary
   - full dynamic workflow
6. Run the plugin.
7. Inspect generated assembly sets and visual `SpringDashpotToGround` features.

## Boundary Logic

For a 3D soil domain with a free top surface, artificial boundaries are applied to:

- bottom face
- two X-side faces
- two horizontal-side faces normal to the other horizontal axis

For a 2D planar model, artificial boundaries are applied to:

- bottom edge
- left edge
- right edge

Top free surfaces are not treated as artificial boundaries.

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
