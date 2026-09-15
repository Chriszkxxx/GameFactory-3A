/**
 * Orders, and the queue that holds them.
 *
 * Order-driven input: a click produces a discrete order that is stored on the
 * unit and outlives the click, and the unit re-derives its own velocity each
 * frame until the order completes. The other examples are frame-driven, where
 * the input frame itself is the intent.
 *
 * Four rules, each a bug when missed:
 * - An order must be able to **complete**. A move order without an arrival
 *   tolerance makes units vibrate on the spot.
 * - Orders are **FIFO**, not a single slot, so shift-click appends instead of
 *   discarding the pending order.
 * - A click resolves to move-or-attack by target at **issue** time, not per
 *   tick, which keeps units dumb.
 * - `moveX/moveY` from the input router pan the camera and drive no unit.
 */

/** Order kinds a unit understands. */
export const OrderKind = Object.freeze({
  MOVE: 'move',
  ATTACK: 'attack',
  STOP: 'stop',
});

/** Distance in metres at which a move order counts as complete. */
export const ARRIVAL_TOLERANCE = 0.9;

/**
 * Create a move order to a world position.
 *
 * @param {{x: number, z: number}} point
 */
export function createMoveOrder(point) {
  return {
    kind: OrderKind.MOVE,
    x: Number(point?.x) || 0,
    z: Number(point?.z) || 0,
    targetId: null,
  };
}

/**
 * Create an attack order against a unit.
 *
 * The target is held by **id**, not by object reference, so a dead target
 * resolves to `null` and the order is abandoned. Holding the object keeps
 * corpses alive inside the queue and leaks them.
 */
export function createAttackOrder(target) {
  return {
    kind: OrderKind.ATTACK,
    x: target?.position?.x ?? 0,
    z: target?.position?.z ?? 0,
    targetId: target?.unitId ?? null,
  };
}

/** Create a stop order: clears the queue and holds position. */
export function createStopOrder() {
  return { kind: OrderKind.STOP, x: 0, z: 0, targetId: null };
}

/**
 * A unit's order queue. FIFO.
 *
 * `issue` replaces the queue (a plain click overrides); `enqueue` appends
 * (shift-click adds a waypoint). Two named operations rather than one
 * boolean flag, so gameplay code never has to know about keyboards.
 */
export class OrderQueue {
  constructor() {
    /** @type {object[]} */
    this.orders = [];
  }

  /** Replace everything with one order. */
  issue(order) {
    this.orders = order ? [order] : [];
    return this;
  }

  /** Append an order behind the current one. */
  enqueue(order) {
    if (order && this.current()?.kind === OrderKind.STOP) this.clear();
    if (order) this.orders.push(order);
    return this;
  }

  /** @returns {object | null} the order being executed. */
  current() {
    return this.orders[0] ?? null;
  }

  /** Drop the current order and advance. @returns {object | null} the next. */
  complete() {
    this.orders.shift();
    return this.current();
  }

  clear() {
    this.orders.length = 0;
    return this;
  }

  get length() {
    return this.orders.length;
  }
}

/**
 * Offsets arranging `count` units in a loose square around a point.
 *
 * Spacing is wider than a unit's radius so bodies settle without shoving
 * each other, which would restart their arrival test indefinitely.
 *
 * @returns {{x: number, z: number}[]}
 */
export function formationOffsets(count, spacing = 1.7) {
  const offsets = [];
  const perRow = Math.max(1, Math.ceil(Math.sqrt(count)));
  for (let i = 0; i < count; i += 1) {
    const row = Math.floor(i / perRow);
    const column = i % perRow;
    const rows = Math.ceil(count / perRow);
    offsets.push({
      x: (column - (perRow - 1) / 2) * spacing,
      z: (row - (rows - 1) / 2) * spacing,
    });
  }
  if (offsets.length) {
    const centerX = offsets.reduce((sum, offset) => sum + offset.x, 0) / offsets.length;
    const centerZ = offsets.reduce((sum, offset) => sum + offset.z, 0) / offsets.length;
    for (const offset of offsets) {
      offset.x -= centerX;
      offset.z -= centerZ;
    }
  }
  return offsets;
}

/**
 * Turn one right-click into the correct order for what was clicked.
 *
 * Target resolution happens **here**, once, at issue time — not inside the
 * unit every frame. A unit that re-decides what a click meant on every tick
 * will change its mind the moment the target dies mid-walk.
 *
 * @param {{point?: {x: number, z: number} | null, target?: object | null,
 *          queue?: boolean}} intent
 * @param {object[]} units selected units receiving the order
 * @returns {{kind: string, count: number}} what was issued, for the HUD
 */
export function issueOrders(intent, units) {
  const receivers = (units ?? []).filter((unit) => unit && unit.alive);
  if (receivers.length === 0) return { kind: 'none', count: 0 };

  // An enemy under the cursor outranks the ground beneath it.
  const target = intent?.target;
  const enemy =
    target && target.alive && target.team !== receivers[0].team ? target : null;

  if (!enemy && !intent?.point) return { kind: 'none', count: 0 };

  const spread = formationOffsets(receivers.length);
  receivers.forEach((unit, index) => {
    const order = enemy
      ? createAttackOrder(enemy)
      : createMoveOrder({
          x: intent.point.x + spread[index].x,
          z: intent.point.z + spread[index].z,
        });
    if (intent.queue) unit.orders.enqueue(order);
    else unit.orders.issue(order);
  });

  return {
    kind: enemy ? OrderKind.ATTACK : OrderKind.MOVE,
    count: receivers.length,
  };
}

/** Clear every selected unit's queue and hold position. */
export function issueStop(units) {
  const receivers = (units ?? []).filter((unit) => unit && unit.alive);
  for (const unit of receivers) unit.orders.issue(createStopOrder());
  return { kind: OrderKind.STOP, count: receivers.length };
}
