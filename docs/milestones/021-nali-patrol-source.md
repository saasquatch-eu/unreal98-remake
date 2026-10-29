# Castle Nali patrol source checkpoint

Prepared on 2026-10-29 after merged PR #20. This checkpoint resolves the
castle `Nali0` patrol links from the owner's checked original export and
package. It creates a private UE5 preparation plan, not a live actor or a
finished walk animation.

## Acceptance criteria and result

- Admit the original map and T3D only when both hashes match the previously
  checked intro plan: **met**. No source file was modified.
- Preserve all four `PatrolPoint` records in source actor order and resolve
  the route by case-insensitive tags, not actor names: **met**. The script
  rejects duplicate tags, broken links and an incomplete loop.
- Preserve Nali start, original tag spelling, locations, optional pause and
  animation properties, and source actor indices: **met**.
- Keep the output private and refuse overwrite: **met**. The output is under
  ignored `data/converted/Unreal/Maps/Unreal/nali-patrol-20261029/`.
- Exercise route resolution and provenance checks with synthetic fixtures:
  **met**. The full Python suite passed, 285 tests.
- Place a walking modern Nali in the UE5 castle: **pending**. The Meshy
  visual prototype is still unrigged and its automatic-weight test failed.

## Source facts

The checked T3D SHA-256 is
`d7b86d1698991d69528f1c6e4238eea961be9d6a63dabccbe31cb6f02abbfb52`;
the corresponding installed `Unreal.unr` SHA-256 is
`a38aa510821fa7e6e17fc5f7dab882dba2452141770ef3f7c9a2c83e9d3ad4f4`.
The private plan also records the intro-plan hash. The source Nali is actor
index 236, `Nali0`, at `(1430.98, 1247.14, 5424.1)`, with
`Orders="Patroling"`, `OrderTag="P1"` and
`AttitudeToPlayer=ATTITUDE_Ignore`.

| Route order | Source actor index | Source name | Tag | Nextpatrol | Location | PauseTime | PatrolAnim |
| --- | ---: | --- | --- | --- | --- | ---: | --- |
| 1 | 350 | PatrolPoint3 | P1 | P2 | (885.02, 535.53, 5428.98) | 1.0 | Cough |
| 2 | 197 | PatrolPoint1 | P2 | p3 | (829.131, 1313.32, 5428.98) | 1.0 | Cough |
| 3 | 196 | PatrolPoint0 | p3 | p4 | (1904.71, 1167.2, 5428.93) | omitted | Breath |
| 4 | 348 | PatrolPoint2 | p4 | P1 | (2045.94, 438.415, 5428.93) | omitted | omitted |

The prior checked `Nali1` package report contains `Walk` (20 frames at
15 frames/s), `Cough` (25 frames at 15 frames/s) and `Breath` (8 frames at
6 frames/s). These are source animation descriptors, not UE5 animation assets.

The [public OldUnreal 227 `ScriptedPawn` source](https://github.com/OldUnreal/Unreal-PubSrc/blob/main/UnrealShare/Classes/ScriptedPawn.uc)
shows how `OrderTag` selects a patrol point and `Nextpatrol` selects the next
tag. On arrival, it plays a valid `PatrolAnim` for `numAnims` iterations; its
`PauseTime` sleep is in the other branch. This later public source is useful
behavioral evidence, but it is **not** a verified dump of this installed 1998
runtime. Do not hard-code a one-second stop at both Cough points solely from
the T3D values.

## Reproduce

Use the repository's Python 3.12+ environment and a new ignored destination:

```sh
PYTHONPATH=tools/src python -m ue1_converter.nali_patrol \
  data/converted/Unreal/Maps/Unreal/intro-ready/Unreal.intro.json \
  --output-dir data/converted/Unreal/Maps/Unreal/nali-patrol-20261029
```

The recorded output is `Nali0_patrol_ue5.json`. For another run, choose a new
directory. The preparation script never writes to the UE5 project.

## Next implementation checkpoint

The private modern Nali model remains an unrigged visual reference. Build and
visually verify a four-arm deformation mesh, rig and walk cycle against
`Nali1.Walk` before claiming realistic movement. In a separate UE5 test scene,
check the character's scale, all four arms and foot contact. Then add the
patrol to the castle, with the source positions, turns and arrival animations.
The castle currently has no validated walking collision or navigation mesh;
either prepare those or explicitly mark any Sequencer-driven route as a
cinematic preview. Verify saved assets after reload and observe actual Play
behavior before claiming that the Nali wanders in the intro.
