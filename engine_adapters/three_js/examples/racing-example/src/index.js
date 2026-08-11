/**
 * Reference arcade racing game.
 *
 * Demonstrates reinterpreting the same generic input frame for a
 * vehicle: `moveY` becomes throttle/brake, `moveX` becomes steering,
 * `run` becomes boost, and `jump` becomes handbrake. The framework
 * contract does not change; only the game's reading of it does.
 */

import * as THREE from 'three';
import {
  A3GameCollisionProbe,
  A3GameControllableEntity,
  A3GameEntityFactory,
  A3GameHudLayer,
  A3GameInputRouter,
  A3GameRuntimeEntityComponent,
  bootA3GameRuntime,
  disposeObject3D,
} from '@a3game/playable';

const VEHICLE_PROFILES = Object.freeze({
  balanced: {
    maxSpeed: 46,
    reverseSpeed: 12,
    acceleration: 18,
    brakeDeceleration: 34,
    coastDeceleration: 7,
    steerRate: 1.9,
    gripFactor: 5.5,
    driftGripFactor: 1.5,
    boostMultiplier: 1.45,
    boostCapacitySeconds: 3.2,
    boostRefillPerSecond: 0.5,
  },
});

export class RacingVehicleEntity extends A3GameControllableEntity {
  /**
   * @param {{object: THREE.Object3D, host: object,
   *          collision: A3GameCollisionProbe,
   *          profile?: keyof typeof VEHICLE_PROFILES}} options
   */
  constructor(options) {
    super();
    this.object = options.object;
    this.host = options.host;
    this.collision = options.collision;
    this.profile = { ...VEHICLE_PROFILES[options.profile ?? 'balanced'] };

    this.runtime = new A3GameRuntimeEntityComponent(this.object);
    this.velocity = new THREE.Vector3();
    this.speed = 0;
    this.heading = this.object.rotation.y;
    this.throttle = 0;
    this.steer = 0;
    this.boosting = false;
    this.handbrake = false;
    this.boostRemaining = this.profile.boostCapacitySeconds;
    this.grounded = true;
    this.driftAngle = 0;
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
    if (!this.runtime.applyRuntimeInput(inputState)) return false;
    this.throttle = inputState.moveY;
    this.steer = inputState.moveX;
    this.boosting = Boolean(inputState.run) && this.boostRemaining > 0;
    this.handbrake = Boolean(inputState.jump);
    return true;
  }

  getRuntimeSnapshot() {
    const snapshot = this.runtime.getRuntimeSnapshot();
    return {
      ...snapshot,
      motionState: this.handbrake
        ? 'drift'
        : this.boosting
          ? 'boost'
          : Math.abs(this.speed) < 0.5
            ? 'idle'
            : 'drive',
    };
  }

  tick(deltaSeconds) {
    const profile = this.profile;
    const boostFactor = this.boosting ? profile.boostMultiplier : 1;

    if (this.throttle > 0.01) {
      this.speed += profile.acceleration * this.throttle * deltaSeconds;
    } else if (this.throttle < -0.01) {
      this.speed -=
        profile.brakeDeceleration * Math.abs(this.throttle) * deltaSeconds;
    } else {
      const drag = profile.coastDeceleration * deltaSeconds;
      this.speed =
        this.speed > 0
          ? Math.max(0, this.speed - drag)
          : Math.min(0, this.speed + drag);
    }
    if (this.handbrake) {
      this.speed *= Math.max(0, 1 - 2.4 * deltaSeconds);
    }
    this.speed = Math.max(
      -profile.reverseSpeed,
      Math.min(profile.maxSpeed * boostFactor, this.speed),
    );

    if (this.boosting) {
      this.boostRemaining = Math.max(
        0,
        this.boostRemaining - deltaSeconds,
      );
      if (this.boostRemaining === 0) this.boosting = false;
    } else {
      this.boostRemaining = Math.min(
        profile.boostCapacitySeconds,
        this.boostRemaining + profile.boostRefillPerSecond * deltaSeconds,
      );
    }

    // Steering authority scales with speed, so a parked car cannot spin.
    const speedRatio = Math.min(
      1,
      Math.abs(this.speed) / (profile.maxSpeed * 0.45),
    );
    this.heading -=
      this.steer * profile.steerRate * speedRatio * deltaSeconds;
    this.object.rotation.y = this.heading;

    const forward = new THREE.Vector3(
      -Math.sin(this.heading),
      0,
      -Math.cos(this.heading),
    );
    const desired = forward.clone().multiplyScalar(this.speed);
    const grip = this.handbrake
      ? profile.driftGripFactor
      : profile.gripFactor;
    this.velocity.lerp(desired, 1 - Math.exp(-grip * deltaSeconds));
    this.driftAngle = this.velocity.angleTo(forward);

    const step = this.velocity.clone().multiplyScalar(deltaSeconds);
    const resolved = this.collision.resolveMove(
      this.object.position,
      step,
      { height: 0.8 },
    );
    if (resolved.blocked) {
      this.speed *= 0.4;
      this.velocity.multiplyScalar(0.4);
      this.#emit({ type: 'collided', speed: this.speed });
    }
    this.object.position.add(resolved.move);

    const ground = this.collision.sampleGround(this.object.position, {
      probeHeight: 1.2,
    });
    this.grounded = ground.hit;
    if (ground.hit) {
      this.object.position.y = THREE.MathUtils.lerp(
        this.object.position.y,
        ground.height,
        1 - Math.exp(-14 * deltaSeconds),
      );
    }
  }

