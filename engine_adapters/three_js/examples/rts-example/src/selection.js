/**
 * Selection: the other half of the strategy input model.
 *
 * Commands answer "do what", selection answers "who". Together they replace
 * the per-frame steering the other examples use.
 *
 * Two things here are easy to get subtly wrong.
 *
 * **Box select must be done in screen space, not world space.** The
 * tempting version builds a world-space box from the drag's start and end
 * ground points and tests unit positions against it. That version behaves
 * differently depending on camera angle and silently misses units on raised
 * ground, because the ground point under the cursor is not the unit's
 * position. Projecting each unit to normalized device coordinates and
 * testing against the screen rectangle is both simpler and correct: it
 * selects exactly what the player drew a box around.
 *
 * **A drag and a click are the same gesture until they are not.** A press
 * followed by a release within a few pixels is a click (pick one unit);
 * beyond that it is a box. Deciding on `pointerdown` is impossible, so the
 * decision is deferred to `pointerup` and the threshold is explicit.
 */

import * as THREE from 'three';

/** Drag distance in pixels beyond which a gesture is a box, not a click. */
export const DRAG_THRESHOLD = 6;

const _projected = new THREE.Vector3();

/**
 * Tracks the current selection and the in-progress drag rectangle.
 *
 * Owns no DOM: the marquee is drawn by whoever supplies `onRectChange`, so
 * this class stays testable without a browser.
 */
export class SelectionModel {
  /**
   * @param {{camera: THREE.Camera, container?: HTMLElement,
   *          onRectChange?: (rect: object | null) => void,
   *          onChange?: (units: object[]) => void}} options
   */
  constructor(options) {
    this.camera = options.camera;
    this.container = options.container ?? null;
    this.onRectChange = options.onRectChange ?? null;
    this.onChange = options.onChange ?? null;

    /** @type {Set<object>} */
    this.selected = new Set();
    /** @type {{x: number, y: number} | null} */
    this.dragStart = null;
    this.dragCurrent = null;
    this.dragging = false;
  }

  /** @returns {object[]} live selected units, in insertion order. */
  list() {
    return [...this.selected].filter((unit) => unit.alive);
  }

  get size() {
    return this.list().length;
  }

  /** Replace the selection. */
  set(units) {
    for (const unit of this.selected) unit.setSelected(false);
    this.selected.clear();
    for (const unit of units ?? []) {
      if (!unit?.alive) continue;
      unit.setSelected(true);
      this.selected.add(unit);
    }
    this.onChange?.(this.list());
    return this;
  }

  /** Add to the selection, for shift-click accumulation. */
  add(units) {
    for (const unit of units ?? []) {
      if (!unit?.alive) continue;
      unit.setSelected(true);
      this.selected.add(unit);
    }
    this.onChange?.(this.list());
    return this;
  }

  clear() {
    return this.set([]);
  }

  /** Drop dead units. Called after combat so rings do not outlive bodies. */
  prune() {
    let changed = false;
    for (const unit of [...this.selected]) {
      if (unit.alive) continue;
      unit.setSelected(false);
      this.selected.delete(unit);
      changed = true;
    }
    if (changed) this.onChange?.(this.list());
    return this;
  }

  // -- Gesture --------------------------------------------------------------

  beginDrag(event) {
    this.dragStart = this.#localPoint(event);
    this.dragCurrent = { ...this.dragStart };
    this.dragging = false;
    return this;
  }

  updateDrag(event) {
    if (!this.dragStart) return this;
    this.dragCurrent = this.#localPoint(event);
    const distance = Math.hypot(
      this.dragCurrent.x - this.dragStart.x,
      this.dragCurrent.y - this.dragStart.y,
    );
    // Only becomes a drag once, and never reverts, so a jittery mouse near
    // the threshold cannot flicker the marquee on and off.
    if (!this.dragging && distance > DRAG_THRESHOLD) this.dragging = true;
    if (this.dragging) this.onRectChange?.(this.rect());
    return this;
  }

