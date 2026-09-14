/**
 * The strategy camera: an orthographic rig that belongs to nobody.
 *
 * This is the fourth camera family in `examples/`, and the one structural
 * difference is ownership. In the other three the camera is attached to
 * something in the fiction:
 *
 *   first person   the camera *is* the entity
 *   second person  the *match* owns it, framing both fighters
 *   third person   it trails a subject, and publishes the yaw that subject
 *                  moves relative to
 *
 * Here it is attached to nothing. It is a **window onto the map**, moved
 * directly by the player, and no unit ever reads it. That single fact
 * removes the hardest part of a third-person camera — keeping camera yaw and
 * body yaw in agreement — and replaces it with a different requirement:
 * the view must stay legible while it moves, which means no lag and hard
 * bounds.
 *
 * Three deliberate choices:
 *
 * - **Orthographic**, not a perspective camera tilted down. Perspective
 *   makes identical units different sizes across the screen and makes the
 *   selection marquee disagree with what it encloses. Orthographic keeps
 *   scale uniform, which is what makes a screen-space box select correct.
 * - **No positional lag.** A trailing strategy camera feels broken: the
 *   player is aiming a cursor at ground that is still sliding.
 * - **Zoom by frustum height, not by moving the camera.** Moving an
 *   orthographic camera along its view axis changes nothing on screen. The
 *   host exposes `setFrustumHeight` precisely for this.
 *
 * The rig keeps a fixed angle. Rotating a strategy camera is a feature that
 * costs a lot — every screen-space assumption above has to survive it — and
 * StarCraft ships without it.
 */

import * as THREE from 'three';
import { MAP_SIZE, terrainHeight } from './battlefield.js';

/** Metres visible vertically at the default zoom. */
export const DEFAULT_FRUSTUM_HEIGHT = 46;

export const MIN_FRUSTUM_HEIGHT = 18;
export const MAX_FRUSTUM_HEIGHT = 96;

/** Pan speed in metres per second at the default zoom. */
export const PAN_SPEED = 34;

/** Pixels from the viewport edge that trigger edge panning. */
export const EDGE_MARGIN = 24;

/**
 * A top-down orthographic rig.
 *
 * `focus` is the ground point at the centre of the screen; the camera is
 * placed at a fixed offset from it. Storing the focus rather than the camera
 * position is what makes clamping to map bounds meaningful — the player
 * cares that the *map* stays on screen, not where the camera object is.
 */
export class StrategyCamera {
  /**
   * @param {{host: object, frustumHeight?: number, pitch?: number,
   *          yaw?: number, panSpeed?: number, bounds?: number}} options
   */
  constructor(options) {
    this.host = options.host;
    this.camera = options.host.camera;
    this.panSpeed = Number(options.panSpeed ?? PAN_SPEED);
    this.frustumHeight = Number(options.frustumHeight ?? DEFAULT_FRUSTUM_HEIGHT);

    // A fixed three-quarter angle. Steep enough to read the map as a plan,
    // shallow enough that unit silhouettes stay recognisable.
    this.pitch = Number(options.pitch ?? 0.95);
    this.yaw = Number(options.yaw ?? Math.PI * 0.25);

    // Slightly inside the map edge, so the player cannot pan into a void.
    this.bounds = Number(options.bounds ?? MAP_SIZE / 2 - 8);

    this.focus = new THREE.Vector3(0, 0, 0);
    this.height = 60;

    /** Set by whoever tracks the pointer; drives edge panning. */
    this.pointer = null;
  }

  /**
   * Switch the host to an orthographic projection and place the rig.
   *
   * Called once, after `host.init()`. Doing it here rather than in the boot
   * function keeps the whole camera contract in one file.
   */
  attach(focusPoint = { x: 0, z: 0 }) {
    this.host.useOrthographicCamera({
      frustumHeight: this.frustumHeight,
      near: -400,
      far: 400,
    });
    this.camera = this.host.camera;
    this.focus.set(Number(focusPoint.x) || 0, 0, Number(focusPoint.z) || 0);
    this.#apply();
    return this;
  }