  /** @param {(event: object) => void} listener */
  onEvent(listener) {
    this.eventListeners.add(listener);
    return () => this.eventListeners.delete(listener);
  }

  /** @returns {object} vehicle telemetry for HUD and tests. */
  getVehicleState() {
    return {
      speedMetresPerSecond: Number(this.speed.toFixed(2)),
      speedKilometresPerHour: Number((this.speed * 3.6).toFixed(1)),
      boostRemaining: Number(this.boostRemaining.toFixed(2)),
      boostRatio: Number(
        (this.boostRemaining / this.profile.boostCapacitySeconds).toFixed(3),
      ),
      drifting: this.handbrake && this.driftAngle > 0.12,
      driftAngle: Number(this.driftAngle.toFixed(3)),
      grounded: this.grounded,
    };
  }

  dispose() {
    this.eventListeners.clear();
    this.runtime.dispose();
    disposeObject3D(this.object);
  }

  #emit(event) {
    const payload = { ...event, entityId: this.runtime.entityId };
    for (const listener of this.eventListeners) listener(payload);
  }
}

/** Lap timing acrossordered checkpoint volumes declared by the world. */
export class RacingLapTracker {
  /**
   * @param {{checkpoints: {name: string, position: {x: number, y: number,
   *          z: number}, radius?: number}[], totalLaps?: number,
   *          onStateChanged?: (state: object) => void}} options
   */
  constructor(options) {
    this.checkpoints = [...(options.checkpoints ?? [])];
    this.totalLaps = Number(options.totalLaps ?? 3);
    this.onStateChanged = options.onStateChanged ?? null;
    /** @type {Map<string, object>} */
    this.progress = new Map();
  }

  /** Register one racer. */
  register(entityId) {
    this.progress.set(String(entityId), {
      entityId: String(entityId),
      lap: 0,
      nextCheckpoint: 0,
      lapTimes: [],
      elapsedSeconds: 0,
      finished: false,
    });
    return this;
  }

  /**
   * Advance timing and checkpoint detection.
   *
   * @param {number} deltaSeconds
   * @param {Map<string, RacingVehicleEntity>} vehicles
   */
  tick(deltaSeconds, vehicles) {
    let changed = false;
    for (const [entityId, state] of this.progress) {
      const vehicle = vehicles.get(entityId);
      if (!vehicle || state.finished) continue;
      state.elapsedSeconds += deltaSeconds;
      const checkpoint = this.checkpoints[state.nextCheckpoint];
      if (!checkpoint) continue;
      const target = new THREE.Vector3(
        checkpoint.position.x,
        checkpoint.position.y,
        checkpoint.position.z,
      );
      const radius = Number(checkpoint.radius ?? 8);
      if (vehicle.object.position.distanceTo(target) > radius) continue;
      state.nextCheckpoint += 1;
      changed = true;
      if (state.nextCheckpoint >= this.checkpoints.length) {
        state.nextCheckpoint = 0;
        state.lap += 1;
        const previous = state.lapTimes.reduce((sum, x) => sum + x, 0);
        state.lapTimes.push(
          Number((state.elapsedSeconds - previous).toFixed(3)),
        );
        if (state.lap >= this.totalLaps) state.finished = true;
      }
    }
    if (changed) this.onStateChanged?.(this.getState());
  }

  /** @returns {object} */
  getState() {
    const racers = [...this.progress.values()].map((item) => ({ ...item }));
    return {
      totalLaps: this.totalLaps,
      checkpointCount: this.checkpoints.length,
      racers,
      finishedCount: racers.filter((item) => item.finished).length,
    };
  }
}

export class RacingEntityFactory extends A3GameEntityFactory {
  /**
   * @param {{collision: A3GameCollisionProbe,
   *          vehicleArtifactId?: string,
   *          onEntityEvent?: (event: object) => void}} options
   */
  constructor(options) {
    super();
    this.collision = options.collision;
    this.vehicleArtifactId = String(options.vehicleArtifactId ?? '');
    this.onEntityEvent = options.onEntityEvent ?? null;
    /** @type {Map<string, RacingVehicleEntity>} */
    this.entities = new Map();
  }

