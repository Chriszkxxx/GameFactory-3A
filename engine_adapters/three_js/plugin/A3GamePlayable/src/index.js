/**
 * `@a3game/playable` - runtime extension contracts for generated
 * three.js gameplay packages.
 *
 * This is the only supported import surface. Generated Gameplay Packages
 * must depend on this barrel, never on deep paths inside the adapter.
 *
 * Layers:
 *   data-types/  generic runtime data contract (wire format)
 *   interfaces/  contracts implemented by generated gameplay
 *   components/  identity and runtime-entity state on Object3D
 *   subsystems/  sessionownership and runtime coordination
 *   engine/      renderer, loop, assets, world, input, animation, HUD
 *
 * The framework provides no Character, Controller, GameMode, weapon,
 * vehicle, combat rule, or game-specific input mapping. Generated
 * projects own concrete gameplay.
 */

export const A3GAME_PLAYABLE_API_VERSION = 'v1';
export const A3GAME_PLAYABLE_ENGINE = 'three_js';

export {
  A3GameControlMode,
  A3GameLocomotionState,
  A3GameRuntimeCommand,
  createControlBinding,
  createControllerState,
  createEntitySnapshot,
  createEntitySpawnRequest,
  createParticipantInfo,
  createRuntimeInputState,
  createTransform,
  createVector3,
  locomotionStateFromInput,
} from './data-types/runtime-types.js';

export {
  A3GameControllableEntity,
  A3GameEntityFactory,
  A3GameRuntimeMessageHandler,
  CONTROLLABLE_ENTITY_METHODS,
  ENTITY_FACTORY_METHODS,
  RUNTIME_MESSAGE_HANDLER_METHODS,
  assertControllableEntity,
  assertEntityFactory,
  assertRuntimeMessageHandler,
  isControllableEntity,
  isEntityFactory,
  isRuntimeMessageHandler,
} from './interfaces/contracts.js';

export {
  A3GAME_USER_DATA_KEY,
  A3GameIdentityComponent,
  A3GameRuntimeEntityComponent,
} from './components/index.js';

export {
  A3GameRuntimeSubsystem,
  A3GameWorldSessionSubsystem,
} from './subsystems/index.js';

export {
  A3GameAnimationDirector,
  A3GameAssetLibrary,
  A3GameCollisionProbe,
  A3GameHudLayer,
  A3GameInputRouter,
  A3GameRuntimeChannel,
  A3GameRuntimeHost,
  A3GameSceneLoader,
  DEFAULT_KEY_BINDINGS,
  disposeObject3D,
} from './engine/index.js';

/**
 * Boot the whole framework in the conventional order.
 *
 * Convenience only: a generated game may wire the pieces itself.
 *
 * @param {{container: string | HTMLElement,
 *          hudContainer?: string | HTMLElement,
 *          manifestUrl?: string, worldUrl?: string,
 *          worldId?: string, hostOptions?: object,
 *          entityFactory?: object}} options
 */
export async function bootA3GameRuntime(options = {}) {
  const { A3GameRuntimeHost } = await import('./engine/runtime-host.js');
  const { A3GameAssetLibrary } = await import('./engine/asset-library.js');
  const { A3GameSceneLoader } = await import('./engine/scene-loader.js');
  const { A3GameHudLayer } = await import('./engine/hud-layer.js');
  const { A3GameWorldSessionSubsystem } = await import(
    './subsystems/world-session-subsystem.js'
  );
  const { A3GameRuntimeSubsystem } = await import(
    './subsystems/runtime-subsystem.js'
  );

  const host = new A3GameRuntimeHost({
    container: options.container,
    hudContainer: options.hudContainer,
    ...(options.hostOptions ?? {}),
  });
  await host.init();

  const assets = new A3GameAssetLibrary({
    manifestUrl: options.manifestUrl,
    renderer: host.renderer,
  });
  await assets.load();

  const sceneLoader = new A3GameSceneLoader({ host, assets });
  let world = null;
  if (options.worldUrl) {
    world = await sceneLoader.loadWorld(options.worldUrl);
  }

  const hud = options.hudContainer
    ? new A3GameHudLayer({ container: options.hudContainer })
    : null;

  const session = new A3GameWorldSessionSubsystem({
    worldId: options.worldId ?? world?.worldId ?? 'world_001',
  });
  const runtime = new A3GameRuntimeSubsystem({ host, session, assets });
  if (options.entityFactory) runtime.setEntityFactory(options.entityFactory);
  runtime.onWorldBeginPlay();
  host.start();

  return { host, assets, sceneLoader, hud, session, runtime, world };
}
