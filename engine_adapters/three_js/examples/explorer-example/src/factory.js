/**
 * The explorer's factory, follow camera, and arrows.
 *
 * The follow camera is the part worth reading. In an FPS the camera is the
 * entity and there is nothing to solve; in third person the camera is an
 * independent object with its own state, and getting it wrong is the
 * single most common reason a third-person game feels bad:
 *
 * - it must **lag**, or every small correction of the character shakes the
 *   whole screen;
 * - it must lag *positionally* but track *rotationally* without lag, or
 *   aiming feels like steering a boat;
 * - it must **rise over terrain**, or walking uphill buries the view in
 *   the hillside — which is why it samples the same `terrainHeight` the
 *   character walks on;
 * - it must own the yaw the character's movement is relative to, because
 *   two objects deriving that yaw separately drift apart.
 */

import * as THREE from 'three';
import {
  A3GameEntityFactory,
  createMaterial,
  A3GameMaterialPreset,
  disposeObject3D,
} from '@a3game/playable';
import { ExplorerEntity } from './entity.js';
import { terrainHeight } from './terrain.js';

/**
 * A third-person camera rig.
 *
 * Owns yaw and pitch, and writes yaw back onto the entity so movement and
 * the camera cannot disagree about which way "forward" is.
 */
export class FollowCamera {
  /**
   * @param {{camera: THREE.Camera, target?: object, distance?: number,
   *          height?: number, lag?: number, minPitch?: number,
   *          maxPitch?: number, sensitivity?: number}} options
   */
  constructor(options) {
    this.camera = options.camera;
    this.target = options.target ?? null;
    this.distance = Number(options.distance ?? 6.2);
    this.height = Number(options.height ?? 2.4);
    this.lag = Number(options.lag ?? 9);
    this.minPitch = Number(options.minPitch ?? -0.55);
    this.maxPitch = Number(options.maxPitch ?? 0.85);
    this.sensitivity = Number(options.sensitivity ?? 1);
    this.yaw = 0;
    this.pitch = 0.22;
    this.focus = new THREE.Vector3();
    this.#scratch = new THREE.Vector3();
  }

  /** @param {object} entity an `ExplorerEntity` */
  follow(entity) {
    this.target = entity;
    if (entity) this.focus.copy(entity.object.position);
    return this;
  }

  /**
   * Consume a look delta, in radians.
   *
   * Pitch is clamped rather than wrapped: a third-person camera that can
   * pass over the top of the character inverts the controls at the moment
   * the player is least able to recover from it.
   */
  look(deltaYaw, deltaPitch) {
    this.yaw -= Number(deltaYaw) * this.sensitivity;
    this.pitch = THREE.MathUtils.clamp(
      this.pitch + Number(deltaPitch) * this.sensitivity,
      this.minPitch,
      this.maxPitch,
    );
    return this;
  }

  update(delta) {
    if (!this.target) return;

    // Yaw is published before it is used, so the entity's movement basis
    // this frame is the camera's yaw this frame.
    this.target.cameraYaw = this.yaw;

    // Positional lag only. An exponential ease is frame-rate independent
    // enough for a camera and needs no velocity state.
    const chase = Math.min(1, delta * this.lag);
    this.focus.lerp(
      this.#scratch.copy(this.target.object.position).setY(
        this.target.object.position.y + 1.2,
      ),
      chase,
    );

    const horizontal = Math.cos(this.pitch) * this.distance;
    const desired = new THREE.Vector3(
      this.focus.x + Math.sin(this.yaw) * horizontal,
      this.focus.y + this.height + Math.sin(this.pitch) * this.distance,
      this.focus.z + Math.cos(this.yaw) * horizontal,
    );

    // Never below the ground it is flying over. Cheaper and steadier than
    // a raycast, and it uses the authoritative height field.
    const floor = terrainHeight(desired.x, desired.z) + 0.9;
    desired.y = Math.max(desired.y, floor);

    this.camera.position.copy(desired);
    this.camera.lookAt(this.focus);
  }

  #scratch;
}

