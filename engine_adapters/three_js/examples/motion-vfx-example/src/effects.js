/**
 * Reference: how a generated game gets effects into a scene.
 *
 * The mistake this replaces is subtler than the motion one. A game that
 * needs a spark reaches for the obvious thing:
 *
 * ```js
 * const spark = new THREE.Sprite(material);   // one object per spark
 * scene.add(spark);
 * requestAnimationFrame(fade);                // a second render loop
 * ```
 *
 * which produces one draw call per particle, a second animation loop, and
 * nothing disposed — so a firefight degrades the frame rate in proportion
 * to how well the player is doing. `A3GameVfxDirector` is the batched
 * alternative: registered effects, a fixed pool each, one draw call each,
 * one tick, one `dispose()`.
 *
 * The division of labour matters as much as the batching:
 *
 * | Need | Primitive |
 * |---|---|
 * | A burst at a point (impact, muzzle, hit) | `play(name, { position, direction })` |
 * | A stream that tracks something (trail, exhaust, smoke) | `follow(name, object3D, { rate })` |
 * | An instantaneous line (tracer, laser) | `registerBeam` + `fireBeam` |
 * | A continuous streak behind a projectile | `A3GameTrailRibbon` |
 *
 * The last two are separate on purpose. A tracer is not a particle effect:
 * it exists for two frames and has a definite start and end. And particles
 * alone cannot draw a streak — a spark stops moving the instant it is
 * emitted, so what the eye sees behind a fast projectile is a dotted line.
 * A ribbon through the positions the projectile actually occupied is the
 * only thing that reads as speed.
 */

import * as THREE from 'three';
import {
  A3GameTrailRibbon,
  A3GameVfxPreset,
  createVfxDirector,
} from '@a3game/playable';

/**
 * Build the director a shooter needs.
 *
 * Presets are named per game rather than taken wholesale, because the name
 * is what the rest of the game refers to and `'bullet_impact'` survives a
 * change of preset while `A3GameVfxPreset.BULLET_IMPACT` does not.
 *
 * @param {object} host an `A3GameRuntimeHost`
 * @returns {object} the director, already attached to the host tick
 */
export function createShooterEffects(host) {
  const vfx = createVfxDirector({
    host,
    presets: {
      muzzle_flash: A3GameVfxPreset.MUZZLE_FLASH,
      bullet_impact: A3GameVfxPreset.BULLET_IMPACT,
      impact_dust: A3GameVfxPreset.IMPACT_DUST,
      blood_hit: A3GameVfxPreset.BLOOD_HIT,
      // A preset is a plain object, so tuning one is a spread rather than a
      // fork. This is how a game gets its own look without a new file.
      heavy_impact: {
        ...A3GameVfxPreset.BULLET_IMPACT,
        size: [0.04, 0.1],
        speed: [5, 14],
        colorStart: ['#fff0c0', '#ff9c3a'],
      },
    },
  });
  // Outgoing and incoming fire are different colours: two tracers that
  // look the same tell the player nothing about who is shooting.
  vfx.registerBeam('player_tracer', { count: 24, color: 0xffe0a8 });
  vfx.registerBeam('enemy_tracer', { count: 24, color: 0xff6a4a });
  return vfx;
}

/**
 * Resolve one shot's visuals.
 *
 * Note where each piece starts. The flash is at the *muzzle*, not at the
 * camera — a flash at the eye is inside the near plane and invisible. The
 * impact burst points along the surface **normal**, not along the shot:
 * sparks that continue into the wall cannot be seen, which is why
 * `A3GameCollisionProbe.hitscan` reports a world-space normal.
 *
 * @param {object} vfx
 * @param {{muzzle: THREE.Vector3, point: THREE.Vector3,
 *          normal?: THREE.Vector3 | number[] | null,
 *          onBody?: boolean, beam?: string}} shot
 */
export function playShotEffects(vfx, shot) {
  vfx.play('muzzle_flash', {
    position: shot.muzzle,
    direction: shot.point.clone().sub(shot.muzzle).normalize(),
    count: 12,
    scale: 0.6,
  });
  vfx.fireBeam(shot.beam ?? 'player_tracer', shot.muzzle, shot.point, {
    lifetime: 0.05,
  });
  if (shot.onBody) {
    vfx.play('blood_hit', { position: shot.point, count: 12 });
    return;
  }
  vfx.play('bullet_impact', {
    position: shot.point,
    direction: shot.normal ?? [0, 1, 0],
    count: 14,
  });
  vfx.play('impact_dust', { position: shot.point, count: 8 });
}

