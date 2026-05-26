# Theory Notes

## Viscous-Spring Artificial Boundary

The viscous-spring artificial boundary represents the far-field soil domain with normal and tangential springs and dashpots attached to the truncated model boundary.

For homogeneous isotropic soil, the plugin computes:

```text
G  = E / (2 * (1 + nu))
lambda = E * nu / ((1 + nu) * (1 - 2 * nu))
Vp = sqrt((lambda + 2G) / rho)
Vs = sqrt(G / rho)
```

The boundary coefficients currently use:

```text
K_normal = E / (2R)
K_shear  = G / (2R)
C_normal = rho * Vp
C_shear  = rho * Vs
```

Nodal values are weighted by tributary geometry:

```text
K_node = tributary_area_or_length * K_boundary
C_node = tributary_area_or_length * C_boundary
```

## 3D Boundary Faces

For a 3D soil box with a free top surface, the plugin applies boundaries to five truncated faces:

- bottom
- X minimum side
- X maximum side
- other horizontal minimum side
- other horizontal maximum side

Each face receives one normal and two shear `SpringDashpotToGround` components.

## 2D Boundary Edges

For a 2D soil domain, the plugin applies boundaries to:

- bottom edge
- left edge
- right edge

Each edge receives one normal and one shear component.

## Layered Soil

Layered soil requires material-dependent boundary parameters on the artificial boundary. The plugin now builds a node-to-material map from adjacent boundary elements and computes `K_normal`, `K_shear`, `C_normal`, and `C_shear` from the material assigned to each boundary node.

When a boundary node lies on a layer interface and is adjacent to elements from more than one material, the nodal tributary contribution is split by adjacent material counts. The resulting `SpringDashpotToGround` components are additive on the same node and degree of freedom, so the interface node receives a weighted contribution from each neighboring layer instead of being forced into only one material group.

For section assignments that are available directly on mesh elements, the element material map is used without geometric inference. For common horizontal layered models whose section assignments are stored on geometric cells, the plugin falls back to a layer-position inference: each section cell's `pointOn` coordinate is read along the selected vertical axis, element centroids are classified into the corresponding layer interval, and boundary nodes inherit the dominant material of their adjacent elements.

This solves the artificial-boundary parameter mismatch for layered soil truncation. Internal reflection and transmission at layer interfaces are still governed by the finite-element model itself; the viscous-spring boundary is applied only to the truncated external faces or edges. Oblique or strongly irregular material zones should still be validated against a benchmark model because the cell-position fallback assumes horizontal layering.

## Equivalent Seismic Boundary Input

Version `0.3.0` adds a practical equivalent-input workflow for PEER strong
motion files. The plugin reads PEER acceleration (`.AT2`), velocity (`.VT2`),
and displacement (`.DT2`) files and converts the source units into the selected
model length unit:

```text
AT2: g      -> model_length / s^2
VT2: cm/s   -> model_length / s
DT2: cm     -> model_length
```

After viscous-spring boundary groups are created, each group receives an
equivalent nodal force time history:

```text
F(t) = K_node * u_g(t) + C_node * v_g(t)
```

where `K_node` and `C_node` are the same tributary-weighted coefficients used
for the visual `SpringDashpotToGround` boundary, and `u_g(t)` and `v_g(t)` are
the converted ground displacement and velocity records. The load direction is
defined in global coordinates by the normalized `Incident Vector` value.

This implementation is intended as a direct uniform boundary-motion input. It
does not yet model layered free-field deconvolution, oblique wave scattering, or
spatially variable wave arrival along the boundary.
