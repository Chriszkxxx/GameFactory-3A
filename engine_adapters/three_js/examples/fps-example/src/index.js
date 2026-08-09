/**
 * Reference first-person shooter.
 *
 * Demonstrates the three patterns an FPS needs that a third-person game
 * does not: the camera is the entity, aiming comes from the input frame's
 * yaw/pitch, and shots resolve through `A3GameCollisionProbe.hitscan`.
 */

import * as THREE from 'three';
import {
  A3GameCollisionProbe,
  A3GameControllableEntity,
  A3GameEntityFactory,
  A3GameInputRouter,
  A3GameRuntimeEntityComponent,
  bootA3GameRuntime,
  disposeObject3D,
} from '@a3game/playable';

const WEAPON_PROFILES = Object.freeze({
  rifle: {
    damage: 24,
    magazine: 30,
    fireIntervalSeconds: 0.1,
    reloadSeconds: 2.1,
    range: 180,
    spreadRadians: 0.006,
    automatic: true,
  },
  pistol: {
    damage: 34,
    magazine: 12,
    fireIntervalSeconds: 0.24,
    reloadSeconds: 1.4,
    range: 120,
    spreadRadians: 0.003,
    automatic: false,
  },
});

export class FpsPlayerEntity extends A3GameControllableEntity {
  /**
   * @param {{host: object, collision: A3GameCollisionProbe,
   *          weapon?: 'rifle' | 'pistol', eyeHeight?: number,
   *          walkSpeed?: number, runSpeed?: number,
   *          maxHealth?: number}} options
   */
  constructor(options) {
    super();
    this.host = options.host;
    this.collision = options.collision;
    this.eyeHeight = Number(options.eyeHeight ?? 1.7);
    this.walkSpeed = Number(options.walkSpeed ?? 4.2);
    this.runSpeed = Number(options.runSpeed ?? 7.4);
    this.maxHealth = Number(options.maxHealth ?? 100);
    this.health = this.maxHealth;
    this.alive = true;

    // The entity owns a pivot; the camera is parented to it so the
    // framework's generic transform snapshot still describes the player.
    this.object = new THREE.Object3D();
    this.object.name = 'fps_player';
    this.host.add(this.object, 'entities');
    this.host.camera.position.set(0, this.eyeHeight, 0);
    this.object.add(this.host.camera);

    this.runtime = new A3GameRuntimeEntityComponent(this.object);
    this.motion = {
      position: this.object.position.clone(),
      velocityY: 0,
      grounded: true,
    };
    this.desired = new THREE.Vector3();
    this.pendingJump = false;
    this.yaw = 0;
    this.pitch = 0;

    this.weaponKey = options.weapon ?? 'rifle';
    this.weapon = { ...WEAPON_PROFILES[this.weaponKey] };
    this.ammoInMagazine = this.weapon.magazine;
    this.reserveAmmo = this.weapon.magazine * 4;
    this.fireCooldown = 0;
    this.reloadTimer = 0;
    this.triggerHeld = false;
    this.shotsFired = 0;
    this.shotsHit = 0;
    /** @type {Set<(event: object) => void>} */
    this.eventListeners = new Set();
  }

  getRuntimeEntityId() {
    return this.runtime.entityId;
  }

  setRuntimeEntityId(entityId) {
    this.runtime.setRuntimeEntityId(entityId);
    return this;
  }

  applyRuntimeInput(inputState) {
    if (!this.alive) return false;
    if (!this.runtime.applyRuntimeInput(inputState)) return false;
    this.yaw = inputState.yaw;
    this.pitch = inputState.pitch;
    const speed = inputState.run ? this.runSpeed : this.walkSpeed;
    const forward = new THREE.Vector3(
      -Math.sin(this.yaw),
      0,
      -Math.cos(this.yaw),
    );
    const right = new THREE.Vector3(-forward.z, 0, forward.x);
    this.desired
      .copy(forward)
      .multiplyScalar(inputState.moveY)
      .addScaledVector(right, inputState.moveX);
    if (this.desired.lengthSq() > 1) this.desired.normalize();
    this.desired.multiplyScalar(speed);
    if (inputState.jump) this.pendingJump = true;
    return true;
  }

  getRuntimeSnapshot() {
    return {
      ...this.runtime.getRuntimeSnapshot(),
      motionState: this.reloadTimer > 0
        ? 'reload'
        : this.runtime.locomotionState,
    };
  }