/**
 * A glowing projectile: emissive body, ribbon, two particle streams.
 *
 * Four layers, because each one fails alone. The mesh is a few pixels
 * wide; the ribbon has no volume; the dense core has no persistence; the
 * slow motes have no shape. Together they read as a light arrow.
 *
 * The ribbon and the emitters live in **world space** rather than being
 * parented to the projectile. That is the whole trick: a parented trail is
 * dragged along by the object it follows, so the streak never forms behind
 * it.
 */
export class ReferenceLightProjectile {
  /**
   * @param {{host: object, vfx: object, origin: THREE.Vector3,
   *          velocity: THREE.Vector3, power?: number}} options
   */
  constructor(options) {
    this.host = options.host;
    this.vfx = options.vfx;
    this.velocity = options.velocity.clone();
    this.power = Number(options.power ?? 1);

    this.vfx.register('projectile_core', A3GameVfxPreset.LIGHT_ARROW_CORE);
    this.vfx.register('projectile_motes', A3GameVfxPreset.LIGHT_ARROW_MOTES);
    this.vfx.register('projectile_impact', A3GameVfxPreset.LIGHT_ARROW_IMPACT);

    this.object = new THREE.Group();
    this.object.add(
      new THREE.Mesh(
        new THREE.ConeGeometry(0.05, 0.4, 8),
        new THREE.MeshStandardMaterial({
          color: 0xffffff,
          emissive: 0x6fc6ff,
          emissiveIntensity: 4,
        }),
      ),
    );
    // A real light, with a short range: the projectile has to illuminate
    // what it passes, and a long-range light in a forest costs more than
    // the effect is worth.
    this.object.add(new THREE.PointLight(0x6fc6ff, 4 + this.power * 6, 6, 2));
    this.object.position.copy(options.origin);
    this.host.add(this.object, 'projectiles');

    this.trail = new A3GameTrailRibbon({
      segments: 26,
      width: 0.1 + this.power * 0.12,
      color: 0xeafcff,
      endColor: 0x1f4fb0,
    });
    this.trail.reset(options.origin);
    this.host.add(this.trail.object3D, 'effects');

    this.core = this.vfx.follow('projectile_core', this.object, { rate: 200 });
    this.motes = this.vfx.follow('projectile_motes', this.object, { rate: 60 });
  }

  /** Advance and lay down another ribbon segment. */
  tick(deltaSeconds) {
    this.object.position.addScaledVector(this.velocity, deltaSeconds);
    this.object.updateMatrixWorld(true);
    this.trail.push(this.object.position, this.host.camera);
    return this;
  }

  /** Burst away from the surface and stop trailing. */
  impact(point, normal) {
    this.vfx.play('projectile_impact', {
      position: point,
      direction: normal,
      spread: 1,
      count: 40,
      scale: 0.8 + this.power * 0.6,
    });
    this.core?.stop();
    this.motes?.stop();
    return this;
  }

  dispose() {
    this.core?.stop();
    this.motes?.stop();
    this.trail.dispose();
    this.object.parent?.remove(this.object);
  }
}

/**
 * A stream whose rate follows a gameplay quantity.
 *
 * Tyre smoke, exhaust, a wound bleeding: all of them are the same shape,
 * and all of them are wrong as a boolean. A handbrake turn at walking pace
 * should produce a chirp, not a cloud, so the emission rate is driven by
 * how hard the tyre is actually working.
 *
 * @param {object} vfx
 * @param {string} name a registered effect
 * @param {THREE.Object3D} marker parented to the moving object
 * @param {() => number} intensity 0 when idle, up to 1 when saturated
 * @returns {(delta: number) => void} call from the host tick
 */
export function createIntensityStream(vfx, name, marker, intensity) {
  const handle = vfx.follow(name, marker, { rate: 0 });
  const system = vfx.get(name);
  return () => {
    if (!system) return;
    const amount = Math.max(0, Math.min(1, Number(intensity()) || 0));
    system.emissionOverTime = amount * 140;
    system.emitting = amount > 0.02;
    if (!handle) return;
  };
}
