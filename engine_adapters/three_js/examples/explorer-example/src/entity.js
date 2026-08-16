/**
 * The explorer: a third-person character with a charged ranged attack.
 *
 * Three things here are specific to third-person exploration, and all
 * three are what an FPS or a fighter gets to skip:
 *
 * 1. **Movement is camera-relative.** "Forward" means away from the
 *    camera, not along the character's own facing. This is the only
 *    mapping that feels right when the player can see the character, and
 *    it is why `applyRuntimeInput` needs a camera yaw that the *camera*
 *    owns — see `cameraYaw`.
 * 2. **The camera is not parented to the entity.** An FPS entity *is* the
 *    camera; here the camera trails, and lags, and is allowed to look
 *    where the character is not. So the entity publishes its position and
 *    `followCamera` consumes it, rather than the entity moving the camera.
 * 3. **The ground is not flat.** Height comes from `terrainHeight`, the
 *    same function the visible mesh was built from.
 *
 * The bow is a *held* action: pressing draws, releasing shoots, and the
 * time between the two decides the shot. That needs the input router's
 * pressed/released phases rather than a click handler.
 */

import * as THREE from 'three';
import {
  A3GameControllableEntity,
  A3GameRuntimeEntityComponent,
  createMaterial,
  A3GameMaterialPreset,
  createRoundedBox,
  disposeObject3D,
} from '@a3game/playable';
import { terrainHeight } from './terrain.js';

/** Tuning for the explorer. All metres, seconds, and metres per second. */
export const EXPLORER_PROFILE = Object.freeze({
  walkSpeed: 4.4,
  runSpeed: 8.2,
  /** Movement is throttled while the bow is drawn, not blocked. */
  drawMoveFactor: 0.4,
  turnResponse: 12,
  jumpImpulse: 6.4,
  gravity: -19,
  eyeHeight: 1.72,
  maxStamina: 100,
  staminaDrainPerSecond: 22,
  staminaRefillPerSecond: 16,
  /** Seconds to a fully charged shot. */
  fullDrawSeconds: 1.1,
  minArrowSpeed: 18,
  maxArrowSpeed: 46,
});

/**
 * Where held equipment sits, relative to the character's own origin.
 *
 * One constant, because five places have to agree about it: the bow mesh,
 * the hand it is parented to, the string's draw offset, the arrow's spawn
 * point, and the test. When these drifted apart the bow floated a third of
 * a metre outside the character's silhouette, which reads as a prop
 * orbiting a person rather than as a person holding a bow.
 */
export const HELD_ANCHORS = Object.freeze({
  bow: { x: -0.23, y: 1.16, z: -0.12 },
  /** Where an arrow leaves the bow. */
  nock: { x: -0.2, y: 1.2, z: -0.34 },
  bowSpan: 0.66,
});

/** Build a stand-in body, used until (or unless) art is imported. */
function createBody() {
  const group = new THREE.Group();
  const cloth = createMaterial(A3GameMaterialPreset.CLOTH, { color: 0x3f5d78 });
  const leather = createMaterial(A3GameMaterialPreset.LEATHER, {
    color: 0x6b4a2f,
  });

  const torso = createRoundedBox({
    width: 0.46,
    height: 0.68,
    depth: 0.26,
    radius: 0.09,
    material: cloth,
  });
  torso.position.y = 1.18;
  group.add(torso);

  const head = new THREE.Mesh(
    new THREE.SphereGeometry(0.15, 16, 12),
    leather,
  );
  head.position.y = 1.66;
  group.add(head);

  for (const sign of [-1, 1]) {
    const leg = createRoundedBox({
      width: 0.16,
      height: 0.84,
      depth: 0.18,
      radius: 0.06,
      material: leather,
    });
    leg.position.set(sign * 0.12, 0.42, 0);
    group.add(leg);
  }

  // The bow: a torus arc, sized and placed from HELD_ANCHORS so it stays
  // inside the character's outline.
  const bow = new THREE.Mesh(
    new THREE.TorusGeometry(HELD_ANCHORS.bowSpan / 2, 0.018, 6, 20, Math.PI * 1.2),
    leather,
  );
  bow.name = 'bow';
  bow.rotation.set(0, Math.PI / 2, Math.PI / 2);
  bow.position.set(HELD_ANCHORS.bow.x, HELD_ANCHORS.bow.y, HELD_ANCHORS.bow.z);
  group.add(bow);

  group.traverse((child) => {
    if (child.isMesh) child.castShadow = true;
  });
  return { group, bow };
}