  tick(deltaSeconds) {
    if (!this.alive) return;
    this.fireCooldown = Math.max(0, this.fireCooldown - deltaSeconds);
    if (this.reloadTimer > 0) {
      this.reloadTimer = Math.max(0, this.reloadTimer - deltaSeconds);
      if (this.reloadTimer === 0) this.#finishReload();
    }

    this.collision.stepCharacter(
      this.motion,
      this.desired.clone().multiplyScalar(deltaSeconds),
      deltaSeconds,
      { height: this.eyeHeight, jump: this.pendingJump, jumpImpulse: 5.6 },
    );
    this.pendingJump = false;
    this.object.position.copy(this.motion.position);
    this.object.rotation.y = this.yaw;
    this.host.camera.rotation.set(this.pitch, 0, 0);

    if (this.triggerHeld && this.weapon.automatic) this.fire();
  }

  /** @param {(event: object) => void} listener */
  onEvent(listener) {
    this.eventListeners.add(listener);
    return () => this.eventListeners.delete(listener);
  }

  setTrigger(held) {
    this.triggerHeld = Boolean(held);
    if (this.triggerHeld && !this.weapon.automatic) this.fire();
    return this;
  }

  /** Resolve one hitscan shot. Returns the hit result or null. */
  fire() {
    if (!this.alive || this.fireCooldown > 0 || this.reloadTimer > 0) {
      return null;
    }
    if (this.ammoInMagazine <= 0) {
      this.startReload();
      return null;
    }
    this.ammoInMagazine -= 1;
    this.shotsFired += 1;
    this.fireCooldown = this.weapon.fireIntervalSeconds;

    const origin = new THREE.Vector3();
    this.host.camera.getWorldPosition(origin);
    const direction = new THREE.Vector3();
    this.host.camera.getWorldDirection(direction);
    // Deterministic-friendly spread: callers may seed Math.random in tests.
    direction.x += (Math.random() - 0.5) * this.weapon.spreadRadians * 2;
    direction.y += (Math.random() - 0.5) * this.weapon.spreadRadians * 2;
    direction.normalize();

    const hit = this.collision.hitscan(origin, direction, {
      range: this.weapon.range,
      ignore: [this.object],
    });
    if (hit.hit) this.shotsHit += 1;
    this.#emit({
      type: 'shot_fired',
      hit: hit.hit,
      hitEntityId: hit.entityId,
      point: hit.point ? hit.point.toArray() : null,
      distance: hit.distance,
      damage: this.weapon.damage,
      ammoInMagazine: this.ammoInMagazine,
    });
    return hit;
  }

  startReload() {
    if (this.reloadTimer > 0) return false;
    if (this.ammoInMagazine >= this.weapon.magazine) return false;
    if (this.reserveAmmo <= 0) return false;
    this.reloadTimer = this.weapon.reloadSeconds;
    this.#emit({ type: 'reload_started' });
    return true;
  }

  receiveDamage(amount, sourceEntityId = '') {
    if (!this.alive) return false;
    this.health = Math.max(0, this.health - Math.max(0, Number(amount) || 0));
    this.#emit({
      type: 'damaged',
      amount,
      sourceEntityId,
      health: this.health,
      healthRatio: this.health / this.maxHealth,
    });
    if (this.health === 0) {
      this.alive = false;
      this.#emit({ type: 'died', sourceEntityId });
    }
    return true;
  }

  /** @returns {object} weapon and accuracy state for HUD and tests. */
  getWeaponState() {
    return {
      weapon: this.weaponKey,
      ammoInMagazine: this.ammoInMagazine,
      reserveAmmo: this.reserveAmmo,
      reloading: this.reloadTimer > 0,
      shotsFired: this.shotsFired,
      shotsHit: this.shotsHit,
      accuracy:
        this.shotsFired === 0
          ? 0
          : Number((this.shotsHit / this.shotsFired).toFixed(3)),
    };
  }

  dispose() {
    this.eventListeners.clear();
    this.object.remove(this.host.camera);
    this.runtime.dispose();
    disposeObject3D(this.object);
  }

  #finishReload() {
    const needed = this.weapon.magazine - this.ammoInMagazine;
    const loaded = Math.min(needed, this.reserveAmmo);
    this.ammoInMagazine += loaded;
    this.reserveAmmo -= loaded;
    this.#emit({
      type: 'reload_finished',
      ammoInMagazine: this.ammoInMagazine,
    });
  }

  #emit(event) {
    const payload = { ...event, entityId: this.runtime.entityId };
    for (const listener of this.eventListeners) listener(payload);
  }
}