  async spawnRuntimeEntity(request, { host, assets }) {
    const reference =
      String(request.parameters?.vehicleArtifactId ?? '') ||
      this.vehicleArtifactId;
    let object;
    if (reference) {
      const instance = await assets.instantiate(reference);
      object = instance.object;
    } else {
      // Fallback proxy keeps the game runnable before art lands.
      object = new THREE.Mesh(
        new THREE.BoxGeometry(1.8, 0.7, 4),
        new THREE.MeshStandardMaterial({ color: 0x2f6fed }),
      );
    }
    object.name = request.entityId || 'racing_vehicle';
    const position = request.transform?.position ?? { x: 0, y: 0, z: 0 };
    object.position.set(position.x, position.y, position.z);
    object.traverse((child) => {
      if (child.isMesh) child.castShadow = true;
    });
    host.add(object, 'entities');

    const entity = new RacingVehicleEntity({
      object,
      host,
      collision: this.collision,
      profile: String(request.parameters?.profile ?? 'balanced'),
    });
    if (this.onEntityEvent) entity.onEvent(this.onEntityEvent);
    this.entities.set(object.name, entity);
    return entity;
  }
}

/**
 * @param {{container?: string, hudContainer?: string, worldUrl?: string,
 *          manifestUrl?: string, vehicleArtifactId?: string,
 *          totalLaps?: number}} [options]
 */
export async function startRacing(options = {}) {
  const runtimeContext = await bootA3GameRuntime({
    container: options.container ?? '#a3game-viewport',
    hudContainer: options.hudContainer ?? '#a3game-hud',
    manifestUrl: options.manifestUrl,
    worldUrl: options.worldUrl ?? '/assets/worlds/world_001.json',
    hostOptions: { fov: 62, far: 4000 },
  });
  const { host, assets, sceneLoader, session, runtime } = runtimeContext;

  const collision = new A3GameCollisionProbe({
    targets: sceneLoader.collisionTargets,
    stepHeight: 0.4,
    radius: 1.2,
    gravity: -22,
  });

  const hud = new A3GameHudLayer({
    container: options.hudContainer ?? '#a3game-hud',
  });
  hud.addText('speed', { anchor: 'bottom-right', value: '0 km/h' });
  hud.addBar('boost', { anchor: 'bottom-left', label: 'BOOST', value: 1 });
  hud.addText('lap', { anchor: 'top-left', value: 'Lap 0' });

  const factory = new RacingEntityFactory({
    collision,
    vehicleArtifactId: options.vehicleArtifactId,
  });
  runtime.setEntityFactory(factory);

  const laps = new RacingLapTracker({
    checkpoints: sceneLoader.spawnPoints.map((point) => ({
      name: point.name,
      position: point.position,
      radius: 10,
    })),
    totalLaps: options.totalLaps ?? 3,
    onStateChanged: (state) => {
      const racer = state.racers[0];
      if (racer) {
        hud.setValue('lap', `Lap ${racer.lap} / ${state.totalLaps}`);
      }
    },
  });

  const joined = await session.syncSession(
    {
      participant: { participantId: 'local_player' },
      controller: { controllerId: 'local_controller', kind: 'human' },
      binding: { mode: 'exclusive', priority: 10 },
      spawnRequest: {
        entityId: 'vehicle_local',
        transform: sceneLoader.resolveSpawnTransform(0),
        parameters: {
          vehicleArtifactId: options.vehicleArtifactId ?? '',
        },
      },
    },
    (request) => runtime.spawnEntity(request),
  );
  laps.register(joined.entityId);

  const input = new A3GameInputRouter({
    target: host.container,
    controllerId: joined.controllerId,
  }).enable();
  input.pipeToSession(session, host, {
    controllerId: joined.controllerId,
  });

  // Chase camera: the framework does not define one, so the game does.
  const chaseOffset = new THREE.Vector3(0, 3.2, 8.5);
  host.detachControls();
  host.onTick((delta) => {
    laps.tick(delta, factory.entities);
    const vehicle = session.getEntity(joined.entityId);
    if (!vehicle) return;
    const state = vehicle.getVehicleState();
    hud.setValue('speed', `${Math.round(state.speedKilometresPerHour)} km/h`);
    hud.setValue('boost', state.boostRatio);
    const target = vehicle.object.position;
    const desired = chaseOffset
      .clone()
      .applyAxisAngle(new THREE.Vector3(0, 1, 0), vehicle.heading)
      .add(target);
    host.camera.position.lerp(desired, 1 - Math.exp(-6 * delta));
    host.camera.lookAt(target.x, target.y + 1.1, target.z);
  });

  const context = {
    ...runtimeContext,
    collision,
    hud,
    factory,
    laps,
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
  globalThis.__A3GAME_RACING__ = context;
  return context;
}