  /**
   * Finish the gesture.
   *
   * @returns {{kind: 'click' | 'box', rect: object | null}}
   */
  endDrag() {
    const wasDragging = this.dragging;
    const rect = wasDragging ? this.rect() : null;
    this.dragStart = null;
    this.dragCurrent = null;
    this.dragging = false;
    this.onRectChange?.(null);
    return { kind: wasDragging ? 'box' : 'click', rect };
  }

  /** @returns {{left: number, top: number, right: number, bottom: number} | null} */
  rect() {
    if (!this.dragStart || !this.dragCurrent) return null;
    return {
      left: Math.min(this.dragStart.x, this.dragCurrent.x),
      right: Math.max(this.dragStart.x, this.dragCurrent.x),
      top: Math.min(this.dragStart.y, this.dragCurrent.y),
      bottom: Math.max(this.dragStart.y, this.dragCurrent.y),
    };
  }

  #localPoint(event) {
    const bounds = this.container?.getBoundingClientRect?.();
    return {
      x: (event?.clientX ?? 0) - (bounds?.left ?? 0),
      y: (event?.clientY ?? 0) - (bounds?.top ?? 0),
    };
  }
}

/**
 * Units whose screen position falls inside a screen-space rectangle.
 *
 * `viewport` is the container's pixel size, so this stays independent of
 * the DOM and can be unit-tested with plain numbers.
 *
 * @param {object[]} units candidates, normally one team's roster
 * @param {{left: number, top: number, right: number, bottom: number}} rect
 * @param {THREE.Camera} camera
 * @param {{width: number, height: number}} viewport
 * @returns {object[]}
 */
export function unitsInScreenRect(units, rect, camera, viewport) {
  if (!rect || !viewport?.width || !viewport?.height) return [];
  const hits = [];
  for (const unit of units ?? []) {
    if (!unit?.alive) continue;
    const screen = projectToScreen(unit, camera, viewport);
    if (!screen) continue;
    if (
      screen.x >= rect.left &&
      screen.x <= rect.right &&
      screen.y >= rect.top &&
      screen.y <= rect.bottom
    ) {
      hits.push(unit);
    }
  }
  return hits;
}

/**
 * Project a unit's centre of mass to container pixels.
 *
 * Its mid-height rather than its feet: a box drawn around visible bodies
 * should catch them, and feet sit below the silhouette the player sees.
 *
 * @returns {{x: number, y: number} | null} null when behind the camera
 */
export function projectToScreen(unit, camera, viewport) {
  _projected.set(
    unit.position.x,
    unit.position.y + (unit.profile?.height ?? 1.7) * 0.5,
    unit.position.z,
  );
  _projected.project(camera);
  // Behind the camera. Orthographic strategy cameras rarely produce this,
  // but a perspective debug camera will, and it would otherwise select
  // units the player cannot see.
  if (_projected.z > 1) return null;
  return {
    x: ((_projected.x + 1) / 2) * viewport.width,
    y: ((1 - _projected.y) / 2) * viewport.height,
  };
}

/**
 * The unit nearest a screen point, within a pixel radius.
 *
 * Screen-space proximity rather than a raycast against unit meshes, for two
 * reasons: it needs no colliders, and it forgives imprecise clicks on the
 * small silhouettes a zoomed-out strategy camera produces. A raycast
 * demands pixel-accurate hits, which is why click-to-select feels stiff in
 * prototypes that use one.
 *
 * @returns {object | null}
 */
export function unitAtScreenPoint(units, point, camera, viewport, radius = 22) {
  let best = null;
  let bestDistance = radius;
  for (const unit of units ?? []) {
    if (!unit?.alive) continue;
    const screen = projectToScreen(unit, camera, viewport);
    if (!screen) continue;
    const distance = Math.hypot(screen.x - point.x, screen.y - point.y);
    if (distance < bestDistance) {
      best = unit;
      bestDistance = distance;
    }
  }
  return best;
}
