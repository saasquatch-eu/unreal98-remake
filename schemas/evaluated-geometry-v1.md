# Evaluated geometry bundle, version 1

`extract-bsp` creates `<Map>.geometry.json` and `<Map>_ue5.obj` in a new private
directory. `schema_version` is 1. This format carries stored geometry, not a new
CSG evaluation or UE5-ready physics/material contract.

| Field | Meaning |
| --- | --- |
| `source`, `package` | Provenance hashes, format version, world model reference/name, native table references |
| `points` | Original compiled world points, followed by separately transformed Mover rest points |
| `surfaces` | Original texture path, raw flags, normal, texture origin/basis, pan, owning actor, source polygon |
| `faces` | Original point boundary, triangulated point triples, omitted boundary-corner indices, role, surface index |
| `zones` | Original zone actor paths, connectivity and visibility masks |
| `movers` | Original actor name/index, face range, raw source properties including animation keys |
| `zone_samples` | Source camera, PlayerStart, and SkyZoneInfo positions queried against the stored BSP |
| `diagnostics` | Table counts, referenced graph coverage, stale unused pool count, native plane deviation, render counts/bounds |

Native faces additionally retain node index, plane, node flags, and zone pair.
Indices into arrays are zero-based. Native serialized object references retain
their original signed/one-based package convention. Texture names and hierarchy
are never inferred from group labels or renamed in the JSON.

Coordinates remain in original UE1 units. Static points are already transformed;
brush transforms must not be applied again. Mover rest geometry uses the validated
T3D transform path and its available decimal precision, with animation pending.

UV values are **texels**, computed from stored origin/basis/pan, not normalized
UE5 UVs. The OBJ carries positions and normals for visible world/Mover geometry;
it deliberately has no `vt` entries or material import instructions. Texture
dimensions must be established before normalized UVs are created.

Roles are `world`, `mover`, `sky_mask`, `sky_geometry`, `invisible`,
`invisible_portal`, or `solid_interior`. Raw flags survive regardless of role.
Visible translucent portal surfaces stay in world geometry; invisible portal
planes and sky masks are not exported as opaque walls. These are render-extraction
categories, not a collision classifier. Sky-zone geometry remains in JSON.

Triangulation uses the dominant normal projection and an extent-scaled area
tolerance of 1e-12. Original boundaries are retained. Duplicate projected corners
and collinear backtracking spurs can be omitted, with their boundary positions
listed in `omitted_corner_indices`. Ordinary collinear corners stay connected.
Projected area is checked; unsafe boundaries stop extraction. Stored BSP plane
deviation is reported without reprojecting original vertices onto planes.

The supported native data is v61, licensee zero, flags zero, with plain native
geometry objects. Geometry tables are fully consumed; Level/Model prefixes are
read only as far as required. Lighting and collision-data tails are not decoded.
No UE5 import, collision, sky rendering, normalized materials, or flyby fidelity
is established by this bundle.
