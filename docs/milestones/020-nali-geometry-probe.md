# Nali geometry and auto-weight probes

Prepared privately on 2026-10-28 after PR #19. This checkpoint tests whether
the Meshy Nali prototype can supply a lower-density **geometry reference** for
a custom four-arm rig. It does not create a production deformation mesh,
skeletal asset, animation or UE5 actor.

## Acceptance criteria and outcome

- Inspect the checked GLB's actual connectivity before reducing it: **met**.
  It has 906 disconnected components and 69,880 boundary edges despite its
  continuous appearance in the prior renders.
- Make a separate lower-density surface while preserving the source GLB:
  **met for a geometry probe**. A 0.008 m voxel remesh and triangle-counted
  decimation produced 80,000 saved triangles, one component and no boundary
  or other nonmanifold edges. Source bounds changed by less than 3 cm on each
  side. The original GLB SHA-256 remained unchanged.
- Validate the saved file, not just Blender's in-memory mesh: **met**. A fresh
  import returned 40,002 vertices, 80,000 triangles, one component, zero
  boundary edges, zero UV layers and zero materials. Four clay views were
  rendered and visually checked; the four-arm silhouette remains visible.
- Test whether a simple four-arm auto-weight rig deforms cleanly: **failed
  visually**. A 26-bone stress armature gave all vertices weights and moved
  all four hands, but its bent pose pulls an upper arm across the chest and
  bunches the lower arms against the hips. This automatic weighting is
  rejected as a rigging solution.
- Keep original assets and private derivatives out of Git: **met**. Only the
  Blender scripts and this handoff are tracked. No Meshy credits, new software
  or UE5 editor actions were used.

## Inputs and saved private outputs

The high-detail source remains
`data/converted/Unreal/Characters/Nali/meshy_output/20261028_224858_nali-reference-ue5_01a1847c/Nali_ue5.glb`
in the owner's main checkout. SHA-256:
`7420903cc74d03838a196ac20028848738c5b898970f5aab9602c6151dc5cc18`.
The checked import contains 481,942 vertices, 892,194 triangles, one material
and one UV layer. Its largest connected component has only 5,500 vertices.
The 906 shells and open boundaries make direct decimation of that model a poor
starting point for skinning.

The geometry probe is in ignored
`data/converted/Unreal/Characters/Nali/geometry-probe-20261028/`:

- `Nali_deform_probe_ue5.glb` — 1,440,964 bytes, SHA-256
  `2e7a0f8b7850c8906dea54cb5c33caaf5ccb9c97a3bc3653530a98b44dc73e6f`.
- `Nali_deform_probe_ue5.json` — source/check hashes, Blender version,
  parameters, source and saved topology, bounds, limitations.
- Four `Nali_deform_probe_{front,right,back,left}_ue5.png` clay views.

This probe deliberately has **no UVs or PBR materials**. Voxel remeshing does
not transfer the source texture mapping reliably. The source GLB remains the
detail and PBR reference for later bake/transfer work. The probe has no
armature, skin weights, animation, cloth or physics. A closed shell with
80,000 triangles does not prove useful joint loops or deformation quality.

For owner review, the private
`data/converted/Unreal/Characters/Nali/review-scene-20261028/Nali_review_ue5.blend`
was opened in the installed Blender app. It displays the unchanged textured
source by default; the geometry probe is in the hidden collection
`02 Geometry probe (hidden)`. The `.blend` file is 74,977,298 bytes, SHA-256
`4f48673e4df6c18d8cdae059d11b1e7e0c595b9e800fb258e6ee4bcf4f65e37e`.
A fresh background reopen found the source mesh visible, probe hidden, front
camera saved, one material and three packed images. Rendering that reopened
scene showed the source textures correctly. This review scene is also ignored
by Git; it does not change the source GLBs or UE5 project.

The failed auto-weight test is in ignored
`data/converted/Unreal/Characters/Nali/weight-probe-20261028/`:
`Nali_auto_weight_pose_ue5.json` records group coverage and per-hand motion;
front and right PNGs show the stress pose. The test uses 26 temporary bones,
rotating the upper and lower shoulders by 0.6 and 0.5 radians in opposite
directions. Blender assigned at least one weight to every vertex. Weighted
hand centroids moved roughly 0.34 m for the upper pair and 0.20–0.21 m for
the lower pair. Coverage and motion establish that the test deform modifier
ran; the visible collapse is why it must not be adopted. No rig file was
exported or imported into UE5.

## Reproduce

Use installed Blender 5.2.3 or inspect any differences with a later version.
Both commands fail on an existing output directory and check their input
hashes. Provide the private source and new private destinations explicitly:

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background \
  --python tools/convert/nali_geometry_probe.py -- \
  --source data/converted/Unreal/Characters/Nali/meshy_output/20261028_224858_nali-reference-ue5_01a1847c/Nali_ue5.glb \
  --output-dir data/converted/Unreal/Characters/Nali/geometry-probe-20261028 \
  --voxel-size 0.008 --target-triangles 80000

/Applications/Blender.app/Contents/MacOS/Blender --background \
  --python tools/convert/nali_weight_probe.py -- \
  --source data/converted/Unreal/Characters/Nali/geometry-probe-20261028/Nali_deform_probe_ue5.glb \
  --output-dir data/converted/Unreal/Characters/Nali/weight-probe-20261028
```

Use new output directory names when rerunning; never overwrite the checked
assets. The commands above describe the recorded run, not a request to
regenerate existing private files. The Python suite is also required for
tracked Python changes (`bash scripts/run-tests.sh`); it does not exercise
Blender. The two Blender runs and saved readbacks provide the integration
evidence for these scripts.

## Next character checkpoint

Treat the 80k shell as a **shape guide**. Build a purpose-made deformation
topology around both shoulder pairs, elbows, wrists, hips, knees and fingers.
Separate the lower arms enough in the rest pose to allow independent motion,
then place a custom four-arm skeleton and paint weights. Validate extreme
poses and all four hand paths before transferring the high-detail surface and
PBR appearance. Use `Nali1.Walk`'s 20 source frames and footstep markers as
motion cues, not as directly retargetable skeletal animation. Check the result
in a safe UE5 test scene before touching the castle intro or its `Nali0` patrol.
