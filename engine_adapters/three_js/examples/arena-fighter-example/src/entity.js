/**
 * Concrete arena fighter entity.
 *
 * Demonstrates the boundary: the framework hands over a normalized input
 * frame; this class decides what "move", "run", and "attack" mean.
 */

import * as THREE from 'three';
import {
  A3GameAnimationDirector,
  A3GameControllableEntity,
  A3GameLocomotionState,
  A3GameRuntimeEntityComponent,
  disposeObject3D,
} from '@a3game/playable';

const ATTACKS = Object.freeze({
  light: { damage: 8, windup: 0.12, active: 0.16, recovery: 0.22, reach: 1.9 },
  heavy: { damage: 21, windup: 0.32, active: 0.2, recovery: 0.46, reach: 2.4 },
});

export class ArenaFighterEntity extends A3GameControllableEntity {
  /**
   * @param {{object: THREE.Object3D, animations?: THREE.AnimationClip[],
   *          host: object, collision: object, teamId?: string,
   *          maxHealth?: number, walkSpeed?: number, runSpeed?: number}} options
   */
  constructor(options) {
    super();
    this.object = options.object;
    this.host = options.host;
    this.collision = options.collision;
    this.teamId = String(options.teamId ?? 'team_a');
    this.maxHealth = Number(options.maxHealth ?? 100);
    this.health = this.maxHealth;
    this.walkSpeed = Number(options.walkSpeed ?? 2.6);
    this.runSpeed = Number(options.runSpeed ?? 5.4);
    this.turnRate = 12;

    this.runtime = new A3GameRuntimeEntityComponent(this.object, {
      persistent: true,
    });
    this.animation = new A3GameAnimationDirector(
      this.object,
      options.animations ?? [],
    );
    this.animation.mapStates({
      idle: 'idle',
      walk: 'walk',
      run: 'run',
      jump: 'jump',
      attack_light: 'attack',
      attack_heavy: 'attack',
      hit: 'hit',
      death: 'death',
    });

    this.motion = {
      position: this.object.position.clone(),
      velocityY: 0,
      grounded: true,
    };
    this.desired = new THREE.Vector3();
    this.attack = null;
    this.attackCooldown = 0;
    this.invulnerable = 0;
    this.alive = true;
    /** @type {Set<(event: object) => void>} */
    this.eventListeners = new Set();
  }

  // --- A3GameControllableEntity ------------------------------------

  getRuntimeEntityId() {
    return this.runtime.entityId;
  }

  setRuntimeEntityId(entityId) {
    this.runtime.setRuntimeEntityId(entityId);
    return this;
  }

  applyRuntimeInput(inputState) {
    if (!this.alive) return false;
    if (!this.runtime.applyRuntimeInput(inputState)) return false;
    // Camera-relative movement: yaw comes from the input frame so the
    // same rule works for keyboard, gamepad, and remote control.
    const speed = inputState.run ? this.runSpeed : this.walkSpeed;
    const forward = new THREE.Vector3(
      Math.sin(inputState.yaw),
      0,
      Math.cos(inputState.yaw),
    );
    const right = new THREE.Vector3(forward.z, 0, -forward.x);
    this.desired
      .copy(forward)
      .multiplyScalar(inputState.moveY)
      .addScaledVector(right, inputState.moveX);
    if (this.desired.lengthSq() > 1) this.desired.normalize();
    this.desired.multiplyScalar(speed);
    this.pendingJump = Boolean(inputState.jump);
    return true;
  }

  getRuntimeSnapshot() {
    const snapshot = this.runtime.getRuntimeSnapshot();
    return {
      ...snapshot,
      // Game-specific state travels in the generic `motionState` field
      // so the framework contract stays unchanged.
      motionState: this.attack
        ? `attack_${this.attack.kind}_${this.attack.phase}`
        : snapshot.motionState,
    };
  }

