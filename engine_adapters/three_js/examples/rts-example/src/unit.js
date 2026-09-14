/**
 * A unit: the thing that executes orders.
 *
 * Compare with `explorer.js` in the exploration example. That entity reads
 * `moveX/moveY` off an input frame and moves. This one **ignores movement
 * input entirely** and instead re-derives its own velocity from whatever
 * order sits at the head of its queue.
 *
 * It still implements `A3GameControllableEntity`, because the runtime
 * subsystem needs a uniform way to spawn, identify, and snapshot entities.
 * But `applyRuntimeInput` deliberately does **not** steer the body: in a
 * strategy game the human's input frame belongs to the camera, and a unit
 * that also consumed it would drift whenever the player panned. The method
 * is kept as the contract's seam for a future scripted or networked
 * controller, and it says so rather than pretending to be unused.
 *
 * Combat is deliberately minimal — a cooldown, a range test, a damage
 * number. The point of the example is the control model, and a real damage
 * formula would only obscure it.
 */

import * as THREE from 'three';
import {
  A3GameControllableEntity,
  createEntitySnapshot,
  createSurfaceMaterial,
} from '@a3game/playable';
import { isPassable, terrainHeight } from './battlefield.js';
import { ARRIVAL_TOLERANCE, OrderKind, OrderQueue } from './commands.js';

/** Teams. `PLAYER` is the only one the local human may select. */
export const Team = Object.freeze({
  PLAYER: 'player',
  ENEMY: 'enemy',
});

/** Tunables for the one unit type this example ships. */
export const UNIT_PROFILE = Object.freeze({
  maxHealth: 100,
  speed: 6.5,
  turnRate: 9,
  radius: 0.45,
  height: 1.7,
  visionRadius: 18,
  attackRange: 7,
  attackDamage: 9,
  attackInterval: 0.85,
  /** Auto-acquire an enemy that wanders this close while idle. */
  aggroRadius: 11,
});

let unitCounter = 0;

/** Reusable scratch vectors, so the hot loop allocates nothing. */
const _toTarget = new THREE.Vector3();
const _step = new THREE.Vector3();

export class Unit extends A3GameControllableEntity {
  /**
   * @param {{host: object, team?: string, entityId?: string,
   *          profile?: object, world?: object}} options
   */
  constructor(options) {
    super();
    this.host = options.host;
    this.team = options.team ?? Team.PLAYER;
    this.profile = { ...UNIT_PROFILE, ...(options.profile ?? {}) };
    this.world = options.world ?? null;

    unitCounter += 1;
    this.unitId = options.entityId || `unit_${unitCounter}`;
    this.runtimeEntityId = this.unitId;

    this.orders = new OrderQueue();
    this.health = this.profile.maxHealth;
    this.alive = true;
    this.selected = false;
    this.attackCooldown = 0;
    this.yaw = 0;

    /** Resolves a target id to a live unit. Injected by the army. */
    this.resolveTarget = null;
    /** Finds the nearest live enemy within a radius. Injected by the army. */
    this.findEnemy = null;

    this.object = this.#build();
    if (this.host?.add) this.host.add(this.object, 'entities');
  }

  #build() {
    const group = new THREE.Group();
    group.name = this.unitId;

    const isPlayer = this.team === Team.PLAYER;
    const body = new THREE.Mesh(
      new THREE.CapsuleGeometry(
        this.profile.radius,
        this.profile.height - this.profile.radius * 2,
        4,
        8,
      ),
      createSurfaceMaterial({
        preset: 'metal',
        color: isPlayer ? 0x4d8fd6 : 0xd05c4a,
        roughness: 0.55,
      }),
    );
    body.castShadow = true;
    body.position.y = this.profile.height / 2;
    group.add(body);
    this.body = body;