export class ExplorerEntity extends A3GameControllableEntity {
  /**
   * @param {{host: object, collision?: object, entityId?: string,
   *          profile?: object}} options
   */
  constructor(options) {
    super();
    this.host = options.host;
    this.collision = options.collision ?? null;
    this.profile = { ...EXPLORER_PROFILE, ...(options.profile ?? {}) };

    this.object = new THREE.Object3D();
    this.object.name = String(options.entityId ?? 'explorer');
    this.host.add(this.object, 'entities');

    // The visible body is a child, so imported art can replace it without
    // touching the transform gameplay reads.
    const body = createBody();
    this.body = body.group;
    this.bow = body.bow;
    this.object.add(this.body);

    this.runtime = new A3GameRuntimeEntityComponent(this.object, {
      entityId: options.entityId ?? '',
    });

    this.motion = { position: new THREE.Vector3(), velocityY: 0, grounded: true };
    this.desired = new THREE.Vector3();
    this.facing = 0;
    /** Written by the camera rig each frame; read by movement. */
    this.cameraYaw = 0;
    this.pendingJump = false;
    this.running = false;
    this.stamina = this.profile.maxStamina;
    this.drawing = false;
    this.drawTime = 0;
    this.alive = true;
    /** @type {Set<(event: object) => void>} */
    this.listeners = new Set();
  }

  getRuntimeEntityId() {
    return this.runtime.entityId;
  }

  setRuntimeEntityId(entityId) {
    this.runtime.setRuntimeEntityId(entityId);
    return this;
  }

