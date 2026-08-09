/** Engine scaffolding exports for the three.js runtime framework. */

export {
  A3GameEnvironmentPreset,
  A3GameRuntimeHost,
  disposeObject3D,
} from './runtime-host.js';
export { A3GameAssetLibrary } from './asset-library.js';
export {
  A3GameMaterialPreset,
  createContactShadow,
  createFillLight,
  createMaterial,
  createRadialGradientTexture,
  createRoundedBox,
  createSeededRandom,
  createSunLight,
  fitToHeight,
  groundObject,
  measureObject,
  prepareModel,
} from './visual-kit.js';
export { A3GameSceneLoader } from './scene-loader.js';
export {
  A3GameInputRouter,
  A3GameLookMode,
  DEFAULT_KEY_BINDINGS,
} from './input-router.js';
export { A3GameAnimationDirector } from './animation-director.js';
export {
  A3GameCollisionProbe,
  resolveEntityId,
} from './collision-probe.js';
export { A3GameHudLayer } from './hud-layer.js';
export { A3GameRuntimeChannel } from './runtime-channel.js';