/**
 * A pooled arrow set.
 *
 * Pooled because a bow fires often and each arrow is short-lived:
 * allocating a mesh per shot makes the garbage collector stutter the frame
 * rate at exactly the moment the player is aiming.
 */
export class ArrowPool {
  /** @param {{host: object, size?: number, gravity?: number}} options */
  constructor(options) {
    this.host = options.host;
    this.gravity = Number(options.gravity ?? -9.8);
    const material = createMaterial(A3GameMaterialPreset.WOOD, {
      color: 0xd8c48a,
    });
    this.material = material;
    const geometry = new THREE.CylinderGeometry(0.012, 0.012, 0.82, 6);
    geometry.rotateX(Math.PI / 2);
    this.geometry = geometry;

    this.arrows = [];
    for (let index = 0; index < Number(options.size ?? 24); index += 1) {
      const mesh = new THREE.Mesh(geometry, material);
      mesh.name = `arrow_${index}`;
      mesh.visible = false;
      mesh.castShadow = true;
      this.host.add(mesh, 'entities');
      this.arrows.push({
        mesh,
        alive: false,
        velocity: new THREE.Vector3(),
        life: 0,
      });
    }
  }

  /** @param {{origin: THREE.Vector3, direction: THREE.Vector3, speed: number}} shot */
  fire(shot) {
    const arrow = this.arrows.find((item) => !item.alive);
    // A full pool drops the shot rather than growing: an unbounded pool
    // under a stuck fire button is a memory leak with a fuse.
    if (!arrow) return null;
    arrow.alive = true;
    arrow.life = 0;
    arrow.mesh.visible = true;
    arrow.mesh.position.copy(shot.origin);
    arrow.velocity.copy(shot.direction).multiplyScalar(shot.speed);
    // A slight launch elevation, so a flat shot still arcs visibly.
    arrow.velocity.y += shot.speed * 0.06;
    return arrow;
  }

  update(delta) {
    for (const arrow of this.arrows) {
      if (!arrow.alive) continue;
      arrow.life += delta;
      arrow.velocity.y += this.gravity * delta;
      arrow.mesh.position.addScaledVector(arrow.velocity, delta);
      // Point along travel: an arrow that stays level while falling is the
      // clearest possible tell that a projectile is faked.
      arrow.mesh.lookAt(
        arrow.mesh.position.clone().add(arrow.velocity),
      );
      const floor = terrainHeight(arrow.mesh.position.x, arrow.mesh.position.z);
      if (arrow.mesh.position.y <= floor || arrow.life > 6) {
        arrow.alive = false;
        arrow.mesh.visible = false;
      }
    }
  }

  /** @returns {number} how many arrows are in flight. */
  countActive() {
    return this.arrows.filter((arrow) => arrow.alive).length;
  }

  dispose() {
    for (const arrow of this.arrows) disposeObject3D(arrow.mesh);
    this.arrows = [];
    this.geometry.dispose();
    this.material.dispose();
  }
}

export class ExplorerFactory extends A3GameEntityFactory {
  /**
   * @param {{collision?: object, profile?: object,
   *          onEntityEvent?: (event: object) => void}} [options]
   */
  constructor(options = {}) {
    super();
    this.collision = options.collision ?? null;
    this.profile = options.profile ?? {};
    this.onEntityEvent = options.onEntityEvent ?? null;
    /** @type {Map<string, ExplorerEntity>} */
    this.entities = new Map();
  }

  async spawnRuntimeEntity(request, { host }) {
    const entity = new ExplorerEntity({
      host,
      collision: this.collision,
      entityId: request.entityId,
      profile: this.profile,
    });
    const position = request.transform?.position ?? { x: 0, y: 0, z: 0 };
    entity.motion.position.set(
      position.x,
      // Snapped to the terrain rather than trusting the spawn's y. A spawn
      // point authored against a flat plane would otherwise drop the
      // character through a hill or hang it above one.
      terrainHeight(position.x, position.z),
      position.z,
    );
    entity.object.position.copy(entity.motion.position);
    if (this.onEntityEvent) entity.onEvent(this.onEntityEvent);
    this.entities.set(request.entityId || entity.object.name, entity);
    return entity;
  }
}
