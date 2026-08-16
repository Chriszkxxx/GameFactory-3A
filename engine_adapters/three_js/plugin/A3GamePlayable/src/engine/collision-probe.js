/**
 * Raycast-based ground, wall, and hitscan probes.
 *
 * three.js ships no physics engine. Rather than pull in a dependency,
 * the framework supplies the raycast primitives every generated game
 * needs: stay on the ground, do not walk through walls, resolve a
 * hitscan shot. A generated game may still add its own physics library.
 */

import * as THREE from 'three';

const DOWN = new THREE.Vector3(0, -1, 0);

/**
 * Walk up the hierarchy for the nearest runtime entity id.
 *
 * A raycast returns the leaf `Mesh`, but identity is attached to the
 * entity root by `A3GameIdentityComponent` or by the scene loader, so
 * every probe result has to resolve it the same way.
 *
 * @param {THREE.Object3D | null} object
 * @returns {string}
 */
export function resolveEntityId(object) {
  let current = object;
  while (current) {
    const entityId = String(
      current.userData?.a3game?.entityId ??
        current.userData?.a3gameWorldEntity?.entityId ??
        '',
    );
    if (entityId) return entityId;
    current = current.parent;
  }
  return '';
}

export class A3GameCollisionProbe {
  /**
   * @param {{targets?: THREE.Object3D[], groundOffset?: number,
   *          stepHeight?: number, radius?: number,
   *          gravity?: number, maxFallSpeed?: number}} [options]
   */
  constructor(options = {}) {
    /** @type {THREE.Object3D[]} */
    this.targets = [...(options.targets ?? [])];
    this.groundOffset = Number(options.groundOffset ?? 0);
    this.stepHeight = Number(options.stepHeight ?? 0.6);
    this.radius = Number(options.radius ?? 0.4);
    this.gravity = Number(options.gravity ?? -18);
    this.maxFallSpeed = Number(options.maxFallSpeed ?? -40);
    this.raycaster = new THREE.Raycaster();
    this.#scratch = {
      origin: new THREE.Vector3(),
      direction: new THREE.Vector3(),
      move: new THREE.Vector3(),
      point: new THREE.Vector3(),
      box: new THREE.Box3(),
      normalMatrix: new THREE.Matrix3(),
    };
  }

  #scratch;

  /** Replace the collision target list, typically from the scene loader. */
  setTargets(targets = []) {
    this.targets = [...targets];
    return this;
  }

  addTarget(target) {
    if (target) this.targets.push(target);
    return this;
  }

  /** Stop treating an object as a collision target. */
  removeTarget(target) {
    const index = this.targets.indexOf(target);
    if (index >= 0) this.targets.splice(index, 1);
    return this;
  }

  /**
   * Find the ground height under a position.
   *
   * @param {THREE.Vector3} position
   * @param {{maxDrop?: number, probeHeight?: number}} [options]
   * @returns {{hit: boolean, height: number, normal: THREE.Vector3,
   *            object: THREE.Object3D | null, distance: number}}
   */
  sampleGround(position, options = {}) {
    const probeHeight = Number(options.probeHeight ?? this.stepHeight + 0.1);
    const maxDrop = Number(options.maxDrop ?? 50);
    const origin = this.#scratch.origin
      .copy(position)
      .setY(position.y + probeHeight);
    this.raycaster.set(origin, DOWN);
    this.raycaster.near = 0;
    this.raycaster.far = probeHeight + maxDrop;
    const hits = this.raycaster.intersectObjects(this.targets, true);
    if (hits.length === 0) {
      return {
        hit: false,
        height: position.y,
        normal: new THREE.Vector3(0, 1, 0),
        object: null,
        distance: Infinity,
      };
    }
    const hit = hits[0];
    return {
      hit: true,
      height: hit.point.y + this.groundOffset,
      normal: hit.face?.normal?.clone() ?? new THREE.Vector3(0, 1, 0),
      object: hit.object,
      distance: hit.distance,
    };
  }

  /**
   * Resolve a horizontal move against walls.
   *
   * Returns the allowed displacement; blocked axes are zeroed so a
   * character slides along a wall instead of stopping dead.
   *
   * @param {THREE.Vector3} position
   * @param {THREE.Vector3} displacement
   * @param {{height?: number}} [options]
   * @returns {{move: THREE.Vector3, blocked: boolean,
   *            normal: THREE.Vector3 | null}}
   */
  resolveMove(position, displacement, options = {}) {
    const height = Number(options.height ?? 1);
    const move = this.#scratch.move.copy(displacement);
    move.y = 0;
    if (move.lengthSq() < 1e-8) {
      return { move: move.clone(), blocked: false, normal: null };
    }
    const origin = this.#scratch.origin
      .copy(position)
      .setY(position.y + height * 0.5);
    const direction = this.#scratch.direction.copy(move).normalize();
    this.raycaster.set(origin, direction);
    this.raycaster.near = 0;
    this.raycaster.far = move.length() + this.radius;
    const hits = this.raycaster.intersectObjects(this.targets, true);
    if (hits.length === 0) {
      return { move: move.clone(), blocked: false, normal: null };
    }
    const hit = hits[0];
    const normal =
      hit.face?.normal?.clone().transformDirection(hit.object.matrixWorld) ??
      new THREE.Vector3(0, 1, 0);
    // Slide: remove the component of the move that points into the wall.
    const into = normal.clone().multiplyScalar(move.dot(normal));
    const slid = move.clone().sub(into);
    slid.y = 0;
    return { move: slid, blocked: true, normal };
  }

  /**
   * Integrate a simple grounded character step.
   *
   * @param {{position: THREE.Vector3, velocityY: number, grounded: boolean}} state
   * @param {THREE.Vector3} displacement horizontal move for this frame
   * @param {number} deltaSeconds
   * @param {{height?: number, jumpImpulse?: number, jump?: boolean}} [options]
   */
  stepCharacter(state, displacement, deltaSeconds, options = {}) {
    const height = Number(options.height ?? 1);
    const resolved = this.resolveMove(state.position, displacement, {
      height,
    });
    state.position.add(resolved.move);

    let velocityY = Number(state.velocityY ?? 0);
    if (options.jump && state.grounded) {
      velocityY = Number(options.jumpImpulse ?? 6.5);
      state.grounded = false;
    }
    velocityY = Math.max(
      this.maxFallSpeed,
      velocityY + this.gravity * deltaSeconds,
    );
    state.position.y += velocityY * deltaSeconds;

    const ground = this.sampleGround(state.position, {
      probeHeight: this.stepHeight + Math.abs(velocityY * deltaSeconds),
    });
    if (ground.hit && state.position.y <= ground.height) {
      state.position.y = ground.height;
      velocityY = 0;
      state.grounded = true;
    } else if (ground.hit && state.position.y - ground.height < 0.02) {
      state.grounded = true;
    } else {
      state.grounded = false;
    }
    state.velocityY = velocityY;
    return {
      grounded: state.grounded,
      blocked: resolved.blocked,
      groundHeight: ground.height,
      normal: resolved.normal,
    };
  }

  /**
   * Resolve a hitscan shot from an origin along a direction.
   *
   * @param {THREE.Vector3} origin
   * @param {THREE.Vector3} direction
   * @param {{range?: number, ignore?: THREE.Object3D[],
   *          targets?: THREE.Object3D[]}} [options]
   * @returns {{hit: boolean, point: THREE.Vector3 | null,
   *            object: THREE.Object3D | null, distance: number,
   *            entityId: string}}
   */
  hitscan(origin, direction, options = {}) {
    this.raycaster.set(origin, direction.clone().normalize());
    this.raycaster.near = 0;
    this.raycaster.far = Number(options.range ?? 200);
    const ignore = new Set(options.ignore ?? []);
    const hits = this.raycaster
      .intersectObjects(options.targets ?? this.targets, true)
      .filter((item) => {
        let current = item.object;
        while (current) {
          if (ignore.has(current)) return false;
          current = current.parent;
        }
        return true;
      });
    if (hits.length === 0) {
      return {
        hit: false,
        point: null,
        object: null,
        distance: Infinity,
        entityId: '',
        normal: null,
      };
    }
    const hit = hits[0];
    // The surface normal, in world space. `Raycaster` reports the face
    // normal in the hit object's local space, which is not what an impact
    // effect needs: sparks have to fly away from the wall as the wall is
    // oriented in the world, and a rotated prop would otherwise scatter
    // them sideways. Null for geometry without faces, for example a line
    // or a bare marker.
    let normal = null;
    if (hit.face) {
      normal = hit.face.normal
        .clone()
        .applyNormalMatrix(
          this.#scratch.normalMatrix.getNormalMatrix(hit.object.matrixWorld),
        )
        .normalize();
    }
    return {
      hit: true,
      point: hit.point.clone(),
      object: hit.object,
      distance: hit.distance,
      entityId: resolveEntityId(hit.object),
      normal,
    };
  }

  /**
   * Find every target whose world bounds overlap a sphere.
   *
   * Ray casts answer "what is in front of me"; pickups, melee arcs,
   * chest proximity, checkpoints, and explosion radius all need "what is
   * near me" instead. Bounding boxes keep this allocation-light and are
   * exact enough for gameplay volumes.
   *
   * A target that carries no geometry — a bare `Object3D` used as a
   * marker, which is what world spawn points and checkpoints are — is
   * treated as a point at its world position rather than skipped.
   *
   * @param {THREE.Vector3} center
   * @param {number} radius
   * @param {{targets?: THREE.Object3D[], ignore?: THREE.Object3D[],
   *          requireEntityId?: boolean}} [options]
   * @returns {{object: THREE.Object3D, entityId: string,
   *            distance: number}[]} sorted nearest first
   */
  overlapSphere(center, radius, options = {}) {
    const ignore = new Set(options.ignore ?? []);
    const limit = Math.max(0, Number(radius) || 0);
    const found = [];
    for (const target of options.targets ?? this.targets) {
      if (!target || ignore.has(target)) continue;
      target.updateWorldMatrix?.(true, false);
      const box = this.#scratch.box.setFromObject(target);
      let distance;
      if (box.isEmpty()) {
        distance = this.#scratch.point
          .setFromMatrixPosition(target.matrixWorld)
          .distanceTo(center);
      } else {
        distance = box.clampPoint(center, this.#scratch.point).distanceTo(center);
      }
      if (distance > limit) continue;
      const entityId = resolveEntityId(target);
      if (options.requireEntityId && !entityId) continue;
      found.push({ object: target, entityId, distance });
    }
    found.sort((left, right) => left.distance - right.distance);
    return found;
  }

  /**
   * Move a small sphere along a segment and report the first blocker.
   *
   * This is the projectile primitive: an arrow, grenade, or ball moves
   * far enough per frame to tunnel through a thin wall, so gameplay must
   * sweep the travelled segment rather than test the end point.
   *
   * @param {THREE.Vector3} from
   * @param {THREE.Vector3} to
   * @param {{radius?: number, ignore?: THREE.Object3D[],
   *          targets?: THREE.Object3D[]}} [options]
   * @returns {{hit: boolean, point: THREE.Vector3 | null,
   *            normal: THREE.Vector3 | null,
   *            object: THREE.Object3D | null, distance: number,
   *            entityId: string}}
   */
  sweepSphere(from, to, options = {}) {
    const direction = this.#scratch.direction.copy(to).sub(from);
    const travelled = direction.length();
    const miss = {
      hit: false,
      point: null,
      normal: null,
      object: null,
      distance: Infinity,
      entityId: '',
    };
    if (travelled < 1e-6) return miss;
    direction.divideScalar(travelled);
    const padding = Math.max(0, Number(options.radius ?? 0.1));
    this.raycaster.set(from, direction);
    this.raycaster.near = 0;
    this.raycaster.far = travelled + padding;
    const ignore = new Set(options.ignore ?? []);
    const hits = this.raycaster
      .intersectObjects(options.targets ?? this.targets, true)
      .filter((item) => {
        let current = item.object;
        while (current) {
          if (ignore.has(current)) return false;
          current = current.parent;
        }
        return true;
      });
    if (hits.length === 0) return miss;
    const hit = hits[0];
    return {
      hit: true,
      point: hit.point.clone(),
      normal:
        hit.face?.normal?.clone().transformDirection(hit.object.matrixWorld) ??
        null,
      object: hit.object,
      distance: hit.distance,
      entityId: resolveEntityId(hit.object),
    };
  }
}
