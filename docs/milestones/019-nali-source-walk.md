# Nali1 source walk reference

Prepared on 2026-10-28 after PR #18. This checkpoint extracts a **private,
read-only animation reference** for the Nali visible in the castle intro. It
does not rig or animate the Meshy prototype and does not change the UE5 map.

## Acceptance criteria and result

- Identify the castle actor and the corresponding original mesh, without
  substituting the playable character's mesh: **met**. The source map's
  `Nali0` is class `Nali`. The original `Nali` class uses `Nali1` from
  `UnrealShare.u`; `Nali2` is the `NaliPlayer` mesh from `UnrealI.u`.
- Admit only a checked original package and fail on malformed mesh records:
  **met** for the installed package hash below. The v61 map reader is unchanged.
- Export all source `Walk` poses to a new private directory, with hashes and
  no overwrite: **met**. Twenty OBJ files and one JSON report were written.
- Verify source frame, face, UV, sequence and notify data with meaningful
  synthetic tests: **met**; 279 Python tests passed in the full suite.
- Review the Meshy prototype from front, back and sides before choosing a rig:
  **met** with temporary Blender renders. The output remains a visual prototype.

## Original source evidence

The installed package was read from
`/Applications/Unreal.app/Contents/Resources/System/UnrealShare.u` without
modification. Its SHA-256 is
`ab2e571dd2e0bad0d8e4389f4d8bc1c7476a61d809de69ce2e7552511197864d`.
The `Nali1` LodMesh is export index 3346, with SHA-256
`11643260bc3301b1d332cdac1735350f2873554c5afc6b5745909088c5e51df7`.
The checked asset has **293 vertices per frame, 397 frames, 33 sequences,
568 full-detail faces and 500 wedges**, with source texture
`UnrealShare.Skins.JNali1`. Its full-detail faces have no degenerate vertex
triples. The mesh scale is approximately `(0.069, 0.069, 0.138)`; the source
origin and rotation are retained separately in the report.

`Walk` occupies frames 262–281 inclusive, has a recorded rate of 15 frames/s,
and contains `Step` notifies at fractions 0.25 and 0.75. Dividing 20 by 15
gives a **nominal** 1.333-second loop. Runtime animation-rate overrides,
interpolation, actor movement and footstep sound mapping have not been
measured. The package also contains `Backup`, `Run`, `WalkFire` and `WalkTool`
sequences; this checkpoint only exports `Walk`.

The installed `UnrealShare.u` has malformed later export-table records after
index 13626. The new `TargetPackage69` reader validates names, imports and
the first 13,627 export entries needed to resolve the selected mesh and its
texture path. It never patches the installed package or treats the unparsed
trailing records as valid. The preparation command requires the exact package
and mesh hashes and exact `Walk` sequence values. This narrow v69 exception
does not loosen the strict v61 map reader.

The private outputs are in
`data/converted/Unreal/Characters/Nali/source-walk/` of the owner's main
checkout. `Nali1.Walk.json` records each OBJ SHA-256, source provenance,
all 33 sequence descriptors, mesh transform and limitations. Every OBJ was
rehashed after writing; files 00 and 19 each contain 293 positions and
568 faces. The OBJ vertices are in **scaled mesh-local** coordinates and
include source face order and wedge UVs with the OBJ V-axis flip. They do not
apply mesh origin/rotation or actor transform. OBJ does not carry the original
material-slot data; use the reader's `NaliMesh.faces` and source package when
building a later conversion. These files are diagnostic pose references,
not a UE5 skeletal animation.

## Visual review of the Meshy prototype

The unchanged private `Nali_ue5.glb` was opened with installed Blender 5.2.3
and rendered from four orthographic angles to temporary PNG files. Front and
back show four separate arms and hands. Side views show substantial overlap
between the upper and lower arm pairs, especially around the shoulder and
elbow silhouettes. The lower shoulder attachment and mesh seams require close
topology inspection before skinning. The GLB remains the high-detail visual
reference: 892,194 triangles, unrigged, and previously measured with 69,880
boundary/nonmanifold edges. No remesh, auto-rig, animation service, additional
credits or UE5 editor import was used.

## Reproduce and continue

Use Python 3.12+ from the repository `.venv`; supply an installed package
with the recorded hash. The output directory must not already exist:

```sh
python -m ue1_converter.nali_prepare \
  /Applications/Unreal.app/Contents/Resources/System/UnrealShare.u \
  --output-dir data/converted/Unreal/Characters/Nali/source-walk
```

For a fresh clone, make a new private output directory and use an absolute
path to the owner's installed package. Run `bash scripts/run-tests.sh` after
changing the reader. The tested run used `PYTHONPATH=tools/src` because its
Python environment was installed editable from a different worktree.

Next: inspect the four-arm shoulder topology and source poses together, then
make a lower-density deformation mesh while preserving the original GLB.
Design a custom four-arm skeleton, retarget the **motion cues** from the 20
source poses, and validate feet, all four arms and cloth in a separate UE5
test scene. Original `Nali0` patrol timing/links and sounds need separate
source verification before castle integration. No extra Meshy credits should
be spent without an explicit task and approval.
