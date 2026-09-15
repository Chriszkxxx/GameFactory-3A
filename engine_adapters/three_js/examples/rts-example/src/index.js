/**
 * Boot sequence for the real-time strategy example.
 *
 *   1. host + assets + world (framework)
 *   2. the battlefield, a query surface as much as a mesh
 *   3. HUD widgets, including the marquee and the minimap
 *   4. entity factory registration
 *   5. local input router, sampled only by the camera
 *   6. orthographic rig that no unit reads, plus the selection and order
 *      layer that turns clicks into queued orders
 *
 * The router's frame and the units' intent never touch: `moveX/moveY` pan the
 * camera while units run on orders.
 *
 * Pointer handlers live here because they are this game's bindings — which
 * button selects, which orders, which modifier queues. `selection.js` owns
 * the geometry and `commands.js` the order semantics; neither knows about a
 * mouse. Binding orders to right-click requires suppressing the browser
 * context menu on the viewport.
 */

import {
  A3GameEntityFactory,
  A3GameInputRouter,
  A3GameLookMode,
  bootA3GameRuntime,
  createSunLight,
} from '@a3game/playable';
import { buildBattlefield, FogOfWar, MAP_SIZE } from './battlefield.js';
import { issueOrders, issueStop } from './commands.js';
import { StrategyCamera } from './camera-rig.js';
import {
  SelectionModel,
  unitAtScreenPoint,
  unitsInScreenRect,
} from './selection.js';
import { Team, Unit } from './unit.js';

export {
  buildBattlefield,
  CELL_SIZE,
  cellToWorld,
  FogOfWar,
  FogState,
  footprintCells,
  GRID_DIM,
  isPassable,
  isInsideMap,
  MAP_SIZE,
  snapToCell,
  terrainHeight,
  worldToCell,
} from './battlefield.js';
export {
  ARRIVAL_TOLERANCE,
  createAttackOrder,
  createMoveOrder,
  createStopOrder,
  formationOffsets,
  issueOrders,
  issueStop,
  OrderKind,
  OrderQueue,
} from './commands.js';
export {
  DEFAULT_FRUSTUM_HEIGHT,
  MAX_FRUSTUM_HEIGHT,
  MIN_FRUSTUM_HEIGHT,
  StrategyCamera,
} from './camera-rig.js';
export {
  DRAG_THRESHOLD,
  projectToScreen,
  SelectionModel,
  unitAtScreenPoint,
  unitsInScreenRect,
} from './selection.js';
export { Team, Unit, UNIT_PROFILE } from './unit.js';

const CONTROLS_TEXT = [
  'WASD / edge — pan the camera',
  'Wheel — zoom',
  'Left click — select · drag — box select',
  'Shift+left — add to selection',
  'Right click — move · on an enemy — attack',
  'Shift+right — queue a waypoint',
  'X — stop · Ctrl+A — select all',
].join('\n');

const PLAYER_SQUAD = 8;
const ENEMY_SQUAD = 6;

/**
 * Spawns units on demand for the runtime subsystem.
 *
 * A strategy game spawns many entities of the same kind, so the team travels
 * on the spawn request rather than in a per-factory field.
 *
 * The team goes in `parameters`, not `metadata`. `runtime.spawnEntity` runs
 * every request through `createEntitySpawnRequest`, whose shape is
 * `{worldId, participantId, entityId, transform, parameters}` — any other key
 * is dropped silently, so a team passed as `metadata` arrives as `undefined`
 * and every unit spawns on the default team.
 */
export class UnitFactory extends A3GameEntityFactory {
  /** @param {{profile?: object, onSpawn?: (unit: Unit) => void}} [options] */
  constructor(options = {}) {
    super();
    this.profile = options.profile ?? {};
    this.onSpawn = options.onSpawn ?? null;
    /** @type {Map<string, Unit>} */
    this.units = new Map();
  }

  async spawnRuntimeEntity(request, { host }) {
    const unit = new Unit({
      host,
      entityId: request.entityId,
      team: request.parameters?.team ?? Team.PLAYER,
      profile: this.profile,
    });
    unit.placeAt(request.transform?.position ?? { x: 0, y: 0, z: 0 });
    this.units.set(unit.unitId, unit);
    this.onSpawn?.(unit);
    return unit;
  }
}