  /** @param {(event: object) => void} listener */
  onEvent(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  applyRuntimeInput(inputState) {
    if (!this.alive) return false;
    if (!this.runtime.applyRuntimeInput(inputState)) return false;

    this.running = Boolean(inputState.run) && this.stamina > 1 && !this.drawing;
    const speed = this.running ? this.profile.runSpeed : this.profile.walkSpeed;

    // Camera-relative basis. `cameraYaw`, not the character's facing:
    // pressing forward has to mean "into the screen" regardless of which
    // way the character currently happens to be turned.
    const forward = new THREE.Vector3(
      -Math.sin(this.cameraYaw),
      0,
      -Math.cos(this.cameraYaw),
    );
    const right = new THREE.Vector3(-forward.z, 0, forward.x);
    this.desired
      .copy(forward)
      .multiplyScalar(Number(inputState.moveY) || 0)
      .addScaledVector(right, Number(inputState.moveX) || 0);
    if (this.desired.lengthSq() > 1) this.desired.normalize();
    this.desired.multiplyScalar(
      speed * (this.drawing ? this.profile.drawMoveFactor : 1),
    );
    if (inputState.jump && !this.drawing) this.pendingJump = true;
    return true;
  }

  tick(delta) {
    if (!this.alive) return;

    if (this.running && this.desired.lengthSq() > 0.01) {
      this.stamina = Math.max(
        0,
        this.stamina - this.profile.staminaDrainPerSecond * delta,
      );
    } else {
      this.stamina = Math.min(
        this.profile.maxStamina,
        this.stamina + this.profile.staminaRefillPerSecond * delta,
      );
    }
    if (this.drawing) this.drawTime += delta;

    const step = this.desired.clone().multiplyScalar(delta);
    if (this.collision) {
      this.collision.stepCharacter(this.motion, step, delta, {
        height: this.profile.eyeHeight,
        jump: this.pendingJump,
        jumpImpulse: this.profile.jumpImpulse,
      });
    } else {
      // No probe: integrate against the height field directly. The example
      // has to run with or without collision geometry, and the terrain
      // function is authoritative either way.
      this.motion.position.add(step);
      if (this.pendingJump && this.motion.grounded) {
        this.motion.velocityY = this.profile.jumpImpulse;
        this.motion.grounded = false;
      }
      this.motion.velocityY += this.profile.gravity * delta;
      this.motion.position.y += this.motion.velocityY * delta;
      const floor = terrainHeight(this.motion.position.x, this.motion.position.z);
      if (this.motion.position.y <= floor) {
        this.motion.position.y = floor;
        this.motion.velocityY = 0;
        this.motion.grounded = true;
      }
    }
    this.pendingJump = false;
    this.object.position.copy(this.motion.position);

    // Facing: towards the camera's aim while drawing, towards travel
    // otherwise. A character that keeps facing its heading while aiming
    // cannot be aimed, and one that snaps to the camera while running
    // looks like it is being dragged.
    const target =
      this.drawing || this.desired.lengthSq() < 0.01
        ? this.cameraYaw
        : Math.atan2(-this.desired.x, -this.desired.z);
    let difference = target - this.facing;
    while (difference > Math.PI) difference -= Math.PI * 2;
    while (difference < -Math.PI) difference += Math.PI * 2;
    this.facing += difference * Math.min(1, delta * this.profile.turnResponse);
    this.body.rotation.y = this.facing;

    // The bow flexes as the shot charges — the only on-screen feedback
    // that holding the key longer is doing anything.
    const charge = this.getDrawRatio();
    this.bow.scale.setScalar(1 + charge * 0.12);
  }

  /** @returns {number} 0..1 charge of the shot currently being drawn. */
  getDrawRatio() {
    if (!this.drawing) return 0;
    return Math.min(1, this.drawTime / this.profile.fullDrawSeconds);
  }

  /** Begin drawing. Returns false if already drawing. */
  startDraw() {
    if (this.drawing || !this.alive) return false;
    this.drawing = true;
    this.drawTime = 0;
    this.#emit({ type: 'draw_started' });
    return true;
  }

  /**
   * Release the shot.
   *
   * @returns {{origin: THREE.Vector3, direction: THREE.Vector3,
   *            speed: number, charge: number} | null}
   */
  releaseDraw() {
    if (!this.drawing) return null;
    const charge = this.getDrawRatio();
    this.drawing = false;
    this.drawTime = 0;

    const origin = new THREE.Vector3(
      HELD_ANCHORS.nock.x,
      HELD_ANCHORS.nock.y,
      HELD_ANCHORS.nock.z,
    )
      .applyAxisAngle(new THREE.Vector3(0, 1, 0), this.facing)
      .add(this.object.position);
    const direction = new THREE.Vector3(
      -Math.sin(this.facing),
      0,
      -Math.cos(this.facing),
    ).normalize();
    const speed =
      this.profile.minArrowSpeed +
      (this.profile.maxArrowSpeed - this.profile.minArrowSpeed) * charge;

    const shot = { origin, direction, speed, charge };
    this.#emit({ type: 'shot_released', charge, speed });
    return shot;
  }

  /** @returns {object} state for the HUD and for tests. */
  getState() {
    return {
      position: this.object.position.toArray().map((v) => Number(v.toFixed(3))),
      facing: Number(this.facing.toFixed(3)),
      grounded: this.motion.grounded,
      running: this.running,
      staminaRatio: Number((this.stamina / this.profile.maxStamina).toFixed(3)),
      drawing: this.drawing,
      drawRatio: Number(this.getDrawRatio().toFixed(3)),
    };
  }

  dispose() {
    this.listeners.clear();
    this.runtime.dispose();
    disposeObject3D(this.object);
  }

  #emit(event) {
    const payload = { ...event, entityId: this.runtime.entityId };
    for (const listener of this.listeners) listener(payload);
  }
}