    // A facing wedge. Without a visible front, a group of capsules gives no
    // feedback that an order was received until the whole formation moves.
    const nose = new THREE.Mesh(
      new THREE.ConeGeometry(this.profile.radius * 0.55, 0.5, 6),
      body.material,
    );
    nose.rotation.x = Math.PI / 2;
    nose.position.set(0, this.profile.height * 0.62, -this.profile.radius - 0.2);
    group.add(nose);

    // Selection ring, hidden until selected. Pre-built rather than created
    // on selection: allocating meshes during a drag-select of fifty units
    // is a visible hitch.
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(this.profile.radius + 0.2, this.profile.radius + 0.4, 24),
      new THREE.MeshBasicMaterial({
        color: 0x8ef58a,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.95,
      }),
    );
    ring.rotation.x = -Math.PI / 2;
    ring.position.y = 0.06;
    ring.visible = false;
    group.add(ring);
    this.selectionRing = ring;

    return group;
  }

  /** @returns {THREE.Vector3} live position; do not mutate. */
  get position() {
    return this.object.position;
  }

  placeAt(point) {
    const x = Number(point?.x) || 0;
    const z = Number(point?.z) || 0;
    this.object.position.set(x, terrainHeight(x, z), z);
    return this;
  }

  setSelected(selected) {
    this.selected = Boolean(selected);
    this.selectionRing.visible = this.selected;
    return this;
  }

  // -- A3GameControllableEntity ---------------------------------------------

  getRuntimeEntityId() {
    return this.runtimeEntityId;
  }

  setRuntimeEntityId(entityId) {
    this.runtimeEntityId = entityId || this.unitId;
    return this;
  }

  /**
   * Contract seam, intentionally not used for movement.
   *
   * A strategy unit is driven by its order queue. The local human's input
   * frame drives the camera, so consuming `moveX/moveY` here would make
   * every selected unit drift while the player pans. Only the sequence
   * number is tracked, so a networked or scripted controller can later
   * attach here without re-plumbing the entity.
   */
  applyRuntimeInput(input) {
    this.lastInputSequence = Number(input?.sequence) || 0;
    return this;
  }

  /**
   * Observable state, for tests and the runtime bridge.
   *
   * `createEntitySnapshot` has a fixed shape — `position` and `rotation` are
   * top level, and there is no `metadata` field, so anything extra passed to
   * it is silently dropped. Strategy state that a test needs to assert on
   * (team, health, the current order) is therefore returned alongside the
   * normalized snapshot rather than inside it.
   */
  getRuntimeSnapshot() {
    const order = this.orders.current();
    return {
      ...createEntitySnapshot({
        entityId: this.runtimeEntityId,
        objectName: this.object.name,
        position: {
          x: this.object.position.x,
          y: this.object.position.y,
          z: this.object.position.z,
        },
        rotation: { x: 0, y: this.yaw, z: 0 },
        locomotionState: order?.kind === OrderKind.MOVE ? 'run' : 'idle',
        lastInputTimeSeconds: this.lastInputSequence ?? 0,
      }),
      team: this.team,
      health: this.health,
      alive: this.alive,
      selected: this.selected,
      orderKind: order?.kind ?? 'idle',
      queueLength: this.orders.length,
    };
  }

  // -- Simulation -----------------------------------------------------------

  /**
   * Advance one simulation step.
   *
   * Order of business matters: resolve the current order into a desired
   * destination, move toward it, then test for completion. Testing before
   * moving reports arrival one step late and lets the unit overshoot.
   */
  tick(delta) {
    if (!this.alive) return;

    this.attackCooldown = Math.max(0, this.attackCooldown - delta);

    let order = this.orders.current();

    // Idle units defend themselves. Without this an army walks past enemies
    // that are shooting it, which reads as broken rather than as obedient.
    if (!order && this.findEnemy) {
      const nearby = this.findEnemy(this, this.profile.aggroRadius);
      if (nearby) {
        this.orders.issue({
          kind: OrderKind.ATTACK,
          x: nearby.position.x,
          z: nearby.position.z,
          targetId: nearby.unitId,
        });
        order = this.orders.current();
      }
    }

    if (!order) return;

    if (order.kind === OrderKind.STOP) {
      this.orders.complete();
      return;
    }

    if (order.kind === OrderKind.ATTACK) {
      this.#tickAttack(order, delta);
      return;
    }

    if (order.kind === OrderKind.MOVE) {
      const arrived = this.#moveToward(order.x, order.z, delta);
      if (arrived) this.orders.complete();
    }
  }

  #tickAttack(order, delta) {
    const target = this.resolveTarget ? this.resolveTarget(order.targetId) : null;

    // A dead or unresolvable target ends the order rather than freezing it.
    if (!target || !target.alive) {
      this.orders.complete();
      return;
    }

    const distance = Math.hypot(
      target.position.x - this.object.position.x,
      target.position.z - this.object.position.z,
    );

    if (distance > this.profile.attackRange) {
      // Chase. The destination is recomputed every step because the target
      // is moving; a cached point would walk to where it used to be.
      this.#moveToward(target.position.x, target.position.z, delta);
      return;
    }

    this.#faceToward(target.position.x, target.position.z, delta);
    if (this.attackCooldown > 0) return;
    this.attackCooldown = this.profile.attackInterval;
    target.applyDamage(this.profile.attackDamage, this);
  }

  /**
   * Step toward a world position.
   *
   * @returns {boolean} whether the destination has been reached
   */
  #moveToward(x, z, delta) {
    const position = this.object.position;
    _toTarget.set(x - position.x, 0, z - position.z);
    const distance = _toTarget.length();
    if (distance <= ARRIVAL_TOLERANCE) return true;

    this.#faceToward(x, z, delta);

    const travel = Math.min(distance, this.profile.speed * delta);
    _step.copy(_toTarget).multiplyScalar(travel / distance);
    const nextX = position.x + _step.x;
    const nextZ = position.z + _step.z;

    // Blocked ground ends the order instead of leaving the unit grinding
    // into a cliff for the rest of the match.
    if (!isPassable(nextX, nextZ)) return true;

    position.set(nextX, terrainHeight(nextX, nextZ), nextZ);
    return false;
  }

  /** Rotate toward a world position at a bounded turn rate. */
  #faceToward(x, z, delta) {
    const desired = Math.atan2(
      x - this.object.position.x,
      z - this.object.position.z,
    );
    // Shortest-arc interpolation. Lerping raw angles spins the long way
    // round whenever the difference crosses PI.
    let difference = desired - this.yaw;
    while (difference > Math.PI) difference -= Math.PI * 2;
    while (difference < -Math.PI) difference += Math.PI * 2;
    this.yaw += difference * Math.min(1, this.profile.turnRate * delta);
    this.object.rotation.y = this.yaw;
  }

  /** Apply damage. @returns {boolean} whether this killed the unit. */
  applyDamage(amount, source = null) {
    if (!this.alive) return false;
    this.health = Math.max(0, this.health - (Number(amount) || 0));

    // Being shot by something out of sight is the trigger for retaliation,
    // and it is also how an idle defender acquires a target that outranges
    // its own aggro radius.
    if (source && this.alive && !this.orders.current()) {
      this.orders.issue({
        kind: OrderKind.ATTACK,
        x: source.position.x,
        z: source.position.z,
        targetId: source.unitId,
      });
    }

    if (this.health > 0) return false;
    this.alive = false;
    this.orders.clear();
    this.object.visible = false;
    this.setSelected(false);
    return true;
  }

  get healthRatio() {
    return this.profile.maxHealth > 0
      ? this.health / this.profile.maxHealth
      : 0;
  }

  dispose() {
    this.body.geometry.dispose();
    this.body.material.dispose();
    this.selectionRing.geometry.dispose();
    this.selectionRing.material.dispose();
    if (this.host?.remove) this.host.remove(this.object);
  }
}
