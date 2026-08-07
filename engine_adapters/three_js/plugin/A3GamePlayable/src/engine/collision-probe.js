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
   * @param {{range?: number, ignore?: THREE.Object3D[]}} [options]
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
      .intersectObjects(this.targets, true)
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
      };
    }
    const hit = hits[0];
    let entityId = '';
    let current = hit.object;
    while (current && !entityId) {
      entityId = String(
        current.userData?.a3game?.entityId ??
          current.userData?.a3gameWorldEntity?.entityId ??
          '',
      );
      current = current.parent;
    }
    return {
      hit: true,
      point: hit.point.clone(),
      object: hit.object,
      distance: hit.distance,
      entityId,
    };
  }
}
