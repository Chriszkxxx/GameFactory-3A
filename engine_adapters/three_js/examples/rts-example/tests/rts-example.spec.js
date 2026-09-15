/**
 * Reference generated-test pattern (vitest) for top-down real-time strategy.
 *
 * Generated games must prove behavior without a GPU or screenshots. The
 * pattern is:
 *   1. build units directly, with injected roster queries;
 *   2. give them **orders** rather than input frames;
 *   3. step them with an explicit delta;
 *   4. assert observable snapshot and rule state.
 *
 * The cases below target the failures this genre actually produces, each of
 * which a test can catch and none of which a screenshot would:
 *
 * - a move order that never terminates (units vibrating on the spot);
 * - a queue with one slot, silently dropping shift-clicked waypoints;
 * - an input frame steering units instead of the camera;
 * - box select computed in world space, which misses units on high ground;
 * - fog that conflates "seen once" with "visible now", leaking live enemy
 *   positions to anyone who scouted;
 * - an attack order that outlives its target.
 */

import { describe, expect, it, beforeEach } from 'vitest';
import * as THREE from 'three';
import { createRuntimeInputState } from '@a3game/playable';
import {
  CELL_SIZE,
  FogOfWar,
  FogState,
  footprintCells,
  isInsideMap,
  MAP_SIZE,
  snapToCell,
  terrainHeight,
  worldToCell,
} from '../src/battlefield.js';
import {
  ARRIVAL_TOLERANCE,
  createMoveOrder,
  formationOffsets,
  issueOrders,
  issueStop,
  OrderKind,
  OrderQueue,
} from '../src/commands.js';
import {
  DEFAULT_FRUSTUM_HEIGHT,
  MAX_FRUSTUM_HEIGHT,
  MIN_FRUSTUM_HEIGHT,
  StrategyCamera,
} from '../src/camera-rig.js';
import {
  projectToScreen,
  SelectionModel,
  unitAtScreenPoint,
  unitsInScreenRect,
} from '../src/selection.js';
import { Team, Unit, UNIT_PROFILE } from '../src/unit.js';

/** Minimal host double: `add` is all a unit needs to exist. */
function createHostDouble() {
  const root = new THREE.Group();
  return {
    container: null,
    camera: new THREE.OrthographicCamera(-20, 20, 20, -20, -400, 400),
    scene: root,
    options: { frustumHeight: DEFAULT_FRUSTUM_HEIGHT, far: 400 },
    add(object) {
      root.add(object);
      return object;
    },
    remove(object) {
      root.remove(object);
      return this;
    },
    useOrthographicCamera(options = {}) {
      this.options.frustumHeight = options.frustumHeight ?? 46;
      return this.camera;
    },
    setFrustumHeight(height) {
      this.options.frustumHeight = height;
      return this;
    },
  };
}

/** A roster that wires the queries units expect, as `Army` does. */
function createRoster(units) {
  for (const unit of units) {
    unit.resolveTarget = (id) => {
      const found = units.find((candidate) => candidate.unitId === id);
      return found && found.alive ? found : null;
    };
    unit.findEnemy = (self, radius) => {
      let best = null;
      let bestDistance = radius;
      for (const candidate of units) {
        if (!candidate.alive || candidate.team === self.team) continue;
        const distance = Math.hypot(
          candidate.position.x - self.position.x,
          candidate.position.z - self.position.z,
        );
        if (distance < bestDistance) {
          best = candidate;
          bestDistance = distance;
        }
      }
      return best;
    };
  }
  return units;
}

function step(units, seconds, delta = 1 / 60) {
  for (let elapsed = 0; elapsed < seconds; elapsed += delta) {
    for (const unit of units) unit.tick(delta);
  }
}

describe('battlefield', () => {
  it('agrees with itself: the mesh height and the query height are one function', () => {
    // Both the visible mesh and gameplay call terrainHeight, so the only
    // thing to assert is that it is deterministic and finite.
    expect(terrainHeight(12, -8)).toBeCloseTo(terrainHeight(12, -8), 10);
    expect(Number.isFinite(terrainHeight(0, 0))).toBe(true);
  });

  it('bounds the map symmetrically', () => {
    expect(isInsideMap(0, 0)).toBe(true);
    expect(isInsideMap(MAP_SIZE / 2 + 1, 0)).toBe(false);
    expect(isInsideMap(0, -MAP_SIZE / 2 - 1)).toBe(false);
  });

  it('keeps the grid an optional alignment layer, not a movement constraint', () => {
    const snapped = snapToCell(3.3, -7.9);
    // Snapping lands on a cell centre, which is offset by half a cell.
    const { cx, cz } = worldToCell(3.3, -7.9);
    expect(snapped.x).toBeCloseTo((cx + 0.5) * CELL_SIZE - MAP_SIZE / 2, 6);
    expect(snapped.z).toBeCloseTo((cz + 0.5) * CELL_SIZE - MAP_SIZE / 2, 6);
    // And it is idempotent, or repeated placement would drift.
    const twice = snapToCell(snapped.x, snapped.z);
    expect(twice.x).toBeCloseTo(snapped.x, 6);
    expect(twice.z).toBeCloseTo(snapped.z, 6);
  });

  it('reports footprint cells for tile-based briefs', () => {
    expect(footprintCells(0, 0, 1)).toHaveLength(1);
    expect(footprintCells(0, 0, 2)).toHaveLength(4);
    expect(footprintCells(0, 0, 3)).toHaveLength(9);
  });
});

