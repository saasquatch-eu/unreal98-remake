# Nali1 four-arm deformation blockout

Prepared on 2026-10-29 after merged PR #22. This checkpoint tests whether the
custom 91-bone skeleton can drive four separate arm chains in a saved,
engine-readable GLB. The simple mannequin is a **motion and export test**. It
is not the final Nali appearance, a continuous anatomical deformation mesh,
muscle simulation, source-matched animation or a UE5 character.

## Acceptance criteria and result

- Leave the checked visual model and skeleton template unchanged: **met**.
  The input `Nali1_skeleton_ue5.blend` retained SHA-256
  `42114b492e06f4e318c6c39b6f4f93d8bc1dc4fa489d43efd4565484c41f87f9`.
  New outputs use a separate ignored directory; the script refuses overwrite.
- Recheck whether the textured decimation can be salvaged by changing only
  weight smoothing: **failed visually**. A zero-smoothing stress pose made
  the shoulder tearing and stretched strips worse. Its private images are in
  `textured-weight-probe4-20261029/`; do not import that model as a rig.
- Make a low-detail skinned blockout around the template: **met for testing**.
  It has 25 independently modeled body/limb/finger parts, 2,378 Blender
  vertices and 4,656 triangles. Every part has weights and UV0. These
  deliberately separate pieces avoid treating the Meshy model's arbitrary
  disconnected islands as controlled joint topology.
- Verify independent four-arm deformation: **met mechanically**. In the
  saved stress pose, the upper hand centroids moved 0.4633 m each and the
  lower hand centroids 0.2998 m each. Front and oblique renders were visually
  inspected. The shoulder attachment, torso overlaps, hands and feet are
  visibly crude; the visual quality criterion for a reusable character is
  **not met**.
- Verify persisted scene and GLB, not only Blender memory: **met**. Reopening
  the `.blend` found 91 bones, 25 weighted parts, UV0 on every part and the
  high-detail guide hidden. The GLB contains one skin with all 91 joints,
  25 primitives, 4,656 triangles and `JOINTS_0`, `WEIGHTS_0`, `TEXCOORD_0`
  on every primitive. Every exported mesh name ends `_ue5`.
- Add a viewable motion loop: **met for an authored preview** in the follow-on
  below. Source-matched walking, corrective muscle behavior, physics and
  castle patrol remain **pending**. No UE5 import or Play test was performed.

## Private outputs and provenance

The selected output is ignored at
`data/converted/Unreal/Characters/Nali/deform-blockout-20261029-v6/` in the
owner's main checkout:

- `Nali1_blockout_ue5.blend` — SHA-256
  `cc1ded75bf7c7d17bda59d015cc40bda585e20379eb03eec2382903acdfc94da`.
  It retains the checked high-detail visual model **hidden as a guide**.
- `Nali1_blockout_ue5.glb` — SHA-256
  `9241cb7059eebf37a95cff0f7dc26760421c6976a4e630f77c21470d71cc1c4a`.
  This export contains only the independently authored blockout and skeleton,
  with one plain material and no original visual mesh or textures.
- `Nali1_blockout_ue5.json` — source hash, saved hashes, geometry counts,
  four hand motion distances and preview paths.
- `Nali1_blockout_{rest,stress,stress_oblique}_ue5.png` — visual diagnostics.

The Game Development Studio asset inspector independently read the final
GLB as 25 meshes, 4,656 triangles, with UVs and a skin. It reports the
expected plain-material warning. Its vertex count can exceed Blender's
because glTF splits vertices at UV seams; triangle count and skin structure
are the relevant saved checks here. This is a synthetic test artifact, not
an attempt to replace the 1998 `Nali1` geometry or textures.

## Reproduce

Use the installed Blender 5.2.3 and a **new** ignored output directory:

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background \
  --python tools/convert/nali_deform_blockout.py -- \
  --skeleton data/converted/Unreal/Characters/Nali/skeleton-template-20261029-v3/Nali1_skeleton_ue5.blend \
  --output-dir data/converted/Unreal/Characters/Nali/deform-blockout-NEW
```

The script rejects a mismatched skeleton hash, an existing destination,
unweighted vertices and immobile hands. The final private run succeeded;
saved `.blend` and `.glb` were separately inspected. The full repository
Python suite passed **285 tests** with Python 3.12.14 and `PYTHONPATH=tools/src`.
No software installation or paid-provider credits were needed.

## Viewable walk preview follow-on

The first walk preview is saved privately at
`data/converted/Unreal/Characters/Nali/walk-preview-20261029-v3/`:

- `Nali1_WalkPreview_ue5.gif` — looping 20-frame visual preview, SHA-256
  `a0506d5de496f41e9db3345be28c0971a13a23664d19d342308c5435f1ff9b2e`.
  ImageIO stores approximately 0.07 seconds per frame, so the GIF runs
  slightly slower than the Blender action's exact 15 fps.
- `Nali1_WalkPreview_ue5.blend` — editable Blender action, SHA-256
  `39c76cf3e79a74794d10648fb37c8728dac106887214bf7d36895c5e8305e880`.
  Reopening it found action `Nali1_WalkPreview_ue5`, frames 0–20, 15 fps and
  the same 91 bones. Select the armature and press Play in Blender's timeline.
- `Nali1_WalkPreview_ue5.glb` — skinned animated export, SHA-256
  `c87858aa7886efa02a7de683c83fb42998ca8b9e46838b5c986b5b508ed72508`.
  Saved GLB readback found one animation with 273 channels, one 91-joint skin,
  25 meshes and a duration of 1.333333 seconds.
- Twenty numbered PNG frames and `Nali1_WalkPreview_ue5.json` preserve the
  rendered sequence, source hash and frame hashes. Frames 0, 5, 10 and 15
  were visually inspected from an oblique camera angle.

The clip is **in place** and uses authored sinusoidal joint angles. It takes
only the original `Walk` sequence's 20-frame/15-fps nominal timing and the
independent lower-arm motion as cues. It does not reconstruct the original
293-vertex poses, patrol movement, contact physics, muscles or sound.
Blender on this Mac has no FFmpeg output option, so the PNGs were assembled
with the installed macOS Swift/ImageIO tool. ImageIO readback confirmed all
20 GIF frames and their 0.07-second delays. No installation or provider
credits were needed.

To regenerate, run the tracked Blender script using a new private directory,
then run the tracked Swift encoder on that directory:

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background \
  --python tools/convert/nali_walk_preview.py -- \
  --source data/converted/Unreal/Characters/Nali/deform-blockout-20261029-v6/Nali1_blockout_ue5.blend \
  --output-dir data/converted/Unreal/Characters/Nali/walk-preview-NEW
/usr/bin/swift tools/convert/nali_frames_to_gif.swift \
  data/converted/Unreal/Characters/Nali/walk-preview-NEW
```

## Next character checkpoint

The blockout proves the bone hierarchy and GLB skin path, while the renders
show that the attachment surfaces are not acceptable. Build continuous,
purpose-made shoulder and torso topology around both arm pairs; refine
elbows, wrists, hands, pelvis and feet. Paint weights and add corrective
volume shapes or bones for deltoids, chest, biceps, forearms and legs. Test
the actual detailed character under extreme poses, then drive a walk from
the checked 20-frame `Nali1.Walk` reference. Validate the resulting skeletal
asset and motion in a separate UE5 test level before placing `Nali0` on the
source patrol route in the castle.
