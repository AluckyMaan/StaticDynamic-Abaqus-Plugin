# Changelog

## 0.6.0 - 2026-06-03

- Added oblique incident-wave controls with arbitrary `Incident Angle` and
  `Azimuth Angle` inputs for traveling-wave arrival-delay generation.
- Added angle-to-propagation-vector resolution using the selected vertical axis;
  explicit `Propagation Vector` values remain supported and take precedence.
- Added run-report fields for incident and azimuth angles.
- Updated the Abaqus/CAE dialog and plugin menu to `StaticDynamic v0.6.0`.

## 0.5.0 - 2026-05-28

- Added earthquake-record preprocessing controls: `Wave Scale` and
  `Baseline Correction = RemoveMean`.
- Added `WavePreprocess` run-report audit fields for removed mean, scale,
  and peak amplitudes before/after preprocessing.
- Added `Site Profile CSV` import for `LayeredSite` arrival-delay input.
- Supported imported profile columns such as `verticalCoordinate`,
  `equivalentVs`, `cumulativeTravelTime`, and `sampleCount`; cumulative travel
  time is generated automatically when omitted.
- Updated the Abaqus/CAE dialog and plugin menu to `StaticDynamic v0.5.0`.

## 0.4.0 - 2026-05-28

- Added traveling-wave seismic input mode with spatial arrival-time delay.
- Added separate `Propagation Vector`, `Apparent Velocity`, and optional
  `Delay Bin Size` controls for incident-wave input.
- Split seismic equivalent-load groups by delay bin so different boundary
  locations can receive shifted amplitudes.
- Added run-report fields for arrival mode, propagation vector, apparent
  velocity, delay range, and delay-bin count.
- Added `SeismicArrivalInfo.csv`, per-face arrival-delay statistics, delay-bin
  safety guard, and P/S incident-direction consistency warnings.
- Added `LayeredSite` input mode with model-derived vertical `Vs` travel-time
  delays and `SeismicSiteProfile.csv` audit export.
- Left equivalent-linear site response and free-field column coupling as the
  next `0.5.0` target.

## 0.3.0 - 2026-05-26

- Added PEER NGA strong-motion reader support for `.AT2`, `.VT2`, and `.DT2`
  files.
- Added PEER unit conversion for acceleration in `g`, velocity in `cm/s`, and
  displacement in `cm` to the selected model length unit (`m`, `cm`, or `mm`).
- Added automatic companion-file loading when one PEER component file is
  selected.
- Added equivalent seismic boundary nodal loads using
  `F(t) = K_node * u_g(t) + C_node * v_g(t)` for each spring-dashpot group.
- Added missing velocity/displacement generation by trapezoidal integration
  when lower-order records are not provided.
- Added GUI controls for `Wave Format = PEER` and `Model Length Unit`.
- Added seismic input statistics to the run report.
- Added preflight guards so seismic input requires `Function Option = Seismic`
  and a valid wave record before final job creation.

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