/**
 * Every unit on the map, and the queries units need about each other.
 *
 * Target resolution and enemy search are injected into units from here, so a
 * unit never holds a reference to the roster. That keeps a unit testable in
 * isolation and stops dead units being reachable through their killers.
 */
export class Army {
  constructor({ fog = null } = {}) {
    this.fog = fog;
    /** @type {Unit[]} */
    this.units = [];
  }

  register(unit) {
    this.units.push(unit);
    unit.resolveTarget = (id) => {
      const found = this.units.find((candidate) => candidate.unitId === id);
      return found && found.alive ? found : null;
    };
    unit.canSeeTarget = (target) => this.visibleTo(unit.team, target);
    unit.findEnemy = (self, radius) => this.nearestEnemy(self, radius);
    return unit;
  }

  /** @returns {Unit[]} live units of a team. */
  team(team) {
    return this.units.filter((unit) => unit.team === team && unit.alive);
  }

  visibleTo(team, target) {
    if (!target?.alive) return false;
    if (target.team === team) return true;
    if (team === Team.PLAYER && this.fog) {
      return this.fog.isVisible(target.position.x, target.position.z);
    }
    return this.team(team).some((scout) =>
      Math.hypot(scout.position.x - target.position.x, scout.position.z - target.position.z) <= scout.profile.visionRadius);
  }

  /** @returns {Unit | null} nearest live enemy within a radius. */
  nearestEnemy(self, radius) {
    let best = null;
    let bestDistance = radius;
    for (const unit of this.units) {
      if (!unit.alive || unit.team === self.team || !this.visibleTo(self.team, unit)) continue;
      const distance = Math.hypot(
        unit.position.x - self.position.x,
        unit.position.z - self.position.z,
      );
      if (distance < bestDistance) {
        best = unit;
        bestDistance = distance;
      }
    }
    return best;
  }

  /**
   * Drop references without touching the units.
   *
   * The roster has no `tick` or `dispose`: the runtime already ticks and
   * disposes every registered entity, so a second lifecycle here would
   * double-step movement and damage, or dispose twice.
   */
  detach() {
    this.units.length = 0;
    return this;
  }
}

/** A DOM marquee, and a minimap, drawn over the viewport. */
function createOverlay(container) {
  const marquee = document.createElement('div');
  Object.assign(marquee.style, {
    position: 'absolute',
    border: '1px solid #8ef58a',
    background: 'rgba(142, 245, 138, 0.12)',
    pointerEvents: 'none',
    display: 'none',
    zIndex: '20',
  });
  container.appendChild(marquee);

  const minimap = document.createElement('canvas');
  minimap.width = 160;
  minimap.height = 160;
  Object.assign(minimap.style, {
    position: 'absolute',
    right: '12px',
    bottom: '12px',
    border: '1px solid rgba(255,255,255,0.35)',
    background: 'rgba(0,0,0,0.55)',
    cursor: 'pointer',
    zIndex: '21',
  });
  container.appendChild(minimap);

  return {
    marquee,
    minimap,
    setRect(rect) {
      if (!rect) {
        marquee.style.display = 'none';
        return;
      }
      Object.assign(marquee.style, {
        display: 'block',
        left: `${rect.left}px`,
        top: `${rect.top}px`,
        width: `${rect.right - rect.left}px`,
        height: `${rect.bottom - rect.top}px`,
      });
    },
    dispose() {
      marquee.remove();
      minimap.remove();
    },
  };
}

/** Paint units and the camera window onto the minimap. */
export function drawMinimap(canvas, army, camera) {
  const context = canvas.getContext('2d');
  if (!context) return;
  const { width, height } = canvas;
  context.clearRect(0, 0, width, height);

  const toCanvas = (x, z) => ({
    cx: ((x + MAP_SIZE / 2) / MAP_SIZE) * width,
    cy: ((z + MAP_SIZE / 2) / MAP_SIZE) * height,
  });

  for (const unit of army.units) {
    if (!army.visibleTo(Team.PLAYER, unit)) continue;
    const { cx, cy } = toCanvas(unit.position.x, unit.position.z);
    context.fillStyle = unit.team === Team.PLAYER ? '#66a9ee' : '#e2705c';
    context.fillRect(cx - 1.5, cy - 1.5, 3, 3);
  }

  const view = camera.getState();
  const half = (view.frustumHeight / MAP_SIZE) * width * 0.5;
  const { cx, cy } = toCanvas(view.x, view.z);
  context.strokeStyle = 'rgba(255,255,255,0.7)';
  context.strokeRect(cx - half, cy - half, half * 2, half * 2);
}