describe('fog of war', () => {
  let fog;

  beforeEach(() => {
    fog = new FogOfWar();
  });

  it('starts fully hidden', () => {
    expect(fog.sample(0, 0)).toBe(FogState.HIDDEN);
    expect(fog.exploredRatio()).toBe(0);
  });

  it('distinguishes remembered ground from currently visible ground', () => {
    fog.beginFrame();
    fog.reveal(0, 0, 10);
    expect(fog.isVisible(0, 0)).toBe(true);
    expect(fog.isExplored(0, 0)).toBe(true);

    // The scout leaves: terrain stays known, live vision does not.
    fog.beginFrame();
    expect(fog.sample(0, 0)).toBe(FogState.REMEMBERED);
    expect(fog.isExplored(0, 0)).toBe(true);
    expect(fog.isVisible(0, 0)).toBe(false);
  });

  it('re-hides nothing that was explored, however far the scout walks', () => {
    fog.beginFrame();
    fog.reveal(-40, -40, 8);
    const explored = fog.exploredRatio();
    fog.beginFrame();
    fog.reveal(40, 40, 8);
    // Exploration is monotonic; only live visibility moves.
    expect(fog.exploredRatio()).toBeGreaterThan(explored);
    expect(fog.isVisible(-40, -40)).toBe(false);
    expect(fog.isExplored(-40, -40)).toBe(true);
  });
});

describe('order queue', () => {
  it('replaces on issue and appends on enqueue', () => {
    const queue = new OrderQueue();
    queue.issue(createMoveOrder({ x: 1, z: 1 }));
    queue.issue(createMoveOrder({ x: 2, z: 2 }));
    expect(queue.length).toBe(1);
    expect(queue.current().x).toBe(2);

    queue.enqueue(createMoveOrder({ x: 3, z: 3 }));
    expect(queue.length).toBe(2);
  });

  it('advances FIFO on completion', () => {
    const queue = new OrderQueue();
    queue.issue(createMoveOrder({ x: 1, z: 0 }));
    queue.enqueue(createMoveOrder({ x: 2, z: 0 }));
    expect(queue.complete().x).toBe(2);
    expect(queue.complete()).toBeNull();
  });
});

describe('issuing orders', () => {
  let host;
  let squad;

  beforeEach(() => {
    host = createHostDouble();
    squad = createRoster([
      new Unit({ host, entityId: 'p1', team: Team.PLAYER }).placeAt({ x: 0, z: 0 }),
      new Unit({ host, entityId: 'p2', team: Team.PLAYER }).placeAt({ x: 2, z: 0 }),
    ]);
  });

  it('spreads a group order so units do not contest one coordinate', () => {
    issueOrders({ point: { x: 20, z: 20 } }, squad);
    const [a, b] = squad.map((unit) => unit.orders.current());
    // Distinct destinations, both near the clicked point.
    expect(a.x === b.x && a.z === b.z).toBe(false);
    expect(Math.hypot(a.x - 20, a.z - 20)).toBeLessThan(4);
  });

  it('turns a click on an enemy into an attack, not a move', () => {
    const enemy = new Unit({ host, entityId: 'e1', team: Team.ENEMY }).placeAt({
      x: 10,
      z: 0,
    });
    const result = issueOrders({ point: { x: 10, z: 0 }, target: enemy }, squad);
    expect(result.kind).toBe(OrderKind.ATTACK);
    expect(squad[0].orders.current().targetId).toBe('e1');
  });

  it('ignores a friendly unit as an attack target', () => {
    const result = issueOrders(
      { point: { x: 5, z: 5 }, target: squad[1] },
      [squad[0]],
    );
    expect(result.kind).toBe(OrderKind.MOVE);
  });

  it('queues rather than replaces when asked', () => {
    issueOrders({ point: { x: 10, z: 0 } }, [squad[0]]);
    issueOrders({ point: { x: 20, z: 0 }, queue: true }, [squad[0]]);
    expect(squad[0].orders.length).toBe(2);
  });

  it('clears the queue on stop', () => {
    issueOrders({ point: { x: 10, z: 0 } }, squad);
    issueOrders({ point: { x: 20, z: 0 }, queue: true }, squad);
    issueStop(squad);
    expect(squad[0].orders.current().kind).toBe(OrderKind.STOP);
    expect(squad[0].orders.length).toBe(1);
  });

  it('lays out a formation centred on the target point', () => {
    const offsets = formationOffsets(4);
    const sumX = offsets.reduce((total, o) => total + o.x, 0);
    const sumZ = offsets.reduce((total, o) => total + o.z, 0);
    expect(sumX).toBeCloseTo(0, 6);
    expect(sumZ).toBeCloseTo(0, 6);
  });
});

