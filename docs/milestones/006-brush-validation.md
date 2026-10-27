# Castle intro: numeric evidence and brush-coordinate validation

Completed on 2026-10-27 with the existing Python environment, original local map,
and published OldUnreal references. No additional software or asset service is
needed for this checkpoint. No UE5 editor operation was performed.

## Result

The four malformed pivot tokens in the T3D export now have exact float32 evidence
from the original binary map. A read-only, bounded package reader finds each
unique Brush object and its explicit PrePivot Vector property. It records byte
offsets, raw bytes, exact decoded values, source actor indices, and source tokens.
Both input hashes must match the original export provenance. The source export
and original map are never rewritten; the coordinate audit uses a separate
in-memory evidence overlay. The inspection report's original warnings remain.

The private report is
`data/converted/Unreal/Maps/Unreal/Unreal.brush-audit.json`.
See `../../schemas/brush-audit-v1.md` and `../../tools/README.md` for format,
commands, and explicit restrictions.

The two `8e-06.0` tokens correspond to the float32 representation of approximately
0.000008. The other tokens correspond to approximately -0.000001 and -0.000006.
These are export-format anomalies; the underlying pivot values are valid finite
numbers. No global suffix stripping or permissive numeric parser was introduced.

## Transform validation

Independent Python matrix composition follows the published brush model sequence:
subtract PrePivot, apply MainScale, rotate, apply PostScale, then add Location.
Omitted transform fields use the documented zero/identity defaults. The reference
does not bake TempScale or DrawScale into brush model coordinates. Texture
gradients and normals use inverse transpose; UV gradients retain their magnitude.
Negative determinant transforms require reversed polygon winding.

The audit processes all 186 source brush instances, resolving reused models while
retaining instance order and duplicate names:

| Observation | Count |
| --- | --- |
| Source brush instances | 186 |
| Explicit static add/subtract instances | 183 |
| Active brush by published default, excluded from static CSG | 1 |
| Movers, kept separate from static CSG | 2 |
| Mirrored transforms | 36 |
| Binary-backed pivot components | 4 |

Source-space bounds are finite for every instance. The audit is not an evaluated
solid model. Actor PolyFlags include combined rendering/solidity/portal flags;
these still require validation before applying all operations as ordinary solids.
Nonzero shear fails explicitly. All transforms in this map use zero/default shear.

## Synthetic CSG reference and tests

A finite-window, axis-aligned reference evaluates ordered occupancy and volume
without generating polygon boundaries. Tests subtract a room from initially
solid space, restore a pillar, cut an opening, reverse operation order, overlap
solids, and repeat operations. This supplies analytic expectations for future BSP
tests; it is not a general brush evaluator. Face membership is half-open and does
not emulate the original engine's BSP tolerances or semi/non-solid behavior.

`bash scripts/run-tests.sh`: **65 passed**. New cases also cover compact indices,
binary table/property bounds, Boolean tags, selected-object ambiguity, unsupported
state frames/arrays/versions, malformed provenance, protection of all input files,
pivot/scale/rotation order, inverse round trips, signed rotator grid behavior,
normal/UV transforms, and mirrored winding. The original 31 tests still pass.

The real map audit matched recorded map/export hashes and was deterministic on
repeat. Input files and ignore rules were checked, and `git diff --check` passed.
Only authored synthetic bytes/geometry are committed. Reports and the original
game data remain private and ignored. No engine C++ changes require a UE5 build.

## Reference and verification boundary

Primary reference: OldUnreal's published Unreal-PubSrc snapshot
`2bd1ce95a78bfd95fb83e7834abbb878b40b3cb6`, particularly
[ABrush model coordinates](https://github.com/OldUnreal/Unreal-PubSrc/blob/2bd1ce95a78bfd95fb83e7834abbb878b40b3cb6/Engine/Inc/ABrush.h),
[math definitions](https://github.com/OldUnreal/Unreal-PubSrc/blob/2bd1ce95a78bfd95fb83e7834abbb878b40b3cb6/Core/Inc/UnMath.h),
and [Brush defaults](https://github.com/OldUnreal/Unreal-PubSrc/blob/2bd1ce95a78bfd95fb83e7834abbb878b40b3cb6/Engine/Classes/Brush.uc).
Engine source is referenced, not vendored into this repository.

A native UCC compiler probe was attempted in a private scratch directory but did
not compile successfully. When macOS requested app-management permission, the
user declined and directed that app changes be done manually. That route was
stopped; subsequent validation used Python only. No native-runtime oracle result
is claimed, and no further app-management permission was sought. Application
installation, updates, and removal are the user's manual responsibility.

The published snapshot is a reference for these math semantics, not proof that
every implementation detail matches the installed 227k binary. Python uses double
precision and does not reproduce all native float32 intermediate rounding.

## Next checkpoint

Evaluate the castle's actual ordered BSP with correct solidity flags, shared
brush instances, portal/sky handling, and separate Movers. Validate representative
openings and surface alignment before generating `Unreal_ue5` geometry. Camera
position conflicts, timing, and playback still require their own investigation.