/**
 * Start the example.
 *
 * @param {{container?: string, hudContainer?: string, worldUrl?: string,
 *          manifestUrl?: string, seed?: number}} [options]
 */
export async function startStrategy(options = {}) {
  const runtimeContext = await bootA3GameRuntime({
    container: options.container ?? '#a3game-viewport',
    hudContainer: options.hudContainer ?? '#a3game-hud',
    manifestUrl: options.manifestUrl,
    worldUrl: options.worldUrl,
    hostOptions: { clearColor: 0x1b2430 },
    autoBeginPlay: false,
    autoStart: false,
  });
  const { host, assets, session, runtime, hud } = runtimeContext;

  host.setEnvironment({
    preset: 'gradient',
    sunPosition: { x: -0.4, y: 0.8, z: -0.45 },
    sky: { zenith: 0x2c5f96, horizon: 0xc9d8e4, ground: 0x4d5a44 },
    environmentIntensity: 0.95,
    toneMapping: 'ACESFilmicToneMapping',
    toneMappingExposure: 0.85,
  });

  const battlefield = buildBattlefield(host, {
    segments: 96,
    seed: options.seed ?? 7,
  });

  const sun = createSunLight({
    position: host.getSunPosition(80),
    radius: 150,
    intensity: 2.4,
    color: 0xfff0d6,
  });
  host.add(sun, 'lights');

  const fog = new FogOfWar();
  const army = new Army({ fog });

  // Orthographic, and attached before any unit exists: `attach` swaps the
  // host camera, and the selection layer must project against the camera the
  // player is actually looking through.
  const strategyCamera = new StrategyCamera({ host }).attach(
    battlefield.playerSpawn,
  );

  hud.addText('selection', { anchor: 'top-right', value: 'Selected 0' });
  hud.addText('forces', { anchor: 'bottom-left', value: '' });
  hud.addText('order', { anchor: 'bottom-center', value: '' });
  hud.addPanel('controls', { anchor: 'top-left', value: CONTROLS_TEXT });

  const overlay = createOverlay(host.container);
  const canvas = host.renderer.domElement;

  const factory = new UnitFactory({ onSpawn: (unit) => army.register(unit) });
  runtime.setEntityFactory(factory);

  const viewport = () => ({
    width: canvas.getBoundingClientRect().width,
    height: canvas.getBoundingClientRect().height,
  });

  const selection = new SelectionModel({
    camera: host.camera,
    container: canvas,
    onRectChange: (rect) => overlay.setRect(rect),
    onChange: (units) => hud.setValue('selection', `Selected ${units.length}`),
  });

  session.registerParticipant('local_commander');
  const joined = session.createController('local_commander', 'local_controller', 'human');

  // Squads are spawned through the runtime so the registry, ids, and
  // snapshots match a generated game; bypassing it would make the example
  // untestable through the runtime bridge.
  for (let i = 0; i < PLAYER_SQUAD; i += 1) {
    const angle = (i / PLAYER_SQUAD) * Math.PI * 2;
    const unit = await runtime.spawnEntity({
      entityId: `player_unit_${i + 1}`,
      parameters: { team: Team.PLAYER },
      transform: {
        position: {
          x: battlefield.playerSpawn.x + Math.cos(angle) * 4,
          y: 0,
          z: battlefield.playerSpawn.z + Math.sin(angle) * 4,
        },
      },
    });
    session.registerEntity(unit.unitId, unit);
  }
  for (let i = 0; i < ENEMY_SQUAD; i += 1) {
    const angle = (i / ENEMY_SQUAD) * Math.PI * 2;
    const unit = await runtime.spawnEntity({
      entityId: `enemy_unit_${i + 1}`,
      parameters: { team: Team.ENEMY },
      transform: {
        position: {
          x: battlefield.enemySpawn.x + Math.cos(angle) * 4,
          y: 0,
          z: battlefield.enemySpawn.z + Math.sin(angle) * 4,
        },
      },
    });
    session.registerEntity(unit.unitId, unit);
  }

  // `ALWAYS` look mode: a strategy game never captures the cursor, and it
  // has no look axis at all. The router is used for its keyboard axes and
  // action bindings; yaw and pitch are ignored.
  const input = new A3GameInputRouter({
    target: canvas,
    controllerId: joined.controllerId,
    lookMode: A3GameLookMode.ALWAYS,
    pointerSensitivity: 0,
    actionBindings: { KeyX: 'stop' },
  }).enable();
  const unsubscribeAction = input.onAction((action, phase) => {
    if (action !== 'stop' || phase !== 'pressed' ||
        document.activeElement?.isContentEditable ||
        /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName ?? '')) return;
    const result = issueStop(selection.list());
    if (result.count > 0) hud.setValue('order', `stop x${result.count}`);
  });

  /** Ground point under a pointer event, or null when off-map. */
  const groundPoint = (event) => {
    const hit = host.raycastFromPointer(event, battlefield.pickTargets);
    return hit ? { x: hit.point.x, z: hit.point.z } : null;
  };

  const localPoint = (event) => {
    const bounds = canvas.getBoundingClientRect();
    return { x: event.clientX - bounds.left, y: event.clientY - bounds.top };
  };

  // -- Pointer bindings ----------------------------------------------------

  const onContextMenu = (event) => event.preventDefault();

  let gesture = null;
  let focused = true;
  const editable = (target) => target?.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target?.tagName ?? '');
  const insideCanvas = (event) => {
    const point = localPoint(event);
    const size = viewport();
    return point.x >= 0 && point.y >= 0 && point.x <= size.width && point.y <= size.height;
  };
  const clearGesture = () => {
    gesture = null;
    selection.endDrag();
    strategyCamera.pointer = null;
  };
  const onPointerLeave = () => { strategyCamera.pointer = null; };
  const onBlur = () => { focused = false; clearGesture(); input.reset(); };
  const onFocus = () => { focused = true; };

  const onPointerDown = (event) => {
    if (gesture || (event.button !== 0 && event.button !== 2)) return;
    gesture = { id: event.pointerId, button: event.button };
    if (event.button === 0) selection.beginDrag(event);
  };

  const onPointerMove = (event) => {
    strategyCamera.pointer = event.target === canvas ? localPoint(event) : null;
    if (gesture?.id === event.pointerId && selection.dragStart) selection.updateDrag(event);
  };

  const onPointerUp = (event) => {
    if (!gesture || gesture.id !== event.pointerId || gesture.button !== event.button) return;
    gesture = null;
    if (event.target !== canvas || !insideCanvas(event)) { clearGesture(); return; }
    if (event.button === 0) {
      selection.updateDrag(event);
      const { kind, rect } = selection.endDrag();
      const roster = army.team(Team.PLAYER);
      const picked =
        kind === 'box'
          ? unitsInScreenRect(roster, rect, host.camera, viewport())
          : [
              unitAtScreenPoint(
                roster,
                localPoint(event),
                host.camera,
                viewport(),
              ),
            ].filter(Boolean);

      if (event.shiftKey) selection.add(picked);
      else selection.set(picked);
      return;
    }

    if (event.button === 2) {
      // Order. The enemy under the cursor takes precedence over the ground.
      const target = unitAtScreenPoint(
        army.team(Team.ENEMY).filter((unit) => army.visibleTo(Team.PLAYER, unit)),
        localPoint(event),
        host.camera,
        viewport(),
      );
      const result = issueOrders(
        { point: groundPoint(event), target, queue: event.shiftKey },
        selection.list(),
      );
      if (result.count > 0) {
        hud.setValue(
          'order',
          `${result.kind} x${result.count}${event.shiftKey ? ' (queued)' : ''}`,
        );
      }
    }
  };

  const onWheel = (event) => {
    event.preventDefault();
    const scale = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? viewport().height : 1;
    strategyCamera.zoom(event.deltaY * scale);
  };

  const onKeyDown = (event) => {
    if (editable(event.target)) { input.reset(); return; }
    if (event.code === 'KeyA' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      input.reset();
      selection.set(army.team(Team.PLAYER));
    }
  };

  const onMinimapClick = (event) => {
    if (event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    clearGesture();
    const bounds = overlay.minimap.getBoundingClientRect();
    const ratioX = (event.clientX - bounds.left) / bounds.width;
    const ratioZ = (event.clientY - bounds.top) / bounds.height;
    strategyCamera.focusOn({
      x: ratioX * MAP_SIZE - MAP_SIZE / 2,
      z: ratioZ * MAP_SIZE - MAP_SIZE / 2,
    });
  };

  canvas.addEventListener('contextmenu', onContextMenu);
  canvas.addEventListener('pointerdown', onPointerDown);
  canvas.addEventListener('pointerleave', onPointerLeave);
  window.addEventListener('pointermove', onPointerMove);
  window.addEventListener('pointercancel', clearGesture);
  window.addEventListener('blur', onBlur);
  window.addEventListener('focus', onFocus);
  canvas.addEventListener('wheel', onWheel, { passive: false });
  overlay.minimap.addEventListener('pointerdown', onMinimapClick);
  // On `window`, so a drag released outside the viewport still resolves;
  // otherwise the marquee sticks on forever.
  window.addEventListener('pointerup', onPointerUp);
  window.addEventListener('keydown', onKeyDown);

  runtime.onWorldBeginPlay();

  const updateVisibility = () => {
    selection.prune();

    // Fog is recomputed after movement, so vision reflects where units are
    // now rather than where they were at the start of the step.
    fog.beginFrame();
    for (const unit of army.team(Team.PLAYER)) {
      fog.reveal(unit.position.x, unit.position.z, unit.profile.visionRadius);
    }

    // Enemies are only rendered while genuinely visible. This is the payoff
    // of keeping REMEMBERED distinct from VISIBLE: remembered ground stays
    // explored, but the enemies standing on it disappear.
    for (const unit of army.units) {
      if (unit.team === Team.ENEMY) {
        unit.object.visible =
          unit.alive && fog.isVisible(unit.position.x, unit.position.z);
      }
    }
    battlefield.updateFog(fog);
  };
  updateVisibility();
  const unsubscribeTick = host.onTick(updateVisibility);

  const unsubscribeRender = host.onRender((delta) => {
    // Camera pan comes from the router's movement axes — the axes that steer
    // the character in every other example.
    if (focused && !editable(document.activeElement)) {
      const frame = input.sample({ controllerId: joined.controllerId });
      strategyCamera.update(delta, { x: frame.moveX, y: frame.moveY }, viewport());
    } else {
      input.reset();
    }

    const players = army.team(Team.PLAYER).length;
    const enemies = army.team(Team.ENEMY).filter((unit) => army.visibleTo(Team.PLAYER, unit)).length;
    hud.setValue(
      'forces',
      `Units ${players} · Visible enemies ${enemies} · Explored ${Math.round(
        fog.exploredRatio() * 100,
      )}%`,
    );
    drawMinimap(overlay.minimap, army, strategyCamera);
  });

  host.start();

  let disposed = false;
  const context = {
    ...runtimeContext,
    battlefield,
    army,
    factory,
    fog,
    selection,
    strategyCamera,
    input,
    controllerId: joined.controllerId,
    dispose() {
      if (disposed) return;
      disposed = true;
      host.stop();
      unsubscribeTick();
      unsubscribeRender();
      canvas.removeEventListener('contextmenu', onContextMenu);
      canvas.removeEventListener('pointerdown', onPointerDown);
      canvas.removeEventListener('pointerleave', onPointerLeave);
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointercancel', clearGesture);
      window.removeEventListener('blur', onBlur);
      window.removeEventListener('focus', onFocus);
      canvas.removeEventListener('wheel', onWheel);
      overlay.minimap.removeEventListener('pointerdown', onMinimapClick);
      window.removeEventListener('pointerup', onPointerUp);
      window.removeEventListener('keydown', onKeyDown);
      unsubscribeAction();
      input.disable();
      selection.clear();
      overlay.dispose();
      // `deinitialize` already disposed every registered entity, so the
      // roster only needs to let go of them.
      runtime.deinitialize();
      army.detach();
      factory.units.clear();
      battlefield.dispose();
      hud.dispose();
      assets.dispose();
      host.dispose();
      if (globalThis.__A3GAME_STRATEGY__ === context) delete globalThis.__A3GAME_STRATEGY__;
    },
  };
  globalThis.__A3GAME_STRATEGY__ = context;
  return context;
}
