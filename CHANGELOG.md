# Changelog

## 0.2.1 - 2026-05-26

- Added run preflight checks for function dependencies, model inputs, geostatic
  file/source consistency, spring-damping depth, and balance tolerance.
- Added `StaticDynamic_run_report.txt` and `StaticDynamic_run_report.csv` with
  input, boundary, material, reaction, spring-dashpot, load, step, and job
  summaries.
- Added report statistics for boundary tributary weights, ODB balance checks,
  CSV reaction gaps, spring-dashpot groups, and reaction-balance loads.
- Updated the geostatic file browser to switch ODB/CSV filters from the selected
  source and keep the text field, command keyword, and dialog cache in sync.
- Compacted the lower-left GUI layout so the wave-file selector is visible on
  high-DPI Abaqus/CAE dialogs.
- Made dialog debug logging opt-in through `STATICDYNAMIC_DEBUG`.
- Added `examples/validate_current_session.py` for lightweight Abaqus-session
  boundary and tributary-weight validation.

## 0.2.0 - 2026-05-25

- Added layered-soil viscous-spring boundary grouping by adjacent boundary element material.
- Added a horizontal cell-layer fallback for section assignments stored on geometry cells.
- Added split material contributions for boundary nodes located on layer interfaces.
- Added X/Y/Z vertical-axis selection and automatic viewport orientation.
- Skipped zero-magnitude reaction-balance nodal loads to avoid Abaqus load creation errors.
- Replaced internal geostatic-run mode with external ODB/CSV geostatic reaction inputs.
- Added ODB displacement-balance checks with a default `1.0e-4` tolerance.
- Added `BoundaryInfo.csv` export with face names, material fractions, and tributary weights.

## 0.1.0 - 2026-05-25

- Added Abaqus/CAE GUI plugin scaffold.
- Added 3D five-face viscous-spring artificial boundary detection.
- Added 2D three-edge boundary logic.
- Added weighted nodal spring-dashpot coefficients based on tributary area or length.
- Added geostatic equilibrium RF extraction and reaction-balance load workflow.
- Added GUI control-state optimization for geostatic and dynamic parameters.
