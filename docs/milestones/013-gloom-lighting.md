# Castle intro: darker overcast lighting

Completed locally on 2026-10-28 in UnrealGoldRemake / UE 5.8.4. The golden
sunset wash is replaced with darker overcast illumination. Stonework remains
readable, with deeper shadows and more prominent warm flames. Software Lumen,
Nanite, Virtual Shadow Maps and the animated flame/water previews remain active.

## Source evidence and limits

The checked original map/export still supplies the 27 steady world lights,
including blue, violet and cyan colors. Those colors have not been changed.
LevelInfo3 explicitly enables bFogZone. Omitted ambient properties have not been
decoded from class defaults and must not be interpreted as zero ambient light.

Private inspection of the map's GenFluid.Sky.NghSky3 and GenFluid.Sky.Ntskyt
images shows black starfields; GenFluid.cloud1a contains dark gray/green clouds.
The previous bright blue sky and strong golden sunset were authored UE5 choices.
This correction reduces their influence. It does not yet import the original
sky miniatures, moons, scrolling textures or lightning. Modern height/volumetric
fog is not a reconstruction of UE1 zone fog.

No matching original-game camera frame was available for this pass. The result
is a source-informed artistic correction, not a verified original-frame match.
The overcast sky remains brighter than the original starfield; original sky
reconstruction and running-original comparison remain the next checkpoint.

## Authored preset

`tools/presets/Unreal_Gloom_ue5.json` records the final settings separately from
the immutable private lighting recipe:

| Setting | Previous | Current |
| --- | --- | --- |
| Directional light | 1,000 lux | 500 lux |
| Pitch / yaw / roll | -12 / 125 / 0 degrees | -35 / 125 / 0 degrees |
| Source angle / soft angle | 2 / 5 degrees | 8 / 20 degrees |
| Sky intensity | 1 | 0.6 |
| Cloud coverage / density | -0.2 / 0.008 | 0.25 / 0.012 |
| Cloud bottom / height | 3 / 5 km | 1.5 / 8 km |
| Cloud shadow strength | unchanged prior default | 0.9 |
| Manual exposure compensation | -6 EV | -5.5 EV |
| Fog density / start | 0.000015 / 1,500 cm | 0.0015 / 1,000 cm |
| Fog height falloff | 0.2 | 0.2 |
| Mie scattering scale | about 0.003996 | 0.01 |
| Seven shadowed point lights | recipe intensity | recipe intensity |
| Twenty non-shadowing fills | recipe intensity | 60% of recipe intensity |

The exposure compensation rises half a stop to retain stone detail under the
weaker, cloud-filtered outdoor illumination. This is an overcast lighting rig;
it is not physically calibrated moonlight. Sun and sky colors remain neutral,
without temperature tint. The sky atmosphere's sunset direction was corrected
before adjusting sky fill. No white-balance color cast was added.

The first dark-cloud trial hid too much stone detail. One refinement restored
diffuse illumination; both fixed gate and moat views were inspected afterward.
There were two lighting-result cycles. Capture poses use a diagnostic 75-degree
FOV; they do not establish the original game's FOV or timing.

## Reproduce and recover

Finish the water checkpoint first. Save work, stop PIE and use the editor's
Python console with the actual absolute repository path:

```python
import runpy
runpy.run_path('/absolute/repo/tools/editor/apply_intro_mood.py', run_name='__main__')
runpy.run_path('/absolute/repo/tools/editor/verify_intro_mood.py', run_name='__main__')
```

The apply command requires the preceding water/lighting baseline. It checks the
complete saved scene, saves the level and project cloud material, then copies
both into a unique ignored `.local/gloom-recovery/<timestamp>/` directory before
editing. The frozen applied preset and pre-edit point-light colors/intensities
are also retained there. Only the project cloud material instance is edited;
engine assets and application bundles are not modified.

For a later refinement, call the script's `apply(profile_path,
previous_profile=...)` function with the **frozen applied-profile.json from the
last successful apply report**, rather than rerunning the initial command.
The report is `.local/logs/unreal-mood-apply.json`. The prior profile is verified
before mutation, and intensities are computed from the original recipe, avoiding
cumulative dimming. Inspect/recover an interrupted application before retrying.
For rollback, close the project before restoring both backed-up files, then
verify against the corresponding preceding profile/stage.

Use `verify_intro_mood.py` for this combined stage. Earlier verifiers intentionally
retain their original defaults. The mood verifier supplies an explicit validated
profile through the water/flame/Lumen chain; no geometry or material-binding
checks are disabled. It reloads the saved map, checks every authored atmosphere
setting and original point-light color within existing 8-bit quantization, and
runs the existing animation GPU checks. Apply also checks exact point-light RGBA
values before/after editing.

## Executed validation

- 196 existing Python tests passed; editor scripts parse successfully.
- Saved-map readback preserves all 7,135 world and 116 Mover triangles, positions,
  winding, UVs, source materials, Nanite fallbacks and explicit effect bindings.
- All three animated materials retain 64 distinct, nonblank GPU frames each.
  Saved water diagnostic emission remains zero.
- Original map/export and checked source/buffer/atlas hashes remain unchanged.
- Native gate and moat captures confirm darker architecture and readable flames.
  These images and all generated assets/reports remain private and ignored.

No new application, external asset provider, C++ build or measured frame-rate
claim is part of this pass. Collision, flyby playback, audio and the later modern
material/art pass remain separate work.
