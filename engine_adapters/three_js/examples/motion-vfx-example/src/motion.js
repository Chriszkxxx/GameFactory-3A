/**
 * Reference: how a generated game gets motion onto a character.
 *
 * This file exists because the first version of the four generated games
 * all made the same mistake, and it is not an obvious one. They did this:
 *
 * ```js
 * const loaded = await assets.tryInstantiate(['hero', 'robot_expressive']);
 * if (loaded) entity.setVisual(loaded.object, loaded.animations);
 * ```
 *
 * which is correct for a *downloaded* character and silently wrong for a
 * *generated* one. Image-to-3D produces one fused body: the manifest entry
 * reports `animations: []` and `skinned: false`. So `loaded.animations` is
 * empty, no animation director is built, and — because swapping the visual
 * throws away the procedural limbs the entity had been posing — the game
 * ends up with a good-looking character that never moves at all. That is
 * strictly worse than the capsule it replaced.
 *
 * There are exactly three ways a character can move on the web, and
 * `createAnimatedActor` tries them in this order:
 *
 *   1. **the model's own clips** — a downloaded CC0 character, or a
 *      generated one re-exported by `pipeline/assets_gen/gen_motion`;
 *   2. **imported motion, retargeted by bone name** — clips staged as
 *      `type: 'motion'` artifacts by `three.assets.import_motion`;
 *   3. **an auto-fitted skeleton driven by authored clips** — the case
 *      that actually applies to TRELLIS.2 output today.
 *
 * And there is a fourth answer, `motionSource: 'none'`, which a game must
 * honour by keeping the body it already had.
 */

import {
  A3GameAnimationDirector,
  A3GameMotionLibrary,
  autoRigHumanoid,
  createAnimatedActor,
  createHumanoidClipSet,
  measureHumanoid,
  retargetClipToSkeleton,
} from '@a3game/playable';

/**
 * The states a game maps, as a preference list per state.
 *
 * A list, not a name. The authored clip set calls the shooting stance
 * `aim`; the CC0 `robot_expressive` avatar has fourteen clips and none of
 * them is called that. Binding a single name means one of the two sources
 * silently plays nothing, and "nothing" for an attack state is a character
 * standing at attention while it kills you.
 */
export const REFERENCE_CLIP_CHAINS = Object.freeze({
  idle: ['idle', 'Idle', 'Standing'],
  walk: ['walk', 'Walking'],
  run: ['run', 'Running', 'walk', 'Walking'],
  jump: ['jump', 'Jump'],
  attack: ['punch', 'Punch'],
  heavy_attack: ['kick', 'Punch'],
  hit: ['hit', 'No'],
  death: ['death', 'Death'],
});

/**
 * The correct shape of "upgrade this entity to imported art".
 *
 * Two things make it different from a bare `tryInstantiate`:
 *
 * - candidates are tried **one at a time**, because "staged" and
 *   "animatable" are different questions and only the second one decides
 *   whether the swap is an improvement;
 * - `ground: true`, because a generated mesh's origin is wherever the
 *   reconstruction left it, and a character placed by its origin stands
 *   with its shins in the floor.
 *
 * @param {object} assets an `A3GameAssetLibrary`
 * @param {object} entity anything with `setVisual(object, clips, options)`
 * @param {string[]} candidates asset ids, best first
 * @param {{height: number, states?: string[]}} options
 * @returns {Promise<{applied: boolean, assetId: string,
 *                    motionSource: string, rejected: string[]}>}
 */
export async function dressCharacter(assets, entity, candidates, options) {
  const rejected = [];
  for (const candidate of candidates) {
    if (!assets.has(candidate)) continue;
    const actor = await createAnimatedActor(assets, candidate, {
      height: options.height,
      ground: true,
      envMapIntensity: 1,
      states: options.states,
      defaultState: 'idle',
    });
    if (!actor) continue;
    if (actor.motionSource === 'none') {
      // Refused, with a reason: usually a mesh whose proportions are not a
      // standing figure, which is what a reconstruction that invented a
      // ground plane looks like. Keep the procedural body — it moves.
      rejected.push(`${candidate}: ${actor.warnings[0] ?? 'no motion'}`);
      continue;
    }
    entity.setVisual(actor.object, actor.animations, {
      animator: actor.animator,
      motionSource: actor.motionSource,
    });
    return {
      applied: true,
      assetId: candidate,
      motionSource: actor.motionSource,
      rejected,
    };
  }
  return { applied: false, assetId: '', motionSource: 'procedural', rejected };
}

/**
 * The same thing spelled out, for a game that needs to intervene.
 *
 * `createAnimatedActor` is the whole sequence in one call; this is what it
 * does, in case a game has to change one step — a non-humanoid creature
 * that needs its own clip set, a character whose motion artifacts are
 * named per state, a rig that needs a wider shoulder line.
 *
 * @param {object} assets
 * @param {string | string[]} reference
 * @param {{height: number, states?: string[],
 *          motionReferences?: string[]}} options
 * @returns {Promise<object | null>}
 */
export async function resolveMotionByHand(assets, reference, options) {
  const loaded = await assets.tryInstantiate(reference, {
    height: options.height,
    ground: true,
    frustumCulled: false,
  });
  if (!loaded) return null;

  // 1. The model's own clips, if the file carried any.
  let clips = (loaded.animations ?? []).filter((clip) => clip.tracks.length);
  let motionSource = clips.length > 0 ? 'clips' : 'none';

  // 2. Motion artifacts staged separately, retargeted by bone name. The
  //    name half of retargeting is all a browser can do; reconciling rest
  //    poses belongs to `operators/gen_motion`, which has the source
  //    skeleton's bind pose and this does not.
  if (clips.length === 0) {
    const motion = new A3GameMotionLibrary({ assets });
    if (motion.available) {
      const imported = await motion.loadForCharacter(loaded.object, {
        references: options.motionReferences,
        states: options.states,
      });
      if (imported.clips.length > 0) {
        clips = imported.clips;
        motionSource = 'imported_motion';
      }
    }
    // A single clip from elsewhere, mapped by hand, looks like this:
    // const { clip } = retargetClipToSkeleton(sourceClip, loaded.object,
    //   { boneMap: { 'Bip01_Pelvis': 'hips' } });
    void retargetClipToSkeleton;
  }

  // 3. Fit a skeleton to the mesh and drive it with authored clips — but
  //    only if the mesh is a standing figure. Rigging a slab produces a
  //    writhing lump, and a game is better off with its capsule.
  if (clips.length === 0) {
    // The gate reads world-space proportions, which is safe because a
    // ratio is scale-invariant. The rig measures the subtree's own local
    // space, because that is where the geometry it binds will live — the
    // asset library's wrapper carries both a fit-to-height scale and a
    // grounding offset, and a skeleton fitted to world measurements would
    // be off by exactly those.
    const measurement = measureHumanoid(loaded.object);
    if (!measurement.humanoid) {
      return { ...loaded, animations: [], animator: null, motionSource: 'none' };
    }
    const rig = autoRigHumanoid(loaded.object);
    if (rig) {
      clips = createHumanoidClipSet(options.states, {
        height: rig.height,
        // The rig's hips carry the model's horizontal centre and its ground
        // offset; a clip built against the template's rest position would
        // throw both away on its first frame.
        hipsRest: rig.bones.get('hips').position,
      });
      motionSource = 'auto_rig';
    }
  }

  const animator =
    clips.length > 0 ? new A3GameAnimationDirector(loaded.object, clips) : null;
  animator?.mapStateChains(REFERENCE_CLIP_CHAINS);
  return { ...loaded, animations: clips, animator, motionSource };
}
