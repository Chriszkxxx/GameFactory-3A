const assert = require("node:assert/strict");

const policy = require("./viewer_engine_policy.js");

assert.equal(policy.usesNativeIframeInput("godot"), true);
assert.equal(policy.usesNativeIframeInput("unity3d"), true);
assert.equal(policy.usesNativeIframeInput("ue5"), false);
assert.equal(policy.acceptsAvatar("godot", "PackedScene", false), true);
assert.equal(policy.acceptsAvatar("godot", "SkeletalMesh", true), false);
assert.equal(policy.acceptsMotion("godot", "AnimationLibrary"), true);
assert.equal(policy.acceptsMotion("godot", "PackedScene"), true);
assert.equal(policy.acceptsMotion("godot", "AnimSequence"), false);
assert.equal(policy.requiresSkeletonMatch("godot"), true);
assert.equal(policy.acceptsAvatar("ue5", "SkeletalMesh", false), false);
assert.equal(policy.acceptsAvatar("ue5", "SkeletalMesh", true), true);

const godotAvatar = {
  artifact_id: "godot_avatar_hero",
  native: { class: "PackedScene", path: "res://assets/imported/avatars/hero.glb" },
  metadata: {
    skeleton: "Character/Skeleton3D",
    skeleton_path: "Character/Skeleton3D",
  },
};
const godotMotion = {
  artifact_id: "godot_motion_walk",
  native: { class: "PackedScene", path: "res://assets/imported/motions/walk.glb" },
  metadata: {
    skeleton: "Character/Skeleton3D",
    skeleton_path: "Character/Skeleton3D",
  },
};
const legacyGodotMotion = {
  artifact_id: "godot_motion_idle",
  native: { class: "PackedScene", path: "res://assets/imported/motions/idle.glb" },
  metadata: { skeleton: "Character/Skeleton3D" },
};
const mismatchedGodotMotion = {
  artifact_id: "godot_motion_other",
  native: { class: "PackedScene", path: "res://assets/imported/motions/other.glb" },
  metadata: { skeleton_path: "Other/Skeleton3D" },
};
assert.equal(policy.assetSkeletonPath(godotAvatar), "Character/Skeleton3D");
assert.deepEqual(
  policy.filterMotionsForAvatar(
    "godot",
    godotAvatar,
    [godotMotion, legacyGodotMotion, mismatchedGodotMotion]
  ).map((asset) => asset.artifact_id),
  ["godot_motion_walk", "godot_motion_idle"]
);

console.log("Browser Player engine policy checks passed");
