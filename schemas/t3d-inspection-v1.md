# T3D inspection JSON, version 1

Produced by `python -m ue1_converter inspect-t3d`; `schema_version` is 1.
This inventory is private when produced from game exports. It is not an evaluated
mesh format. Array order is deterministic and follows source order unless noted.

| Field | Meaning |
| --- | --- |
| `source` | Original filename, raw-byte SHA-256, byte/line counts, selected codec |
| `interpretation` | Limits on geometry, units, defaults, references, and camera data |
| `counts`, `actor_classes` | Source block/record counts; class keys sorted |
| `explicit_csg_operations` | Counts of exported operation properties; omitted values excluded |
| `models` | Inline definitions with model name, reference, source actor index/name, line, polygon count |
| `brushes` | Brush/Mover instances in actor order, raw properties and CSG operation, exact model-reference matches |
| `camera_points` | InterpolationPoint actors in source order; specified Position/Location and all raw properties |
| `camera_groups` | Groups by raw Tag value, sorted explicit positions, omitted positions, duplicate positions |
| `scene_controls` | Raw LevelInfo, SpecialEvent, Trigger, PlayerStart, and SkyZoneInfo properties |
| `references` | Unique explicit kind/path pairs sorted lexically, with occurrence counts |
| `diagnostics` | Warnings ordered by line and code, including source actor index/name |

Actor indices are zero-based within the Map. Source lines are one-based. A name
can occur more than once and must never be used alone as instance identity.
Property records contain `name`, raw `value`, and `line`. Quotes, object paths,
enum spellings, numeric tokens, and omitted vector/rotator components are retained.
Missing properties are represented by null or omitted from property lists; no
class defaults, identity transforms, or camera position zero are inferred.

`geometry_status` is `inline`, `shared`, or `unresolved`. Definitions bind only
when an actor's exact exported Model reference agrees with its inline brush name.
An instance resolves only when that exact reference has one definition. Zero or
multiple definitions remain unresolved. Polygons and vertices are counted once
per inline definition, rather than again for each shared instance. The parser API
retains full polygon records; this inventory does not serialize their coordinates.

`location_specified` contains only exported camera Location components in source
units, or null when absent/invalid. Other camera properties remain raw. Position
is an explicit integer or null; this array is not a validated playback path.
RateModifier is not interpreted as a duration. Camera linking, interpolation,
looping, field of view, and omitted defaults require runtime investigation.

Reference discovery covers explicit object references in properties and headers,
plus bare polygon Texture headers. Class-default dependencies, texture animation,
and other package dependencies are not discovered by this pass.

Warnings currently cover malformed transform components, duplicate actor names,
unbound model definitions, unresolved model instances, omitted camera positions,
and duplicate camera positions within a raw Tag group. Duplicate actor properties
are retained by parsing but cause inspection to fail rather than choose a value.
Successful inspection with warnings does not establish conversion readiness.