  tick(deltaSeconds) {
    if (!this.alive) {
      this.animation.update(deltaSeconds);
      return;
    }
    this.attackCooldown = Math.max(0, this.attackCooldown - deltaSeconds);
    this.invulnerable = Math.max(0, this.invulnerable - deltaSeconds);
    this.#advanceAttack(deltaSeconds);

    const locked = this.attack !== null;
    const displacement = locked
      ? new THREE.Vector3()
      : this.desired.clone().multiplyScalar(deltaSeconds);
    const result = this.collision.stepCharacter(
      this.motion,
      displacement,
      deltaSeconds,
      {
        height: 1.7,
        jump: this.pendingJump && !locked,
        jumpImpulse: 6.2,
      },
    );
    this.pendingJump = false;
    this.object.position.copy(this.motion.position);

    if (!locked && this.desired.lengthSq() > 1e-4) {
      const targetYaw = Math.atan2(this.desired.x, this.desired.z);
      this.object.rotation.y = dampAngle(
        this.object.rotation.y,
        targetYaw,
        this.turnRate,
        deltaSeconds,
      );
    }

    if (!locked) {
      const state = result.grounded
        ? this.runtime.locomotionState
        : A3GameLocomotionState.JUMP;
      this.animation.play(state);
    }
    this.animation.update(deltaSeconds);
  }

  dispose() {
    this.eventListeners.clear();
    this.animation.dispose();
    this.runtime.dispose();
    disposeObject3D(this.object);
  }

  // --- Arena fighter rules -----------------------------------------

  /** @param {(event: object) => void} listener */
  onEvent(listener) {
    this.eventListeners.add(listener);
    return () => this.eventListeners.delete(listener);
  }

  /**
   * Begin one attack. Returns false when locked out.
   *
   * @param {'light' | 'heavy'} kind
   */
  startAttack(kind) {
    const profile = ATTACKS[kind];
    if (!profile || !this.alive) return false;
    if (this.attack || this.attackCooldown > 0) return false;
    this.attack = { kind, phase: 'windup', timer: profile.windup, profile };
    this.runtime.setMotionState(`attack_${kind}`);
    this.animation.playOnce(`attack_${kind}`, { timeScale: 1.1 });
    this.#emit({ type: 'attack_started', kind });
    return true;
  }

  /**
   * Apply damage from another entity.
   *
   * @param {number} amount
   * @param {string} sourceEntityId
   */
  receiveDamage(amount, sourceEntityId = '') {
    if (!this.alive || this.invulnerable > 0) return false;
    this.health = Math.max(0, this.health - Math.max(0, Number(amount) || 0));
    this.invulnerable = 0.25;
    this.#emit({
      type: 'damaged',
      amount,
      sourceEntityId,
      health: this.health,
      healthRatio: this.health / this.maxHealth,
    });
    if (this.health <= 0) {
      this.alive = false;
      this.attack = null;
      this.runtime.setMotionState('death');
      this.animation.play('death', { loop: false, clampWhenFinished: true });
      this.#emit({ type: 'died', sourceEntityId });
    } else {
      this.animation.playOnce('hit');
    }
    return true;
  }

  /** @returns {{origin: THREE.Vector3, direction: THREE.Vector3, reach: number}} */
  getAttackVolume() {
    const direction = new THREE.Vector3(
      Math.sin(this.object.rotation.y),
      0,
      Math.cos(this.object.rotation.y),
    );
    const origin = this.object.position
      .clone()
      .add(new THREE.Vector3(0, 1.1, 0));
    return {
      origin,
      direction,
      reach: this.attack?.profile.reach ?? ATTACKS.light.reach,
    };
  }

  #advanceAttack(deltaSeconds) {
    if (!this.attack) return;
    this.attack.timer -= deltaSeconds;
    if (this.attack.timer > 0) return;
    const { kind, phase, profile } = this.attack;
    if (phase === 'windup') {
      this.attack = { kind, phase: 'active', timer: profile.active, profile };
      this.#emit({ type: 'attack_active', kind, damage: profile.damage });
      return;
    }
    if (phase === 'active') {
      this.attack = {
        kind,
        phase: 'recovery',
        timer: profile.recovery,
        profile,
      };
      return;
    }
    this.attack = null;
    this.attackCooldown = 0.12;
    this.runtime.setMotionState(this.runtime.locomotionState);
    this.#emit({ type: 'attack_finished', kind });
  }

  #emit(event) {
    const payload = { ...event, entityId: this.runtime.entityId };
    for (const listener of this.eventListeners) listener(payload);
  }
}

/** Frame-rate independent angle damping across the -PI..PI seam. */
export function dampAngle(current, target, rate, deltaSeconds) {
  let delta = target - current;
  while (delta > Math.PI) delta -= Math.PI * 2;
  while (delta < -Math.PI) delta += Math.PI * 2;
  return current + delta * (1 - Math.exp(-rate * deltaSeconds));
}
