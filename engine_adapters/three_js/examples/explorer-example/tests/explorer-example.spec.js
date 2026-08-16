/**
 * Reference generated-test pattern (vitest) for third-person exploration.
 *
 * Generated games must prove behavior without a GPU or screenshots. The
 * pattern is:
 *   1. build the entity directly with fake collision targets;
 *   2. drive it with normalized input frames;
 *   3. step it with an explicit delta;
 *   4. assert observable snapshot and rule state.
 *
 * The cases below are chosen for the things an exploration game gets wrong
 * that a test can actually catch: camera-relative movement, a height field
 * that gameplay and visuals must agree on, and a charge that has to depend
 * on how long a key was held.
 */

import { describe, expect, it, beforeEach } from 'vitest';
import * as THREE from 'three';
import { createRuntimeInputState } from '@a3game/playable';
import { ExplorerEntity, EXPLORER_PROFILE, HELD_ANCHORS } from '../src/explorer.js';
import { ArrowPool } from '../src/arrow.js';
import { FollowCamera } from '../src/index.js';
import {
  buildTerrain,
  buildWorld,
  isBuildable,
  scatterProps,
  terrainHeight,
  WORLD_SIZE,
} from '../src/world.js';

/** Minimal host double: `add` and `onTick` are all an entity needs. */
function createHostDouble() {
  const root = new THREE.Group();
  const tickListeners = new Set();
  return {
    container: null,
    camera: new THREE.PerspectiveCamera(),
    scene: root,
    add(object) {
      root.add(object);
      return object;
    },
    onTick(listener) {
      tickListeners.add(listener);
      return () => tickListeners.delete(listener);
    },
    step(delta) {
      for (const listener of tickListeners) listener(delta, delta);
    },
  };
}

function drive(entity, frame, seconds = 1, step = 1 / 60) {
  for (let elapsed = 0; elapsed < seconds; elapsed += step) {
    entity.applyRuntimeInput(createRuntimeInputState(frame));
    entity.tick(step);
  }
}

describe('world', () => {
  it('is a pure function of position, so every caller agrees', () => {
    expect(terrainHeight(12, -30)).toBe(terrainHeight(12, -30));
  });

  it('leaves a flat clearing at the spawn', () => {
    // Nothing within the clearing may be steep enough to slide on.
    for (const [x, z] of [[0, 0], [4, 0], [0, -4], [-3, 3]]) {
      expect(Math.abs(terrainHeight(x, z))).toBeLessThan(0.5);
    }
  });

  it('rises at the world edge, so the boundary needs no invisible wall', () => {
    const middle = terrainHeight(20, 0);
    const edge = terrainHeight(WORLD_SIZE / 2 - 2, 0);
    expect(edge).toBeGreaterThan(middle + 6);
  });

  it('builds a mesh whose vertices sit on the height field', () => {
    const mesh = buildTerrain({ segments: 24 });
    const position = mesh.geometry.attributes.position;
    // If these disagree the player walks through hills; it is the single
    // most important invariant in the file.
    for (let index = 0; index < position.count; index += 37) {
      const x = position.getX(index);
      const y = position.getY(index);
      const z = position.getZ(index);
      expect(y).toBeCloseTo(terrainHeight(x, z), 5);
    }
    mesh.userData.dispose();
  });

  it('scatters props only on buildable ground, and deterministically', () => {
    const first = scatterProps({ count: 40, seed: 5 });
    const second = scatterProps({ count: 40, seed: 5 });
    expect(first).toEqual(second);
    for (const prop of first) {
      expect(isBuildable(prop.x, prop.z)).toBe(true);
      expect(prop.y).toBeCloseTo(terrainHeight(prop.x, prop.z), 6);
    }
  });

  it('returns fewer props rather than hanging when nothing is buildable', () => {
    const placed = scatterProps({ count: 30, maxSlope: -1 });
    expect(placed).toEqual([]);
  });

  it('assembles a world whose spawn is on the terrain', () => {
    const host = createHostDouble();
    const world = buildWorld(host, { segments: 16, propCount: 5 });
    expect(world.collisionTargets).toContain(world.terrain);
    expect(world.playerSpawn.y).toBeCloseTo(
      terrainHeight(world.playerSpawn.x, world.playerSpawn.z),
      6,
    );
    expect(world.props).toHaveLength(5);
    world.dispose();
  });
});

