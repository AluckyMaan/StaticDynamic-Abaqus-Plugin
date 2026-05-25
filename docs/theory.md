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

Layered soil requires material-dependent boundary parameters. The current public version does not yet group boundary nodes by layer material. For layered soil, a future implementation should infer material properties from adjacent boundary elements or user-provided layer definitions.
