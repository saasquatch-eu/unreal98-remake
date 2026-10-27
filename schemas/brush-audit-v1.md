# Brush audit JSON, version 1

Produced by `validate-brushes`. Detailed map-derived output belongs under ignored
`data/converted/`. This is a coordinate audit, not evaluated BSP or a mesh format.

- `source` and `package` identify the original input hashes and binary format.
  Both must match recorded export provenance before any component is substituted.
- `reference_commit` pins the published math/default reference; `limitations`
  records unsupported behavior and numerical precision boundaries.
- `numeric_evidence` contains source actor index/name and line, original property
  component/token, decoded float32 value, binary export index, absolute byte
  offset, and the four original little-endian bytes as hex. Actor indices and
  binary export indices are distinct zero-based identifiers. Lines are one-based.
- `brushes` follows source actor order, retaining repeated names and shared model
  references. It records source-space bounds, source polygon count, orientation,
  explicit CSG operation and raw actor PolyFlags. Bounds use rounded T3D values
  except for the specifically evidenced components; they are not final UE5 bounds.
- `counts` distinguishes 186 brush instances from the count of inline model
  definitions. Movers stay separate; the omitted-operation brush is categorized
  by the published active-brush default. Static operations still require full
  BSP flag/solidity handling.

Raw source exports are unchanged. Only the audit's in-memory transform view uses
binary evidence. The strict numeric parser continues to reject malformed tokens.
The binary reader currently accepts only v61, licensee zero, flags zero, selected
objects without state frames/array tags, and explicit finite Vector properties.

Successful coordinates do not prove CSG, UV rendering, collision, or flyby fidelity.
The original-runtime oracle was not executed. Nonzero shear is unsupported;
the published default of zero shear is used for omitted SheerRate. Floating-point
operations use Python double precision, with the published legacy rotator grid.