describe('ExplorerEntity', () => {
  let host;
  let entity;

  beforeEach(() => {
    host = createHostDouble();
    entity = new ExplorerEntity({ host, entityId: 'explorer_test' });
  });

  it('re-derives a spawn point\'s height from the terrain', () => {
    // A spawn authored against a flat plane carries y = 0. Trusting it
    // drops the character through a hill or hangs it above one, so the
    // height is taken from the field and the authored y ignored.
    entity.placeAt({ x: 33, y: 0, z: -21 });
    expect(entity.object.position.y).toBeCloseTo(terrainHeight(33, -21), 6);
    expect(entity.getState().grounded).toBe(true);
  });

  it('moves relative to the camera, not to its own facing', () => {
    // Camera looking down -Z: "forward" must go to -Z.
    entity.cameraYaw = 0;
    drive(entity, { moveY: 1 }, 0.5);
    expect(entity.object.position.z).toBeLessThan(-0.5);

    // Same input, camera turned a quarter turn: the same key must now send
    // the character along -X instead. This is the assertion that fails if
    // someone "simplifies" movement to be facing-relative.
    const turned = new ExplorerEntity({ host, entityId: 'explorer_turned' });
    turned.cameraYaw = Math.PI / 2;
    drive(turned, { moveY: 1 }, 0.5);
    expect(turned.object.position.x).toBeLessThan(-0.5);
    expect(Math.abs(turned.object.position.z)).toBeLessThan(0.5);
  });

  it('hugs the height field wherever it walks', () => {
    entity.cameraYaw = 0.7;
    drive(entity, { moveY: 1, run: true }, 2.5);
    const { x, z } = entity.object.position;
    const floor = terrainHeight(x, z);
    // Not "equal to the floor": walking downhill the character is in free
    // fall for a frame or two while the ground drops away, so a little
    // above is correct. What must never happen is sinking *into* the
    // terrain, or drifting far enough above it to look like flying.
    expect(entity.object.position.y).toBeGreaterThanOrEqual(floor - 1e-6);
    expect(entity.object.position.y - floor).toBeLessThan(0.15);
    expect(entity.getState().grounded).toBe(true);
  });

  it('settles exactly onto the height field when standing still', () => {
    entity.motion.position.set(24, 60, -18);
    drive(entity, {}, 3);
    const { x, z } = entity.object.position;
    expect(entity.object.position.y).toBeCloseTo(terrainHeight(x, z), 6);
  });

  it('spends stamina sprinting and refills it standing still', () => {
    drive(entity, { moveY: 1, run: true }, 2);
    const drained = entity.getState().staminaRatio;
    expect(drained).toBeLessThan(1);
    drive(entity, {}, 2);
    expect(entity.getState().staminaRatio).toBeGreaterThan(drained);
  });

  it('stops sprinting when stamina is gone', () => {
    entity.stamina = 0.5;
    drive(entity, { moveY: 1, run: true }, 0.5);
    expect(entity.getState().running).toBe(false);
  });

  it('charges the shot with how long the key was held', () => {
    entity.startDraw();
    drive(entity, {}, 0.2);
    const quick = entity.releaseDraw();

    entity.startDraw();
    drive(entity, {}, EXPLORER_PROFILE.fullDrawSeconds + 0.3);
    const full = entity.releaseDraw();

    expect(quick.charge).toBeLessThan(full.charge);
    expect(full.charge).toBe(1);
    expect(full.speed).toBeGreaterThan(quick.speed);
    expect(full.speed).toBeCloseTo(EXPLORER_PROFILE.maxArrowSpeed, 5);
  });

  it('caps the charge at a full draw', () => {
    entity.startDraw();
    drive(entity, {}, EXPLORER_PROFILE.fullDrawSeconds * 4);
    expect(entity.getDrawRatio()).toBe(1);
  });

  it('releases nothing when it was never drawing', () => {
    expect(entity.releaseDraw()).toBeNull();
  });

  it('slows down while drawing instead of freezing', () => {
    entity.cameraYaw = 0;
    drive(entity, { moveY: 1 }, 0.5);
    const walked = Math.abs(entity.object.position.z);

    const drawing = new ExplorerEntity({ host, entityId: 'explorer_draw' });
    drawing.cameraYaw = 0;
    drawing.startDraw();
    drive(drawing, { moveY: 1 }, 0.5);
    const drawn = Math.abs(drawing.object.position.z);

    expect(drawn).toBeGreaterThan(0);
    expect(drawn).toBeLessThan(walked);
  });

  it('fires from a nock inside the character silhouette', () => {
    entity.startDraw();
    const shot = entity.releaseDraw();
    const offset = shot.origin.clone().sub(entity.object.position);
    // Held equipment has to stay within arm's reach, or it reads as a prop
    // orbiting the character rather than as something being held.
    expect(Math.hypot(offset.x, offset.z)).toBeLessThan(0.45);
    expect(HELD_ANCHORS.bowSpan).toBeLessThan(0.9);
  });

  it('faces where the camera aims while drawing', () => {
    entity.cameraYaw = 1.1;
    entity.startDraw();
    drive(entity, { moveY: 1 }, 1.5);
    expect(entity.facing).toBeCloseTo(1.1, 1);
  });
});

