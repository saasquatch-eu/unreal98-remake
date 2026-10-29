"""Create a four-arm Nali1 skeleton template beside the checked visual guide.

This is an armature layout, not a skinned character or muscle simulation.
Run with Blender and put arguments after ``--``. Outputs are private.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

import bpy


SOURCE_SHA256 = "7420903cc74d03838a196ac20028848738c5b898970f5aab9602c6151dc5cc18"


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])


def add_bone(armature, name, head, tail, parent=None, deform=True):
    bone = armature.edit_bones.new(name)
    bone.head = head
    bone.tail = tail
    bone.use_deform = deform
    if parent:
        bone.parent = armature.edit_bones[parent]
    return bone


def build_arm(armature, side, sign, tier, shoulder, elbow, wrist, palm):
    prefix = f"arm_{tier}_{side}"
    clavicle = f"{prefix}_clavicle"
    upper = f"{prefix}_upper"
    forearm = f"{prefix}_forearm"
    hand = f"{prefix}_hand"
    anchor = (sign * .16, 0, shoulder[2] + .015)
    add_bone(armature, clavicle, anchor, shoulder, "spine_upper")
    add_bone(armature, upper, shoulder, elbow, clavicle)
    add_bone(armature, forearm, elbow, wrist, upper)
    add_bone(armature, hand, wrist, palm, forearm)

    def lerp(a, b, t):
        return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))

    add_bone(armature, f"{prefix}_upper_twist", lerp(shoulder, elbow, .35),
             lerp(shoulder, elbow, .8), upper)
    add_bone(armature, f"{prefix}_forearm_twist", lerp(elbow, wrist, .35),
             lerp(elbow, wrist, .8), forearm)
    # These two guides mark the future corrective-volume regions. They are
    # deliberately non-deforming: no untested Blender driver is exported.
    add_bone(armature, f"{prefix}_deltoid_guide", shoulder,
             (shoulder[0] + sign * .04, shoulder[1] - .035, shoulder[2] - .045),
             clavicle, deform=False)
    add_bone(armature, f"{prefix}_biceps_guide", lerp(shoulder, elbow, .25),
             lerp(shoulder, elbow, .7), upper, deform=False)

    digit_length = .085 if tier == "upper" else .068
    for digit, y_offset in enumerate((-.025, 0, .025), start=1):
        root = (palm[0] + sign * .006 * (digit - 2), palm[1] + y_offset,
                palm[2] - .007)
        previous = hand
        for joint in range(1, 4):
            start = (root[0], root[1], root[2] - digit_length * (joint - 1) / 3)
            end = (root[0] + sign * .003, root[1],
                   root[2] - digit_length * joint / 3)
            name = f"{prefix}_finger{digit}_{joint}"
            add_bone(armature, name, start, end, previous)
            previous = name
    thumb_start = (palm[0] - sign * .025, palm[1] - .035, palm[2] + .025)
    thumb_mid = (thumb_start[0] - sign * .026, thumb_start[1] - .01,
                 thumb_start[2] - .025)
    thumb_end = (thumb_mid[0] - sign * .012, thumb_mid[1] - .005,
                 thumb_mid[2] - .025)
    add_bone(armature, f"{prefix}_thumb_1", thumb_start, thumb_mid, hand)
    add_bone(armature, f"{prefix}_thumb_2", thumb_mid, thumb_end,
             f"{prefix}_thumb_1")


def main():
    args = arguments()
    source = args.source.resolve()
    destination = args.output_dir.resolve()
    if destination.exists() or destination == source or destination in source.parents:
        raise ValueError("output directory must be new and distinct from the source")
    digest = sha256(source.read_bytes()).hexdigest()
    if digest != SOURCE_SHA256:
        raise ValueError("Nali visual guide differs from checked source SHA-256")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    meshes = [item for item in bpy.context.scene.objects if item.type == "MESH"]
    if len(meshes) != 1 or len(meshes[0].data.vertices) != 481942:
        raise ValueError("unexpected Nali visual-guide mesh")
    guide = meshes[0]
    guide.name = "Nali1_visual_guide_ue5"
    guide.hide_render = True
    guide.hide_set(False)

    armature = bpy.data.armatures.new("Nali1_skeleton_ue5")
    rig = bpy.data.objects.new("Nali1_skeleton_ue5", armature)
    bpy.context.scene.collection.objects.link(rig)
    rig.show_in_front = True
    armature.display_type = "STICK"
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")

    add_bone(armature, "root", (0, 0, -.25), (0, 0, -.20), deform=False)
    add_bone(armature, "pelvis", (0, 0, -.20), (0, 0, .02), "root")
    add_bone(armature, "spine_lower", (0, 0, .02), (0, 0, .32), "pelvis")
    add_bone(armature, "spine_upper", (0, 0, .32), (0, 0, .57), "spine_lower")
    add_bone(armature, "neck", (0, 0, .57), (0, 0, .76), "spine_upper")
    add_bone(armature, "head", (0, 0, .76), (0, 0, .92), "neck")
    add_bone(armature, "jaw_guide", (0, -.065, .76), (0, -.11, .72),
             "head", deform=False)
    for side, sign in (("L", -1), ("R", 1)):
        hip = (sign * .16, 0, -.16)
        knee = (sign * .18, 0, -.52)
        ankle = (sign * .18, 0, -.82)
        ball = (sign * .18, -.12, -.91)
        toe = (sign * .18, -.22, -.92)
        add_bone(armature, f"leg_{side}_thigh", hip, knee, "pelvis")
        add_bone(armature, f"leg_{side}_shin", knee, ankle, f"leg_{side}_thigh")
        add_bone(armature, f"leg_{side}_foot", ankle, ball, f"leg_{side}_shin")
        add_bone(armature, f"leg_{side}_toe", ball, toe, f"leg_{side}_foot")
        build_arm(armature, side, sign, "upper", (sign * .29, 0, .56),
                  (sign * .42, 0, .29), (sign * .50, 0, -.01),
                  (sign * .53, 0, -.12))
        build_arm(armature, side, sign, "lower", (sign * .24, 0, .32),
                  (sign * .32, 0, .07), (sign * .39, 0, -.15),
                  (sign * .42, 0, -.22))
    bpy.ops.object.mode_set(mode="OBJECT")

    expected = 91
    if len(armature.bones) != expected:
        raise ValueError(f"expected {expected} bones, found {len(armature.bones)}")
    if len(set(bone.name for bone in armature.bones)) != expected:
        raise ValueError("duplicate bone name")
    hands = [f"arm_{tier}_{side}_hand" for side in ("L", "R")
             for tier in ("upper", "lower")]
    bpy.context.view_layer.update()
    rest_hands = {name: rig.pose.bones[name].tail.copy() for name in hands}
    test_clavicle = rig.pose.bones["arm_lower_L_clavicle"]
    test_clavicle.rotation_mode = "XYZ"
    test_clavicle.rotation_euler.z = .45
    bpy.context.view_layer.update()
    test_motion = {name: (rig.pose.bones[name].tail - rest_hands[name]).length
                   for name in hands}
    if test_motion["arm_lower_L_hand"] < .05 or any(
        distance > 1e-5 for name, distance in test_motion.items()
        if name != "arm_lower_L_hand"
    ):
        raise ValueError(f"four arm chains are not independent: {test_motion}")
    test_clavicle.rotation_euler.z = 0
    bpy.context.view_layer.update()
    destination.mkdir(parents=True, exist_ok=False)
    scene_file = destination / "Nali1_skeleton_ue5.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(scene_file))
    report = {
        "schema": "nali1-skeleton-template-v1",
        "source_glb": str(source),
        "source_sha256": digest,
        "blender_version": bpy.app.version_string,
        "skeleton_bones": expected,
        "four_arm_chains": [f"arm_{tier}_{side}" for side in ("L", "R")
                            for tier in ("upper", "lower")],
        "guide_visible_on_open": True,
        "guide_skinned": False,
        "animation_present": False,
        "muscle_simulation_present": False,
        "independence_test_hand_motion_m": test_motion,
        "bone_manifest": [{"name": bone.name,
                           "parent": bone.parent.name if bone.parent else None,
                           "deform": bone.use_deform,
                           "head": list(bone.head_local),
                           "tail": list(bone.tail_local)} for bone in armature.bones],
        "scene_sha256": sha256(scene_file.read_bytes()).hexdigest(),
    }
    (destination / "Nali1_skeleton_ue5.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"scene": str(scene_file), "bones": expected,
                      "sha256": report["scene_sha256"]}), flush=True)


if __name__ == "__main__":
    main()
