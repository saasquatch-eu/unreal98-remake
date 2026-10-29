# Nali1 four-arm skeleton layout and remesh assessment

Prepared on 2026-10-29 after merged PR #21. This checkpoint defines and saves
an independently authored **armature layout** for the Nali character. It does
not skin the visual model, simulate muscle, create a walk animation, import a
skeletal asset into UE5 or place `Nali0` in the castle.

## Acceptance criteria and result

- Preserve the checked original Meshy GLB and make new private outputs: **met**.
  The source SHA-256 stayed
  `7420903cc74d03838a196ac20028848738c5b898970f5aab9602c6151dc5cc18`.
- Run at most one owner-approved 5-credit quad remesh and inspect the saved
  bytes: **met**. Meshy task `01a1883d-db61-730e-94a7-a477e6a43efc` succeeded
  and charged exactly **5 credits**; the balance changed from 1550 to 1545.
- Determine whether that remesh is skinning-ready: **failed**. It has 1,551
  disconnected components and 25,465 boundary edges. A quad request did not
  produce a continuous four-shoulder deformation surface. Do not use it as
  a skeletal mesh or spend credits on automatic rigging of it.
- Save a reusable, four-arm skeleton layout with named chains and a checked
  source guide: **met as a template**. The private `.blend` has 91 bones,
  four clavicle/upper/forearm/hand chains, four sets of fingers/thumbs,
  arm twist bones, pelvis/spine/head and two leg chains. Deltoid/biceps
  guide bones are non-deforming markers, not muscle mechanics.
- Verify the saved scene and independent arm parenting: **met**. A 0.45-radian
  left lower-clavicle pose moved its hand 0.1648 m; the other three hand
  endpoints did not move. The saved scene was reopened and read back with
  91 bones, the checked 481,942-vertex visual guide visible, and the rig
  displayed in front.
- Build a deformation mesh, painted weights and muscle behavior: **pending**.
  Neither the original 906-shell model nor the 1,551-shell remesh can be
  accepted merely because an armature exists beside it.

## Private evidence

The new Meshy download is ignored at
`data/converted/Unreal/Characters/Nali/meshy_output/20261029_nali-quad-remesh-ue5_01a1883d/Nali_quad_remesh_ue5.glb`.
SHA-256: `34d0da68c6e7c64b7a0b31798a4e02c9b1e99dbf7fc1362c6347c21a4eb0620b`.
Static GLB inspection found 51,002 vertices, 73,652 triangles, one material,
one UV set and three 4K PBR textures, but no skin, skeleton or animation.
Tangents are absent and would need generation on import. Blender topology
inspection counted 1,551 connected components, 25,465 boundary edges and
one additional nonmanifold edge. A front render was saved and inspected as
`Nali_quad_remesh_front_ue5.png` in the same directory. It retains the
four-arm appearance, but appearance does not establish deformation topology.
The original visual GLB had 906 components and 69,880 boundary edges; the
Meshy output reduced boundary count while increasing disconnected pieces.

The selected skeleton scene is ignored at
`data/converted/Unreal/Characters/Nali/skeleton-template-20261029-v3/Nali1_skeleton_ue5.blend`.
SHA-256: `42114b492e06f4e318c6c39b6f4f93d8bc1dc4fa489d43efd4565484c41f87f9`.
The adjacent `Nali1_skeleton_ue5.json` records all bone names, parents,
rest endpoints, deform flags, source hash and independent-arm test distances.
The checked visual model is a **visible, unskinned guide** in the Blender
scene. The guide and remesh remain private and are never committed.

The earlier local Blender QuadriFlow attempts on the 80k closed guide were
rejected by Blender's manifold/normal check. Manual weights on the closed and
textured decimated guides still visibly distorted the lower shoulders. Those
private probes are rejected diagnostics, not rig candidates. The 20 original
`Nali1.Walk` poses remain the motion reference; no source pose was converted
to skeletal keys here.

## Reproduce and validate

The tracked script refuses an existing output directory and rejects any
source GLB whose hash or vertex count differs. Use installed Blender 5.2.3
and a **new** ignored destination:

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background \
  --python tools/convert/nali_skeleton_template.py -- \
  --source data/converted/Unreal/Characters/Nali/meshy_output/20261028_224858_nali-reference-ue5_01a1847c/Nali_ue5.glb \
  --output-dir data/converted/Unreal/Characters/Nali/skeleton-template-NEW
```

The script saves the Blender file and manifest, checks 91 unique bones and
four-chain independence, and never binds or exports the source mesh. Reopen
the saved `.blend` to verify persisted visibility and bone count. The full
repository Python suite passed **285 tests** using this worktree's `tools/src`
on Python 3.12.14. No UE5 editor action or Play validation was performed for
this checkpoint.

## Next character checkpoint

Make a purpose-built low-density deformation surface around all four
shoulders, elbows, wrists, hips and knees. The template is a starting layout:
anatomical joint positions, finger count and bone naming may still need
revision against source and visual reference. Bind and paint weights, then
test extreme arm poses, shoulder volume, foot contact and all four hand paths.
Only after the skin passes visual checks should high-detail appearance be
transferred and corrective shapes or UE deformation features be built.
Create a source-guided walk from the 20 `Nali1.Walk` poses, validate in a
separate UE5 test scene, and then add the checked `Nali0` route to the castle.
No additional software installation is currently necessary; manual character
topology and rigging work remains.