describe('unit execution', () => {
  let host;
  let unit;

  beforeEach(() => {
    host = createHostDouble();
    unit = createRoster([
      new Unit({ host, entityId: 'p1', team: Team.PLAYER }).placeAt({ x: 0, z: 0 }),
    ])[0];
  });

  it('completes a move order and then stops, rather than vibrating', () => {
    unit.orders.issue(createMoveOrder({ x: 0, z: 14 }));
    step([unit], 5);

    expect(unit.orders.length).toBe(0);
    expect(Math.hypot(unit.position.x - 0, unit.position.z - 14)).toBeLessThan(
      ARRIVAL_TOLERANCE + 0.2,
    );

    // Idle for another second: an incomplete termination test shows up here
    // as continued movement.
    const settled = unit.position.clone();
    step([unit], 1);
    expect(unit.position.distanceTo(settled)).toBeLessThan(1e-6);
  });

  it('walks a queued path in order', () => {
    unit.orders.issue(createMoveOrder({ x: 0, z: 8 }));
    unit.orders.enqueue(createMoveOrder({ x: 8, z: 8 }));
    step([unit], 6);
    expect(unit.orders.length).toBe(0);
    expect(unit.position.x).toBeGreaterThan(6);
    expect(unit.position.z).toBeGreaterThan(6);
  });

  it('does not move in response to an input frame', () => {
    // The whole control-model claim of this example: input drives the camera,
    // orders drive units. A regression here means someone wired moveX/moveY
    // into the entity.
    const before = unit.position.clone();
    for (let i = 0; i < 60; i += 1) {
      unit.applyRuntimeInput(
        createRuntimeInputState({ moveX: 1, moveY: 1, sequence: i }),
      );
      unit.tick(1 / 60);
    }
    expect(unit.position.distanceTo(before)).toBeLessThan(1e-9);
  });

  it('reports order state through the runtime snapshot', () => {
    unit.orders.issue(createMoveOrder({ x: 0, z: 20 }));
    unit.tick(1 / 60);
    const snapshot = unit.getRuntimeSnapshot();
    // `createEntitySnapshot` has no `metadata` field and puts position at the
    // top level, so strategy state sits alongside it rather than inside it.
    expect(snapshot.orderKind).toBe(OrderKind.MOVE);
    expect(snapshot.team).toBe(Team.PLAYER);
    expect(snapshot.locomotionState).toBe('run');
    expect(snapshot.position).toMatchObject({ x: expect.any(Number) });
    expect(snapshot.entityId).toBe('p1');
  });
});

describe('combat', () => {
  let host;
  let attacker;
  let victim;

  beforeEach(() => {
    host = createHostDouble();
    [attacker, victim] = createRoster([
      new Unit({ host, entityId: 'p1', team: Team.PLAYER }).placeAt({ x: 0, z: 0 }),
      new Unit({ host, entityId: 'e1', team: Team.ENEMY }).placeAt({ x: 4, z: 0 }),
    ]);
  });

  it('closes to range, then damages the target', () => {
    attacker.orders.issue({
      kind: OrderKind.ATTACK,
      x: victim.position.x,
      z: victim.position.z,
      targetId: 'e1',
    });
    // Victim holds still: only the attacker acts.
    step([attacker], 2);
    expect(victim.health).toBeLessThan(UNIT_PROFILE.maxHealth);
  });

  it('abandons an attack order when the target dies', () => {
    attacker.orders.issue({
      kind: OrderKind.ATTACK,
      x: victim.position.x,
      z: victim.position.z,
      targetId: 'e1',
    });
    victim.applyDamage(UNIT_PROFILE.maxHealth);
    expect(victim.alive).toBe(false);

    step([attacker], 0.5);
    // The order is dropped rather than freezing the unit forever.
    expect(attacker.orders.length).toBe(0);
  });

  it('retaliates when shot while idle', () => {
    expect(victim.orders.length).toBe(0);
    victim.applyDamage(5, attacker);
    expect(victim.orders.current().kind).toBe(OrderKind.ATTACK);
    expect(victim.orders.current().targetId).toBe('p1');
  });

  it('auto-acquires an enemy that wanders into aggro range while idle', () => {
    victim.placeAt({ x: 5, z: 0 });
    step([attacker], 1 / 30);
    expect(attacker.orders.current()?.kind).toBe(OrderKind.ATTACK);
  });
});

