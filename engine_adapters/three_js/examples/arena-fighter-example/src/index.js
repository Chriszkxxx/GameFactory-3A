/**
 * Arena fighter boot sequence.
 *
 * Shows the full generated-gameplay wiring order:
 *   1. host + assets + world (framework)
 *   2. collision targets from the loaded world
 *   3. HUD widgets
 *   4. entity factory registration
 *   5. local input router piped into the session
 *
 * Nothing here reaches into the adapter's private modules, and no asset
 * URL is hard coded.
 */

import {
  A3GameCollisionProbe,
  A3GameHudLayer,
  A3GameInputRouter,
  bootA3GameRuntime,
} from '@a3game/playable';
import {
  ArenaFighterEntityFactory,
  ArenaMatchRules,
} from './factory.js';

export { ArenaFighterEntity } from './entity.js';
export { ArenaFighterEntityFactory, ArenaMatchRules } from './factory.js';

/**
 * @param {{container?: string, hudContainer?: string,
 *          worldUrl?: string, manifestUrl?: string,
 *          avatarArtifactId?: string, motionArtifactIds?: string[],
 *          autoJoinLocalPlayer?: boolean}} [options]
 */
export async function startArenaFighter(options = {}) {
  const runtimeContext = await bootA3GameRuntime({
    container: options.container ?? '#a3game-viewport',
    hudContainer: options.hudContainer ?? '#a3game-hud',
    manifestUrl: options.manifestUrl,
    worldUrl: options.worldUrl ?? '/assets/worlds/world_001.json',
    hostOptions: { fov: 55, shadows: true },
  });
  const { host, assets, sceneLoader, session, runtime } = runtimeContext;

  const collision = new A3GameCollisionProbe({
    targets: sceneLoader.collisionTargets,
    stepHeight: 0.55,
    radius: 0.42,
  });

  const hud = new A3GameHudLayer({
    container: options.hudContainer ?? '#a3game-hud',
  });
  hud.addText('round_timer', { anchor: 'top-center', value: '--' });
  hud.addBar('player_health', {
    anchor: 'bottom-left',
    label: 'HP',
    value: 1,
  });
  hud.addText('score', { anchor: 'top-right', value: '0' });

  let localEntityId = '';
  let input = null;

  const rules = new ArenaMatchRules({
    session,
    factory: null,
    onStateChanged: (state) => {
      hud.setValue(
        'round_timer',
        `${Math.ceil(state.remainingSeconds)}s`,
      );
      const player = state.fighters.find(
        (item) => item.entityId === localEntityId,
      );
      if (player) {
        hud.setValue('player_health', player.healthRatio);
        hud.setValue('score', String(player.score));
      }
    },
  });

  const factory = new ArenaFighterEntityFactory({
    collision,
    avatarArtifactId: options.avatarArtifactId,
    motionArtifactIds: options.motionArtifactIds,
    onEntityEvent: (event) => rules.handleEntityEvent(event),
  });
  rules.factory = factory;
  runtime.setEntityFactory(factory);
  host.onTick((delta) => rules.tick(delta));

  if (options.autoJoinLocalPlayer !== false) {
    const joined = await session.syncSession(
      {
        participant: { participantId: 'local_player' },
        controller: { controllerId: 'local_controller', kind: 'human' },
        binding: { mode: 'exclusive', priority: 10 },
        spawnRequest: {
          entityId: 'fighter_local',
          transform: sceneLoader.resolveSpawnTransform(0),
          parameters: {
            avatarArtifactId: options.avatarArtifactId ?? '',
            teamId: 'team_a',
          },
        },
      },
      (request) => runtime.spawnEntity(request),
    );
    localEntityId = joined.entityId;

    input = new A3GameInputRouter({
      target: host.container,
      controllerId: joined.controllerId,
      actionBindings: { Mouse0: 'attack_light', Mouse2: 'attack_heavy' },
    }).enable();
    input.onAction((action, phase) => {
      if (phase !== 'pressed') return;
      const entity = session.getEntity(localEntityId);
      if (action === 'attack_light') entity?.startAttack('light');
      if (action === 'attack_heavy') entity?.startAttack('heavy');
    });
    input.pipeToSession(session, host, {
      controllerId: joined.controllerId,
    });
    host.attachOrbitControls({
      target: { x: 0, y: 1.2, z: 0 },
      minDistance: 3,
      maxDistance: 12,
      maxPolarAngle: Math.PI / 2.1,
    });
  }

  const context = {
    ...runtimeContext,
    collision,
    hud,
    factory,
    rules,
    input,
    localEntityId,
    dispose() {
      input?.disable();
      hud.dispose();
      runtime.deinitialize();
      assets.dispose();
      host.dispose();
    },
  };
  globalThis.__A3GAME_ARENA__ = context;
  return context;
}
