/**
 * The battlefield: ground, passability, and fog of war.
 *
 * The world is a query surface, not scenery — selection, movement, targeting
 * and vision all query it every frame — so terrain is a plain function over
 * continuous coordinates.
 *
 * Positions are continuous metres with real-time movement. The grid is an
 * optional alignment layer: `snapToCell` rounds to a cell centre and
 * `footprintCells` reports the cells a body covers, for tile-based briefs.
 * The simulation depends on neither, so both brief styles share this file.
 *
 * Fog is stored per cell, since it is genuinely discrete — a bitmap the
 * renderer samples and the AI reads — with three states:
 *
 *   HIDDEN      never seen; terrain unknown
 *   REMEMBERED  seen before, not now; terrain known, enemies stale
 *   VISIBLE     in vision range now; everything live
 *
 * `REMEMBERED` must not update enemy positions. Collapsing it into `VISIBLE`
 * leaks the enemy army's live position to anyone who scouted once.
 */

import * as THREE from 'three';

/** Side length of the square map, in metres. */
export const MAP_SIZE = 160;

/** Side length of one fog / alignment cell, in metres. */
export const CELL_SIZE = 2;

/** Cells per axis. */
export const GRID_DIM = Math.round(MAP_SIZE / CELL_SIZE);

/** Vision state of one cell. */
export const FogState = Object.freeze({
  HIDDEN: 0,
  REMEMBERED: 1,
  VISIBLE: 2,
});

/**
 * Ground height in metres at a world position.
 *
 * Gentle, because a strategy camera looks almost straight down: dramatic
 * relief reads as noise from above and makes unit bases float visibly. Both
 * the visible mesh and every gameplay query call this function, which is the
 * only arrangement in which a unit cannot stand inside a hill.
 */
export function terrainHeight(x, z) {
  return (
    Math.sin(x * 0.045) * 0.6 +
    Math.cos(z * 0.052) * 0.55 +
    Math.sin((x + z) * 0.021) * 0.9
  );
}

/** Whether a world position is inside the map bounds. */
export function isInsideMap(x, z) {
  const half = MAP_SIZE / 2;
  return x >= -half && x <= half && z >= -half && z <= half;
}

/**
 * Whether the ground at a position can be walked on.
 *
 * Slope is measured by sampling the height field rather than reading a
 * precomputed mask, so terrain and passability can never disagree.
 */
export function isPassable(x, z) {
  if (!isInsideMap(x, z)) return false;
  const d = 1;
  const gradX = Math.abs(terrainHeight(x + d, z) - terrainHeight(x - d, z));
  const gradZ = Math.abs(terrainHeight(x, z + d) - terrainHeight(x, z - d));
  return Math.max(gradX, gradZ) < 1.4;
}

// ---------------------------------------------------------------------------
// Optional grid alignment layer
// ---------------------------------------------------------------------------

/** World position -> integer cell coordinates. */
export function worldToCell(x, z) {
  const half = MAP_SIZE / 2;
  return {
    cx: x === half ? GRID_DIM - 1 : Math.floor((x + half) / CELL_SIZE),
    cz: z === half ? GRID_DIM - 1 : Math.floor((z + half) / CELL_SIZE),
  };
}

/** Integer cell coordinates -> world position of the cell centre. */
export function cellToWorld(cx, cz) {
  const half = MAP_SIZE / 2;
  return {
    x: (cx + 0.5) * CELL_SIZE - half,
    z: (cz + 0.5) * CELL_SIZE - half,
  };
}

/**
 * Round a world position to the centre of its cell.
 *
 * For tile-aligned placement (a building footprint, a board-game brief).
 * Unit movement never calls this: snapping a moving body to cell centres is
 * what makes continuous movement look like it is stuttering.
 */
export function snapToCell(x, z) {
  const { cx, cz } = worldToCell(x, z);
  return cellToWorld(cx, cz);
}

/**
 * Cells covered by an axis-aligned `span` x `span` footprint centred on a
 * world position — the `4 = 2x2`, `9 = 3x3` sizing a tile brief specifies.
 *
 * @returns {{cx: number, cz: number}[]}
 */
export function footprintCells(x, z, span = 1) {
  const { cx, cz } = worldToCell(x, z);
  const reach = Math.floor(span / 2);
  const from = -reach;
  const to = span % 2 === 0 ? reach - 1 : reach;
  const cells = [];
  for (let dz = from; dz <= to; dz += 1) {
    for (let dx = from; dx <= to; dx += 1) {
      cells.push({ cx: cx + dx, cz: cz + dz });
    }
  }
  return cells;
}

// ---------------------------------------------------------------------------
// Fog of war
// ---------------------------------------------------------------------------