  /**
   * Pan by a normalized direction, in screen terms.
   *
   * `x` is right, `y` is up-screen. The vector is rotated by the rig's yaw
   * so that "up" means up-screen rather than world -Z; a rig at 45 degrees
   * whose WASD ignores yaw pans diagonally, which feels broken immediately.
   *
   * Speed scales with zoom, because at a wide zoom a fixed metres-per-second
   * pan feels sluggish while at a tight zoom it overshoots.
   */
  pan(x, y, delta) {
    const dx = Number(x) || 0;
    const dy = Number(y) || 0;
    if (dx === 0 && dy === 0) return this;

    const scale =
      this.panSpeed * delta * (this.frustumHeight / DEFAULT_FRUSTUM_HEIGHT);
    const sin = Math.sin(this.yaw);
    const cos = Math.cos(this.yaw);

    // Screen-right and screen-up projected onto the ground plane.
    this.focus.x += (dx * cos - dy * sin) * scale;
    this.focus.z += (dx * sin + dy * cos) * scale;

    this.focus.x = THREE.MathUtils.clamp(this.focus.x, -this.bounds, this.bounds);
    this.focus.z = THREE.MathUtils.clamp(this.focus.z, -this.bounds, this.bounds);
    this.#apply();
    return this;
  }

  /**
   * Zoom by a wheel delta.
   *
   * Multiplicative, so each notch changes the view by the same *proportion*.
   * An additive step is coarse when zoomed in and imperceptible when zoomed
   * out.
   */
  zoom(wheelDelta) {
    const factor = Math.exp((Number(wheelDelta) || 0) * 0.0015);
    this.setFrustumHeight(this.frustumHeight * factor);
    return this;
  }

  setFrustumHeight(height) {
    this.frustumHeight = THREE.MathUtils.clamp(
      Number(height) || DEFAULT_FRUSTUM_HEIGHT,
      MIN_FRUSTUM_HEIGHT,
      MAX_FRUSTUM_HEIGHT,
    );
    this.host.setFrustumHeight(this.frustumHeight);
    return this;
  }

  /** Centre the view on a world position, e.g. from a minimap click. */
  focusOn(point) {
    this.focus.set(
      THREE.MathUtils.clamp(Number(point?.x) || 0, -this.bounds, this.bounds),
      0,
      THREE.MathUtils.clamp(Number(point?.z) || 0, -this.bounds, this.bounds),
    );
    this.#apply();
    return this;
  }

  /**
   * Per-frame update: keyboard pan plus edge pan.
   *
   * @param {number} delta seconds
   * @param {{x: number, y: number}} axis normalized keyboard pan intent
   * @param {{width: number, height: number}} [viewport]
   */
  update(delta, axis = { x: 0, y: 0 }, viewport = null) {
    let x = Number(axis.x) || 0;
    let y = Number(axis.y) || 0;

    // Edge panning, only while the pointer is actually inside the viewport.
    // Without that guard the view drifts forever once the mouse leaves the
    // canvas, which is the single most reported bug in prototype RTS cameras.
    if (this.pointer && viewport?.width && viewport?.height) {
      const { x: px, y: py } = this.pointer;
      const inside =
        px >= 0 && py >= 0 && px <= viewport.width && py <= viewport.height;
      if (inside) {
        if (px < EDGE_MARGIN) x -= 1;
        else if (px > viewport.width - EDGE_MARGIN) x += 1;
        if (py < EDGE_MARGIN) y += 1;
        else if (py > viewport.height - EDGE_MARGIN) y -= 1;
      }
    }

    if (x !== 0 || y !== 0) {
      const length = Math.hypot(x, y) || 1;
      this.pan(x / length, y / length, delta);
    }
    return this;
  }

  #apply() {
    // Follow the terrain under the focus so the view does not sink into a
    // hill, using the same height field gameplay uses.
    const ground = terrainHeight(this.focus.x, this.focus.z);
    const horizontal = Math.cos(this.pitch) * this.height;
    this.camera.position.set(
      this.focus.x + Math.sin(this.yaw) * horizontal,
      ground + Math.sin(this.pitch) * this.height,
      this.focus.z + Math.cos(this.yaw) * horizontal,
    );
    this.camera.lookAt(this.focus.x, ground, this.focus.z);
  }

  /** @returns {{x: number, z: number, frustumHeight: number}} */
  getState() {
    return {
      x: Number(this.focus.x.toFixed(3)),
      z: Number(this.focus.z.toFixed(3)),
      frustumHeight: Number(this.frustumHeight.toFixed(2)),
    };
  }
}
