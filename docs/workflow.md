# Workflow Notes

## Core Pipeline

The plugin currently follows this sequence:

1. Locate the Abaqus model and soil instance.
2. Run preflight checks for function dependencies, model inputs, geostatic file
   consistency, structure depth, and balance tolerance.
3. Detect model dimension as 2D or 3D.
4. Detect artificial boundary faces or edges.
5. Extract material properties when node information or spring-damping output
   requires boundary parameters.
6. Create a visible boundary node set.
7. If spring-damping is enabled:
   - choose a geostatic reaction source: ODB or CSV
   - `ODB`: read boundary reactions from the final frame of the selected step
     in a balanced ODB after checking the final-frame `U` tolerance
   - `CSV`: read boundary reactions from `nodeLabel, RF1, RF2, RF3`
   - apply weighted visual viscous-spring boundaries
   - apply equivalent reaction-balance nodal loads
8. If seismic load is enabled:
   - read wave data from PEER (`.AT2/.VT2/.DT2`), CSV, or Excel files
   - convert PEER units into the selected model length unit
   - choose uniform input or traveling-wave input
   - for traveling-wave input, compute boundary-node arrival delays from the
     propagation vector and apparent velocity
   - create the final analysis step
   - create equivalent boundary input amplitudes and nodal loads from
     `K_node * u_g(t) + C_node * v_g(t)`
   - create the final job
   - optionally submit the final job
9. Write `StaticDynamic_run_report.txt` and `StaticDynamic_run_report.csv`.

## GUI Modes

The GUI enables and disables parameter groups according to selected functions:

- Node set only: model and node-set options are active.
- Spring damping: geostatic ODB/CSV source options are active.
- Seismic load: dynamic parameters and wave file options are active.

## Validation Checklist

For a regular 3D box, confirm:

- five boundary faces are detected
- `BoundaryInfo.csv` lists face names, material fractions, and tributary weights
- bottom face area equals model plan area
- each side face area equals side geometry area
- generated `SD_VisualVS_*` features exist
- generated `SD_VS_Group_*` sets correspond to tributary area groups

For 2D models, confirm:

- three boundary edges are detected
- two spring-dashpot directions are created for each edge
- no out-of-plane DOF is used
