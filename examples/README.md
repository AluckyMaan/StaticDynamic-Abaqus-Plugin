# Examples

Large Abaqus `.cae` and `.odb` files are intentionally not stored in this repository.

Suggested validation case:

```text
3D homogeneous soil box
Dimensions: 40 x 40 x 30
Vertical axis: Z
Element type: C3D8R
Boundary faces:
  Bottom area = 1600
  Each side area = 1200
```

Expected boundary detection:

```text
Bottom: 81 nodes
XMin:   63 nodes
XMax:   63 nodes
YMin:   63 nodes
YMax:   63 nodes
Unique boundary nodes: 273
```

Expected weighted boundary behavior:

```text
Bottom total tributary area = 1600
Each side total tributary area = 1200
```

Screenshots and lightweight model-generation scripts can be added here in future releases.