export class FpsEntityFactory extends A3GameEntityFactory {
  /**
   * @param {{collision: A3GameCollisionProbe,
   *          onEntityEvent?: (event: object) => void}} options
   */
  constructor(options) {
    super();
    this.collision = options.collision;
    this.onEntityEvent = options.onEntityEvent ?? null;
    /** @type {Map<string, FpsPlayerEntity>} */
    this.entities = new Map();
  }

  async spawnRuntimeEntity(request, { host }) {
    const entity = new FpsPlayerEntity({
      host,
      collision: this.collision,
      weapon: String(request.parameters?.weapon ?? 'rifle'),
    });
    const position = request.transform?.position ?? { x: 0, y: 0, z: 0 };
    entity.motion.position.set(position.x, position.y, position.z);
    entity.object.position.copy(entity.motion.position);
    if (this.onEntityEvent) entity.onEvent(this.onEntityEvent);
    this.entities.set(request.entityId || entity.object.name, entity);
    return entity;
  }
}

/**
 * @param {{container?: string, hudContainer?: string, worldUrl?: string,
 *          manifestUrl?: string, weapon?: string}} [options]
 */
export async function startFps(options = {}) {
  const hudContainer = options.hudContainer ?? '#a3game-hud';
  const runtimeContext = await bootA3GameRuntime({
    container: options.container ?? '#a3game-viewport',
    hudContainer,
    manifestUrl: options.manifestUrl,
    worldUrl: options.worldUrl ?? '/assets/worlds/world_001.json',
    hostOptions: { fov: 75 },
    // Local input must reach the session before the runtime tick
    // consumes it, so this game owns the begin-play ordering.
    autoBeginPlay: false,
    autoStart: false,
  });
  const { host, assets, sceneLoader, session, runtime, hud } = runtimeContext;

  const collision = new A3GameCollisionProbe({
    targets: sceneLoader.collisionTargets,
    stepHeight: 0.5,
    radius: 0.35,
  });

  hud.addCrosshair();
  hud.addBar('health', { anchor: 'bottom-left', label: 'HP', value: 1 });
  hud.addText('ammo', { anchor: 'bottom-right', value: '--' });
  hud.addText('accuracy', { anchor: 'top-right', value: '0%' });

  const factory = new FpsEntityFactory({
    collision,
    onEntityEvent: (event) => {
      if (event.type === 'damaged' || event.type === 'died') {
        hud.setValue('health', event.healthRatio ?? 0);
      }
      const entity = factory.entities.get(event.entityId);
      if (!entity) return;
      const state = entity.getWeaponState();
      hud.setValue(
        'ammo',
        state.reloading
          ? 'RELOADING'
          : `${state.ammoInMagazine} / ${state.reserveAmmo}`,
      );
      hud.setValue(
        'accuracy',
        `${Math.round(state.accuracy * 100)}%`,
      );
    },
  });
  runtime.setEntityFactory(factory);

  const joined = await session.syncSession(
    {
      participant: { participantId: 'local_player' },
      controller: { controllerId: 'local_controller', kind: 'human' },
      binding: { mode: 'exclusive', priority: 10 },
      spawnRequest: {
        entityId: 'fps_local',
        transform: sceneLoader.resolveSpawnTransform(0),
        parameters: { weapon: options.weapon ?? 'rifle' },
      },
    },
    (request) => runtime.spawnEntity(request),
  );

  // This game derives yaw/pitch from the input frame, so it takes plain
  // pointer lock. Attaching PointerLockControls as well would make both
  // the controls and `tick()` write the same camera every frame.
  host.container.addEventListener('click', () => {
    void host.requestPointerLock();
  });

  const input = new A3GameInputRouter({
    target: host.container,
    controllerId: joined.controllerId,
    actionBindings: { Mouse0: 'fire', KeyR: 'reload' },
  }).enable();
  input.onAction((action, phase) => {
    const entity = session.getEntity(joined.entityId);
    if (!entity) return;
    if (action === 'fire') entity.setTrigger(phase === 'pressed');
    if (action === 'reload' && phase === 'pressed') entity.startReload();
  });
  input.pipeToSession(session, host, {
    controllerId: joined.controllerId,
  });

  runtime.onWorldBeginPlay();
  host.start();

  const context = {
    ...runtimeContext,
    collision,
    hud,
    factory,
    input,
    localEntityId: joined.entityId,
    dispose() {
      input.disable();
      hud.dispose();
      runtime.deinitialize();
      assets.dispose();
      host.dispose();
    },
  };
  globalThis.__A3GAME_FPS__ = context;
  return context;
}
