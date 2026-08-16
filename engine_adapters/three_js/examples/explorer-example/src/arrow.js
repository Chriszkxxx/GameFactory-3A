/**
 * Arrows, as a pool rather than as one object per shot.
 *
 * Pooled because a bow fires often and each arrow is short-lived:
 * allocating a mesh and a material per shot makes the garbage collector
 * stutter the frame rate at exactly the moment the player is aiming, which
 * is the worst possible moment for it.
 *
 * The pool is also why this is its own module. Arrows outlive the shot that
 * created them and are ticked independently of the explorer, so they are
 * not part of the character; and they need the height field, so they are
 * not part of the boot sequence either.
 */

import * as THREE from 'three';
import {
  createMaterial,
  A3GameMaterialPreset,
  disposeObject3D,
} from '@a3game/playable';
import { terrainHeight } from './world.js';

/** Flight tuning. Metres, seconds, metres per second. */
export const ARROW_PROFILE = Object.freeze({
  gravity: -9.8,
  /** Seconds before an arrow that never lands is retired anyway. */
  maxLifeSeconds: 6,
  /** Fraction of launch speed added as upward elevation. */
  launchElevation: 0.06,
  length: 0.82,
  radius: 0.012,
});

export class ArrowPool {
  /**
   * @param {{host: object, size?: number, gravity?: number,
   *          profile?: object}} options
   */
  constructor(options) {
    this.host = options.host;
    this.profile = { ...ARROW_PROFILE, ...(options.profile ?? {}) };
    // An explicit `gravity` still wins, because the tests need to switch it
    // off to prove the lifetime cap works at all.
    if (options.gravity !== undefined) {
      this.profile = { ...this.profile, gravity: Number(options.gravity) };
    }

    // One geometry and one material for every arrow, which is the other
    // half of pooling: 24 meshes sharing them cost one upload, not 24.
    const material = createMaterial(A3GameMaterialPreset.WOOD, {
      color: 0xd8c48a,
    });
    this.material = material;
    const geometry = new THREE.CylinderGeometry(
      this.profile.radius,
      this.profile.radius,
      this.profile.length,
      6,
    );
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

  /**
   * Launch an arrow, if one is free.
   *
   * @param {{origin: THREE.Vector3, direction: THREE.Vector3,
   *          speed: number}} shot as returned by `ExplorerEntity.releaseDraw`
   * @returns {object | null} null when every arrow is in flight
   */
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
    arrow.velocity.y += shot.speed * this.profile.launchElevation;
    return arrow;
  }

  update(delta) {
    for (const arrow of this.arrows) {
      if (!arrow.alive) continue;
      arrow.life += delta;
      arrow.velocity.y += this.profile.gravity * delta;
      arrow.mesh.position.addScaledVector(arrow.velocity, delta);
      // Point along travel: an arrow that stays level while falling is the
      // clearest possible tell that a projectile is faked.
      arrow.mesh.lookAt(arrow.mesh.position.clone().add(arrow.velocity));

      const floor = terrainHeight(arrow.mesh.position.x, arrow.mesh.position.z);
      if (
        arrow.mesh.position.y <= floor ||
        arrow.life > this.profile.maxLifeSeconds
      ) {
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
