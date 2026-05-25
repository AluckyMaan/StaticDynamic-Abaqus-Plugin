# Workflow Notes

## Core Pipeline

The plugin currently follows this sequence:

1. Locate the Abaqus model and soil instance.
2. Detect model dimension as 2D or 3D.
3. Extract material properties from the soil material.
4. Detect artificial boundary faces or edges.
5. Create a visible boundary node set.
6. If spring-damping is enabled:
   - create or reuse a geostatic step
   - temporarily constrain boundary nodes
   - submit a geostatic job
   - read boundary reaction forces from the ODB
   - remove temporary constraints
   - apply weighted visual viscous-spring boundaries
   - apply equivalent reaction-balance nodal loads
7. If seismic load is enabled:
   - read wave data
   - create the final analysis step
   - create the final job
   - optionally submit the final job

## GUI Modes

The GUI enables and disables parameter groups according to selected functions:

- Node set only: model and node-set options are active.
- Spring damping: geostatic and job resource parameters are active.
- Seismic load: dynamic parameters and wave file options are active.

## Validation Checklist

For a regular 3D box, confirm:

- five boundary faces are detected
- bottom face area equals model plan area
- each side face area equals side geometry area
- generated `SD_VisualVS_*` features exist
- generated `SD_VS_Group_*` sets correspond to tributary area groups

For 2D models, confirm:

- three boundary edges are detected
- two spring-dashpot directions are created for each edge
- no out-of-plane DOF is used
