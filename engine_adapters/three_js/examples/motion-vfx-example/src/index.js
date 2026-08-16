/**
 * Reference patterns for motion and effects on `@a3game/playable`.
 *
 * Read `motion.js` for how a character is made to move, and `effects.js`
 * for how particles, beams, and trails get into a scene. This barrel only
 * re-exports them; there is no game here.
 *
 * Like the other example packages, this one is a **read-only reference**.
 * It is never installed, and a generated game must adapt these patterns
 * inside its own Gameplay Package rather than depending on this one.
 */

export {
  REFERENCE_CLIP_CHAINS,
  dressCharacter,
  resolveMotionByHand,
} from './motion.js';

export {
  ReferenceLightProjectile,
  createIntensityStream,
  createShooterEffects,
  playShotEffects,
} from './effects.js';