describe('FollowCamera', () => {
  it('publishes its yaw onto the entity it follows', () => {
    const host = createHostDouble();
    const entity = new ExplorerEntity({ host, entityId: 'explorer_cam' });
    const camera = new FollowCamera({ camera: host.camera }).follow(entity);
    camera.look(0.4, 0);
    camera.update(1 / 60);
    // Two objects deriving this separately is how movement and the view
    // drift apart, so the camera owns it and the entity reads it.
    expect(entity.cameraYaw).toBe(camera.yaw);
  });

  it('clamps pitch so it can never pass over the character', () => {
    const host = createHostDouble();
    const camera = new FollowCamera({ camera: host.camera });
    camera.look(0, 100);
    expect(camera.pitch).toBeLessThanOrEqual(camera.maxPitch);
    camera.look(0, -100);
    expect(camera.pitch).toBeGreaterThanOrEqual(camera.minPitch);
  });

  it('never sinks below the terrain it flies over', () => {
    const host = createHostDouble();
    const entity = new ExplorerEntity({ host, entityId: 'explorer_hill' });
    entity.motion.position.set(40, terrainHeight(40, 40), 40);
    entity.object.position.copy(entity.motion.position);
    const camera = new FollowCamera({ camera: host.camera }).follow(entity);
    // Aim straight down, which is what would otherwise bury the camera.
    camera.look(0, -100);
    for (let step = 0; step < 60; step += 1) camera.update(1 / 60);
    const floor = terrainHeight(host.camera.position.x, host.camera.position.z);
    expect(host.camera.position.y).toBeGreaterThanOrEqual(floor);
  });
});

describe('ArrowPool', () => {
  it('recycles arrows instead of allocating per shot', () => {
    const host = createHostDouble();
    const pool = new ArrowPool({ host, size: 3 });
    const shot = {
      origin: new THREE.Vector3(0, 20, 0),
      direction: new THREE.Vector3(0, 0, -1),
      speed: 30,
    };
    expect(pool.fire(shot)).not.toBeNull();
    expect(pool.fire(shot)).not.toBeNull();
    expect(pool.fire(shot)).not.toBeNull();
    // Full pool drops the shot rather than growing without bound.
    expect(pool.fire(shot)).toBeNull();
    expect(pool.countActive()).toBe(3);
    pool.dispose();
  });

  it('retires an arrow when it reaches the ground', () => {
    const host = createHostDouble();
    const pool = new ArrowPool({ host, size: 2 });
    pool.fire({
      origin: new THREE.Vector3(0, terrainHeight(0, 0) + 0.2, 0),
      direction: new THREE.Vector3(0, -1, 0),
      speed: 20,
    });
    expect(pool.countActive()).toBe(1);
    for (let step = 0; step < 30; step += 1) pool.update(1 / 60);
    expect(pool.countActive()).toBe(0);
    pool.dispose();
  });

  it('gives up on an arrow that never lands', () => {
    const host = createHostDouble();
    const pool = new ArrowPool({ host, size: 2, gravity: 0 });
    pool.fire({
      origin: new THREE.Vector3(0, 400, 0),
      direction: new THREE.Vector3(0, 1, 0),
      speed: 40,
    });
    for (let step = 0; step < 60 * 8; step += 1) pool.update(1 / 60);
    expect(pool.countActive()).toBe(0);
    pool.dispose();
  });
});