describe('selection', () => {
  let host;
  let squad;
  const viewport = { width: 800, height: 600 };

  beforeEach(() => {
    host = createHostDouble();
    host.camera.position.set(0, 40, 40);
    host.camera.lookAt(0, 0, 0);
    host.camera.updateMatrixWorld(true);
    host.camera.updateProjectionMatrix();
    squad = createRoster([
      new Unit({ host, entityId: 'p1', team: Team.PLAYER }).placeAt({ x: 0, z: 0 }),
      new Unit({ host, entityId: 'p2', team: Team.PLAYER }).placeAt({ x: 60, z: 60 }),
    ]);
  });

  it('box selects in screen space, so raised ground does not break it', () => {
    const near = projectToScreen(squad[0], host.camera, viewport);
    const rect = {
      left: near.x - 30,
      right: near.x + 30,
      top: near.y - 30,
      bottom: near.y + 30,
    };
    const hits = unitsInScreenRect(squad, rect, host.camera, viewport);
    expect(hits).toContain(squad[0]);
    expect(hits).not.toContain(squad[1]);
  });

  it('picks the nearest unit to a click, within a pixel radius', () => {
    const near = projectToScreen(squad[0], host.camera, viewport);
    expect(unitAtScreenPoint(squad, near, host.camera, viewport)).toBe(squad[0]);
    expect(
      unitAtScreenPoint(
        squad,
        { x: near.x + 400, y: near.y },
        host.camera,
        viewport,
      ),
    ).toBeNull();
  });

  it('excludes dead units from selection and prunes them afterwards', () => {
    const selection = new SelectionModel({
      camera: host.camera,
      container: null,
    });
    selection.set(squad);
    expect(selection.size).toBe(2);

    squad[1].applyDamage(UNIT_PROFILE.maxHealth);
    selection.prune();
    expect(selection.size).toBe(1);
    expect(squad[1].selectionRing.visible).toBe(false);
  });

  it('treats a small drag as a click and a large one as a box', () => {
    const selection = new SelectionModel({
      camera: host.camera,
      container: null,
    });
    selection.beginDrag({ clientX: 100, clientY: 100 });
    selection.updateDrag({ clientX: 102, clientY: 101 });
    expect(selection.endDrag().kind).toBe('click');

    selection.beginDrag({ clientX: 100, clientY: 100 });
    selection.updateDrag({ clientX: 180, clientY: 160 });
    const finished = selection.endDrag();
    expect(finished.kind).toBe('box');
    expect(finished.rect).toMatchObject({ left: 100, top: 100 });
  });
});

describe('strategy camera', () => {
  let host;
  let camera;

  beforeEach(() => {
    host = createHostDouble();
    camera = new StrategyCamera({ host }).attach({ x: 0, z: 0 });
  });

  it('pans in screen space, not along world axes', () => {
    // The rig is yawed, so a pure screen-right pan must change both x and z.
    camera.pan(1, 0, 1);
    const state = camera.getState();
    expect(Math.abs(state.x)).toBeGreaterThan(0.01);
    expect(Math.abs(state.z)).toBeGreaterThan(0.01);
  });

  it('clamps the focus to the map so the view cannot leave the battlefield', () => {
    for (let i = 0; i < 200; i += 1) camera.pan(1, 1, 1);
    const state = camera.getState();
    expect(Math.abs(state.x)).toBeLessThanOrEqual(MAP_SIZE / 2);
    expect(Math.abs(state.z)).toBeLessThanOrEqual(MAP_SIZE / 2);
  });

  it('zooms by frustum height, within bounds', () => {
    camera.setFrustumHeight(1);
    expect(camera.getState().frustumHeight).toBe(MIN_FRUSTUM_HEIGHT);
    camera.setFrustumHeight(10_000);
    expect(camera.getState().frustumHeight).toBe(MAX_FRUSTUM_HEIGHT);
  });

  it('does not drift when the pointer is outside the viewport', () => {
    camera.pointer = { x: -50, y: -50 };
    const before = camera.getState();
    camera.update(1, { x: 0, y: 0 }, { width: 800, height: 600 });
    expect(camera.getState()).toEqual(before);
  });

  it('edge pans while the pointer is inside the viewport', () => {
    camera.pointer = { x: 2, y: 300 };
    const before = camera.getState();
    camera.update(0.5, { x: 0, y: 0 }, { width: 800, height: 600 });
    expect(camera.getState()).not.toEqual(before);
  });
});
