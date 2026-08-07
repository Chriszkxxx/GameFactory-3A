/**
 * Reference generated-test pattern (vitest).
 *
 * Generated games must prove behavior without a GPU or screenshots. The
 * pattern is:
 *   1. build the entity directly with fake collision targets;
 *   2. drive it with normalized input frames;
 *   3. step it with an explicit delta;
 *   4. assert observable snapshot and rule state.
 *
 * `ThreeClient.testing.run_automation_tests()` parses the JSON report
 * this file produces. A zero exit code alone is not success.
 */

import { describe, expect, it, beforeEach } from 'vitest';
import * as THREE from 'three';
import {
  A3GameCollisionProbe,
  A3GameLocomotionState,
  createRuntimeInputState,
} from '@a3game/playable';
import { ArenaFighterEntity } from '../src/entity.js';
import { ArenaFighterEntityFactory, ArenaMatchRules } from '../src/factory.js';

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

/** A large flat ground plane so `stepCharacter` always finds a floor. */
function createGroundProbe() {
  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(200, 200),
    new THREE.MeshBasicMaterial(),
  );
  ground.rotation.x = -Math.PI / 2;
  ground.updateMatrixWorld(true);
  return new A3GameCollisionProbe({ targets: [ground] });
}

function createFighter(host, collision, overrides = {}) {
  const object = new THREE.Object3D();
  object.name = 'fighter_test';
  host.add(object);
  const entity = new ArenaFighterEntity({
    object,
    animations: [],
    host,
    collision,
    ...overrides,
  });
  entity.setRuntimeEntityId(overrides.entityId ?? 'fighter_test');
  return entity;
}

describe('ArenaFighterEntity', () => {
  let host;
  let collision;

  beforeEach(() => {
    host = createHostDouble();
    collision = createGroundProbe();
  });

  it('reports walk locomotion for a partial move frame', () => {
    const fighter = createFighter(host, collision);
    const accepted = fighter.applyRuntimeInput(
      createRuntimeInputState({ moveY: 1, sequence: 1 }),
    );
    expect(accepted).toBe(true);
    expect(fighter.getRuntimeSnapshot().locomotionState).toBe(
      A3GameLocomotionState.WALK,
    );
  });

  it('reports run locomotion when the run flag is set', () => {
    const fighter = createFighter(host, collision);
    fighter.applyRuntimeInput(
      createRuntimeInputState({ moveY: 1, run: true, sequence: 1 }),
    );
    expect(fighter.getRuntimeSnapshot().locomotionState).toBe(
      A3GameLocomotionState.RUN,
    );
  });

  it('drops out-of-order input frames', () => {
    const fighter = createFighter(host, collision);
    expect(
      fighter.applyRuntimeInput(
        createRuntimeInputState({ moveY: 1, sequence: 5 }),
      ),
    ).toBe(true);
    expect(
      fighter.applyRuntimeInput(
        createRuntimeInputState({ moveY: -1, sequence: 3 }),
      ),
    ).toBe(false);
  });

  it('moves forward and stays grounded over several steps', () => {
    const fighter = createFighter(host, collision);
    fighter.applyRuntimeInput(
      createRuntimeInputState({ moveY: 1, yaw: 0, sequence: 1 }),
    );
    for (let index = 0; index < 30; index += 1) fighter.tick(1 / 60);
    expect(fighter.object.position.z).toBeGreaterThan(0.5);
    expect(Math.abs(fighter.object.position.y)).toBeLessThan(0.05);
    expect(fighter.motion.grounded).toBe(true);
  });

  it('advances an attack through windup, active, and recovery', () => {
    const fighter = createFighter(host, collision);
    const events = [];
    fighter.onEvent((event) => events.push(event.type));

    expect(fighter.startAttack('light')).toBe(true);
    expect(fighter.startAttack('light')).toBe(false);
    for (let index = 0; index < 60; index += 1) fighter.tick(1 / 60);

    expect(events).toContain('attack_started');
    expect(events).toContain('attack_active');
    expect(events).toContain('attack_finished');
    expect(fighter.attack).toBeNull();
  });

  it('applies damage once per invulnerability window', () => {
    const fighter = createFighter(host, collision, { maxHealth: 50 });
    expect(fighter.receiveDamage(20, 'other')).toBe(true);
    expect(fighter.receiveDamage(20, 'other')).toBe(false);
    expect(fighter.health).toBe(30);
    fighter.tick(0.3);
    expect(fighter.receiveDamage(40, 'other')).toBe(true);
    expect(fighter.alive).toBe(false);
  });
});

describe('ArenaMatchRules', () => {
  it('resolves a melee hit against an opposing fighter and scores it', () => {
    const host = createHostDouble();
    const collision = createGroundProbe();
    const factory = new ArenaFighterEntityFactory({ collision });
    const rules = new ArenaMatchRules({
      session: null,
      factory,
      roundSeconds: 10,
    });

    const attacker = createFighter(host, collision, {
      entityId: 'attacker',
      teamId: 'team_a',
    });
    const defender = createFighter(host, collision, {
      entityId: 'defender',
      teamId: 'team_b',
      maxHealth: 20,
    });
    // Place the defender inside the attacker's forward reach.
    defender.object.position.set(0, 0, 1.2);
    factory.entities.set('attacker', attacker);
    factory.entities.set('defender', defender);
    attacker.onEvent((event) => rules.handleEntityEvent(event));

    attacker.startAttack('heavy');
    for (let index = 0; index < 90; index += 1) attacker.tick(1 / 60);

    expect(defender.health).toBeLessThan(20);
    const state = rules.getState();
    expect(state.fighters).toHaveLength(2);
    expect(state.aliveCount).toBeLessThanOrEqual(2);
  });

  it('ends the round when the clock expires', () => {
    const factory = new ArenaFighterEntityFactory({
      collision: createGroundProbe(),
    });
    const rules = new ArenaMatchRules({
      session: null,
      factory,
      roundSeconds: 1,
    });
    rules.tick(0.6);
    expect(rules.getState().finished).toBe(false);
    rules.tick(0.6);
    expect(rules.getState().finished).toBe(true);
  });
});
