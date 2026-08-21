(function exposeViewerEnginePolicy(root, factory) {
  const policy = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = policy;
  }
  root.A3GameViewerEnginePolicy = policy;
}(typeof globalThis === "object" ? globalThis : this, () => {
  const nativeCanvasEngines = new Set(["unity3d", "godot"]);
  const avatarClasses = {
    ue5: new Set(["SkeletalMesh"]),
    unity3d: new Set(["GameObject", "Prefab", "SkeletalMesh"]),
    godot: new Set(["PackedScene"]),
  };
  const motionClasses = {
    ue5: new Set(["AnimSequence"]),
    unity3d: new Set(["AnimationClip"]),
    godot: new Set(["PackedScene", "AnimationLibrary", "Animation"]),
  };

  function usesNativeIframeInput(engineId) {
    return nativeCanvasEngines.has(String(engineId || "").toLowerCase());
  }

  function acceptsAvatar(engineId, className, hasSkeleton, technicalName = false) {
    const normalizedEngine = String(engineId || "").toLowerCase();
    const accepted = avatarClasses[normalizedEngine] || avatarClasses.ue5;
    if (!accepted.has(String(className || "")) || technicalName) {
      return false;
    }
    return normalizedEngine !== "ue5" || Boolean(hasSkeleton);
  }

  function acceptsMotion(engineId, className) {
    const normalizedEngine = String(engineId || "").toLowerCase();
    const accepted = motionClasses[normalizedEngine] || motionClasses.ue5;
    return accepted.has(String(className || ""));
  }

  function requiresSkeletonMatch(engineId) {
    return Boolean(String(engineId || "").toLowerCase());
  }

  function assetSkeletonPath(asset) {
    const metadata = asset?.metadata || {};
    if (metadata.skeleton_path || metadata.skeleton) {
      return String(metadata.skeleton_path || metadata.skeleton);
    }
    const dependency = (metadata.dependencies || []).find(
      (item) => item?.type === "skeleton"
    );
    return String(dependency?.assets?.[0] || "");
  }

  function normalizeSkeletonPath(path) {
    return String(path || "").split(".", 1)[0].trim();
  }

  function filterMotionsForAvatar(engineId, avatar, motions) {
    const candidates = Array.isArray(motions) ? motions : [];
    if (!avatar) {
      return [];
    }
    const skeletonPath = normalizeSkeletonPath(assetSkeletonPath(avatar));
    if (!requiresSkeletonMatch(engineId)) {
      return skeletonPath
        ? candidates.filter((motion) => {
          const motionSkeleton = normalizeSkeletonPath(assetSkeletonPath(motion));
          return !motionSkeleton || motionSkeleton === skeletonPath;
        })
        : candidates;
    }
    if (!skeletonPath) {
      return [];
    }
    return candidates.filter(
      (motion) => normalizeSkeletonPath(assetSkeletonPath(motion)) === skeletonPath
    );
  }

  return {
    acceptsAvatar,
    acceptsMotion,
    assetSkeletonPath,
    filterMotionsForAvatar,
    requiresSkeletonMatch,
    usesNativeIframeInput,
  };
}));