/**
 * Per-cell vision, with `REMEMBERED` as a distinct state.
 *
 * `beginFrame` demotes every `VISIBLE` cell to `REMEMBERED`, then each
 * friendly unit re-reveals what it can see. Demoting first is what makes a
 * unit walking away actually re-hide ground, instead of permanently lighting
 * everywhere anyone has ever stood.
 */
export class FogOfWar {
  constructor({ dim = GRID_DIM } = {}) {
    if (dim !== GRID_DIM) throw new RangeError('Fog grid must match the battlefield dimensions');
    this.dim = dim;
    this.state = new Uint8Array(dim * dim);
  }

  #index(cx, cz) {
    if (cx < 0 || cz < 0 || cx >= this.dim || cz >= this.dim) return -1;
    return cz * this.dim + cx;
  }

  /** Demote current vision to memory. Call once per simulation step. */
  beginFrame() {
    const { state } = this;
    for (let i = 0; i < state.length; i += 1) {
      if (state[i] === FogState.VISIBLE) state[i] = FogState.REMEMBERED;
    }
    return this;
  }

  /** Mark a circular area around a world position as currently visible. */
  reveal(x, z, radius) {
    const { cx, cz } = worldToCell(x, z);
    const cells = Math.ceil(radius / CELL_SIZE);
    const limit = cells * cells;
    for (let dz = -cells; dz <= cells; dz += 1) {
      for (let dx = -cells; dx <= cells; dx += 1) {
        if (dx * dx + dz * dz > limit) continue;
        const index = this.#index(cx + dx, cz + dz);
        if (index >= 0) this.state[index] = FogState.VISIBLE;
      }
    }
    return this;
  }

  /** @returns {number} one of `FogState` for a world position. */
  sample(x, z) {
    const { cx, cz } = worldToCell(x, z);
    const index = this.#index(cx, cz);
    return index >= 0 ? this.state[index] : FogState.HIDDEN;
  }

  /** Whether a world position is visible **right now**. */
  isVisible(x, z) {
    return this.sample(x, z) === FogState.VISIBLE;
  }

  /** Whether terrain at a world position has ever been seen. */
  isExplored(x, z) {
    return this.sample(x, z) !== FogState.HIDDEN;
  }

  /** Fraction of the map ever explored, for a HUD readout. */
  exploredRatio() {
    let seen = 0;
    for (let i = 0; i < this.state.length; i += 1) {
      if (this.state[i] !== FogState.HIDDEN) seen += 1;
    }
    return seen / this.state.length;
  }

  reset() {
    this.state.fill(FogState.HIDDEN);
    return this;
  }
}

// ---------------------------------------------------------------------------
// Visible ground
// ---------------------------------------------------------------------------

/**
 * Open terrain from `terrainHeight`. Obstacle navigation is not implemented.
 *
 * The mesh is only the *visible* half of the battlefield; the query
 * functions above are the authoritative half. They agree because both are
 * derived from the same function.
 */
export function buildBattlefield(host, options = {}) {
  const segments = Math.max(8, Number(options.segments ?? 96));
  const group = new THREE.Group();
  group.name = 'battlefield';

  const geometry = new THREE.PlaneGeometry(
    MAP_SIZE,
    MAP_SIZE,
    segments,
    segments,
  );
  geometry.rotateX(-Math.PI / 2);
  const position = geometry.attributes.position;
  for (let i = 0; i < position.count; i += 1) {
    position.setY(i, terrainHeight(position.getX(i), position.getZ(i)));
  }
  geometry.computeVertexNormals();

  const groundMaterial = new THREE.MeshStandardMaterial({
    color: 0x5c6f4a,
    roughness: 0.95,
    vertexColors: true,
  });
  const colors = new THREE.Float32BufferAttribute(new Float32Array(position.count * 3), 3);
  geometry.setAttribute('color', colors);
  const ground = new THREE.Mesh(geometry, groundMaterial);
  ground.name = 'ground';
  ground.receiveShadow = true;
  group.add(ground);

  const rocks = new THREE.Group();
  rocks.name = 'obstacles';
  group.add(rocks);
  host.add(group, 'world');

  return {
    group,
    ground,
    obstacles: rocks,
    /** Ground plane only. Selection and command rays must not hit units. */
    pickTargets: [ground],
    playerSpawn: { x: -MAP_SIZE * 0.28, y: 0, z: MAP_SIZE * 0.28 },
    enemySpawn: { x: MAP_SIZE * 0.28, y: 0, z: -MAP_SIZE * 0.28 },
    updateFog(fog) {
      for (let i = 0; i < position.count; i += 1) {
        const state = fog.sample(position.getX(i), position.getZ(i));
        const shade = state === FogState.VISIBLE ? 1 : state === FogState.REMEMBERED ? 0.25 : 0;
        colors.setXYZ(i, shade, shade, shade);
      }
      colors.needsUpdate = true;
    },
    dispose() {
      geometry.dispose();
      groundMaterial.dispose();
      host.remove(group);
    },
  };
}
