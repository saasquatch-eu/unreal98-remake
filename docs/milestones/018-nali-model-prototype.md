# Nali visual model prototype

Prepared privately on 2026-10-28. This checkpoint supplies a **textured,
four-armed visual prototype** for the castle intro's `Nali0`. It does not add
an actor or asset to UnrealGoldRemake. It has no skeleton, animation, muscle
deformation, collision, patrol behavior or UE5 import validation.

## Source and generation

The owner supplied a concept image showing a full-body four-armed alien and a
face close-up. A single-character front reference was made from that image
with the built-in image-generation editor. The original installed-game
`UnrealI.Skins.JNali1` texture was decoded read-only for comparison. Both
images remain under ignored `data/converted/Unreal/Characters/Nali/`.

The first Meshy text-to-3D preview (task
`01a18472-fde3-7137-b49a-92445a71c171`) produced a two-armed human figure.
It was rejected before texturing or import; Meshy reported 20 credits consumed.

After the owner approved one additional 30-credit run, Meshy image-to-3D task
`01a1847c-9bd9-76b8-bb37-6b502a38faff` used the clean reference with
standard geometry, 4K PBR texturing, automatic pose and image enhancement off.
The task succeeded and reported **30 credits consumed**. Its local GLB and
preview are in ignored
`data/converted/Unreal/Characters/Nali/meshy_output/20261028_224858_nali-reference-ue5_01a1847c/`:

- `Nali_ue5.glb` — 56,172,420 bytes; SHA-256
  `7420903cc74d03838a196ac20028848738c5b898970f5aab9602c6151dc5cc18`.
- `preview.png` — inspected front render, with four visible arms and a look
  close to the owner's concept.
- `task_01a1847c-9bd9-76b8-bb37-6b502a38faff.json` and `metadata.json` —
  Meshy task receipt and recovery details. Signed download URLs in the receipt
  expire; recover from the task ID, not a copied URL.

This content is private and Git-ignored. Do not copy the concept, original
skin, GLB, texture bytes, or generated preview into Git.

## Checks and limitations

The downloaded file is a valid glTF 2.0 binary container. Its JSON describes
one mesh, one material, three embedded image/texture references, no skins,
481,942 position vertices and **892,194 triangles**. Headless Blender 5.2.3
loaded the mesh and measured dimensions about 1.182 × 0.468 × 1.902 m.
It found **69,880 boundary/nonmanifold edges**. These are topology findings,
not proof of a particular defect; inspect the seams and deformation areas
before attempting rigging. The front thumbnail establishes appearance only;
back, side, texture seams, topology and real-time performance still need
visual and engine checks.

The installed Game Asset Production skill's `game-dev` CLI was not present, so
its packaging/validation workflow was not run. Blender was used only for a
read-only import and topology query; no mesh normalization or rigging occurred.
The original `UnrealI.u` contains `Nali2` as a LodMesh, but that is the
playable `NaliPlayer` mesh. The castle `Nali0` uses `Nali1` from
`UnrealShare.u`; its `Walk` frames are documented in milestone 019. No Meshy auto-rig,
animation, remesh or additional paid task has been submitted.

## Continue from here

1. Inspect the GLB from multiple angles and check whether all four arms have
   separate, plausible shoulder geometry. Compare it with the original Nali
   model and the owner's concept before choosing a topology cleanup method.
2. Create a lower-density deformation mesh and preserve the detailed sculpt
   and PBR maps. Set explicit triangle/texture budgets based on close-up and
   castle flyby uses. Keep all revisions as new private files; retain the
   downloaded original and its SHA as the source of truth.
3. Build a **custom four-arm skeleton**, skin weights and corrective deformation.
   Study the original Nali animations, then reproduce the characteristic walk
   and upper/lower arm timing before adding secondary cloth/body motion.
4. Import into a safe UE5 test scene, inspect materials and animation under
   the existing gloomy lighting, then integrate `Nali0` and its verified
   patrol links into the intro map. Use the normal editor backup/readback flow.

Meshy's standard humanoid rig is for two arms; its API is intended for standard
bipeds. Do not spend credits on automatic rigging or animation for this model
without a specific suitability check and new authorization. The owner's
30-credit approval covered the image-to-3D model only.
