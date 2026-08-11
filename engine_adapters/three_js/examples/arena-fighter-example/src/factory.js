/**
 * Arena fighter entity factory and match rules.
 *
 * The factory is the only place that knows which concrete class an
 * entity uses. The framework calls it through `IA3GameEntityFactory`'s
 * web counterpart, `A3GameEntityFactory`.
 */

import * as THREE from 'three';
import {
  A3GameEntityFactory,
  A3GameCollisionProbe,
} from '@a3game/playable';
import { ArenaFighterEntity } from './entity.js';

export class ArenaFighterEntityFactory extends A3GameEntityFactory {
  /**
   * @param {{collision: A3GameCollisionProbe,
   *          avatarArtifactId?: string,
   *          motionArtifactIds?: string[],
   *          onEntityEvent?: (event: object) => void}} options
   */
  constructor(options = {}) {
    super();
    this.collision = options.collision;
    this.avatarArtifactId = String(options.avatarArtifactId ?? '');
    this.motionArtifactIds = [...(options.motionArtifactIds ?? [])];
    this.onEntityEvent = options.onEntityEvent ?? null;
    /** @type {Map<string, ArenaFighterEntity>} */
    this.entities = new Map();
  }

  /** @returns {Promise<ArenaFighterEntity>} */
  async spawnRuntimeEntity(request, { host, assets }) {
    const avatarRef =
      String(request.parameters?.avatarArtifactId ?? '') ||
      this.avatarArtifactId;
    if (!avatarRef) {
      throw new Error(
        'Arena fighter spawn requires an avatarArtifactId parameter',
      );
    }
    const { object, animations } = await assets.instantiate(avatarRef);

    // Motion clips imported separately are merged onto the same rig.
    const extraClips = [];
    for (const motionRef of this.motionArtifactIds) {
      const loaded = await assets.loadArtifact(motionRef).catch(() => null);
      if (loaded?.animations) extraClips.push(...loaded.animations);
    }

    object.name = request.entityId || 'arena_fighter';
    const transform = request.transform ?? {};
    object.position.set(
      transform.position?.x ?? 0,
      transform.position?.y ?? 0,
      transform.position?.z ?? 0,
    );
    object.traverse((child) => {
      if (!child.isMesh) return;
      child.castShadow = true;
      child.receiveShadow = true;
    });
    host.add(object, 'entities');

    const entity = new ArenaFighterEntity({
      object,
      animations: [...animations, ...extraClips],
      host,
      collision: this.collision,
      teamId: String(request.parameters?.teamId ?? 'team_a'),
      maxHealth: Number(request.parameters?.maxHealth ?? 100),
    });
    if (this.onEntityEvent) entity.onEvent(this.onEntityEvent);
    this.entities.set(request.entityId || object.name, entity);
    return entity;
  }

  /** Remove an entity from factory bookkeeping. */
  forget(entityId) {
    return this.entities.delete(String(entityId));
  }
}

/**
 * Arena match rules: resolve melee hits, track score, end the round.
 *
 * Rules live in the generated package, never in the framework.
 */
export class ArenaMatchRules {
  /**
   * @param {{session: object, factory: ArenaFighterEntityFactory,
   *          roundSeconds?: number,
   *          onStateChanged?: (state: object) => void}} options
   */
  constructor(options) {
    this.session = options.session;
    this.factory = options.factory;
    this.roundSeconds = Number(options.roundSeconds ?? 120);
    this.onStateChanged = options.onStateChanged ?? null;
    this.remainingSeconds = this.roundSeconds;
    this.finished = false;
    /** @type {Map<string, number>} */
    this.scores = new Map();
  }

  /** Handle one entity event emitted by a fighter. */
  handleEntityEvent(event) {
    if (event.type === 'attack_active') {
      this.#resolveMelee(event.entityId, event.damage);
      return;
    }
    if (event.type === 'died') {
      const killer = String(event.sourceEntityId ?? '');
      if (killer) {
        this.scores.set(killer, (this.scores.get(killer) ?? 0) + 1);
      }
      this.#publish();
    }
  }

  /** Advance the round clock. Bind to the host tick. */
  tick(deltaSeconds) {
    if (this.finished) return;
    this.remainingSeconds = Math.max(
      0,
      this.remainingSeconds - deltaSeconds,
    );
    if (this.remainingSeconds === 0) {
      this.finished = true;
      this.#publish();
    }
  }

  /** @returns {object} match state, suitable for HUD binding and tests. */
  getState() {
    const fighters = [...this.factory.entities.entries()].map(
      ([entityId, entity]) => ({
        entityId,
        teamId: entity.teamId,
        health: entity.health,
        healthRatio: entity.health / entity.maxHealth,
        alive: entity.alive,
        score: this.scores.get(entityId) ?? 0,
      }),
    );
    return {
      remainingSeconds: Number(this.remainingSeconds.toFixed(2)),
      finished: this.finished,
      fighters,
      aliveCount: fighters.filter((item) => item.alive).length,
    };
  }

  #resolveMelee(attackerId, damage) {
    const attacker = this.factory.entities.get(String(attackerId));
    if (!attacker) return;
    const { origin, direction, reach } = attacker.getAttackVolume();
    for (const [entityId, target] of this.factory.entities) {
      if (entityId === String(attackerId) || !target.alive) continue;
      if (target.teamId === attacker.teamId) continue;
      const toTarget = target.object.position
        .clone()
        .add(new THREE.Vector3(0, 1.1, 0))
        .sub(origin);
      if (toTarget.length() > reach) continue;
      if (toTarget.normalize().dot(direction) < 0.35) continue;
      target.receiveDamage(damage, String(attackerId));
    }
    this.#publish();
  }

  #publish() {
    this.onStateChanged?.(this.getState());
  }
}
