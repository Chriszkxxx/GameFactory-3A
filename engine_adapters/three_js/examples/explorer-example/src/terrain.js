/**
 * Terrain for the exploration example.
 *
 * The height field is a plain function of x and z rather than a mesh with
 * a lookup table, and that is the load-bearing decision in this file.
 * Gameplay asks "where is the floor here?" dozens of times a frame — for
 * the player, for every arrow, for every prop being placed — and if the
 * answer comes from anywhere other than the same function that built the
 * visible mesh, the player walks through hills and stands on air.
 *
 * So: one function, exported, used by the mesh builder *and* by the
 * entity, and never duplicated.
 */

import * as THREE from 'three';
import { createSeededRandom, createSurfaceMaterial, A3GameSurfacePattern } from '@a3game/playable';

/** Half-extent of the walkable world, in metres. */
export const WORLD_HALF = 90;

/**
 * Ground height at a world position.
 *
 * @param {number} x
 * @param {number} z
 * @returns {number} metres
 */
export function terrainHeight(x, z) {
  const ridges =
    Math.sin(x * 0.042) * 2.8 +
    Math.cos(z * 0.036) * 3.1 +
    Math.sin((x + z) * 0.021) * 3.6;
  const detail = Math.sin(x * 0.16) * 0.44 + Math.cos(z * 0.19) * 0.4;

  // A flat clearing at the origin. A player who spawns on a slope slides
  // before they have touched the controls, which reads as a bug.
  const clearing = THREE.MathUtils.clamp((Math.hypot(x, z) - 12) / 16, 0, 1);

  // A rim at the world edge. This is a soft boundary that needs no
  // invisible wall and no message: terrain that climbs faster than the
  // player can walk turns them around on its own.
  const edge = THREE.MathUtils.clamp(
    (Math.hypot(x, z) - WORLD_HALF * 0.66) / (WORLD_HALF * 0.34),
    0,
    1,
  );
  return (ridges + detail) * clearing + edge * edge * 14;
}

/**
 * Whether a spot is flat enough to stand a prop on.
 *
 * Sampled as a real slope over a metre rather than as a height threshold,
 * because a prop on a steep face floats on its downhill side however
 * correct its own y is.
 *
 * @param {number} x
 * @param {number} z
 * @param {number} [maxSlope] metres of rise per metre travelled
 */
export function isBuildable(x, z, maxSlope = 0.42) {
  const here = terrainHeight(x, z);
  const dx = Math.abs(terrainHeight(x + 1, z) - here);
  const dz = Math.abs(terrainHeight(x, z + 1) - here);
  return Math.max(dx, dz) <= maxSlope;
}

/**
 * Build the terrain mesh, tinted by height and slope.
 *
 * The vertex colours are what make the ground read as ground: a single
 * flat green plane with a normal map still looks like a plane, because
 * real terrain changes colour where it changes shape — rock on the steep
 * faces, grass on the flats, pale gravel in the hollows.
 *
 * @param {{segments?: number, repeat?: number}} [options]
 * @returns {THREE.Mesh} with `userData.dispose()`
 */
export function buildTerrain(options = {}) {
  const segments = Math.max(16, Math.floor(Number(options.segments ?? 180)));
  const geometry = new THREE.PlaneGeometry(
    WORLD_HALF * 2,
    WORLD_HALF * 2,
    segments,
    segments,
  );
  geometry.rotateX(-Math.PI / 2);

  const position = geometry.attributes.position;
  const colours = new Float32Array(position.count * 3);
  const grass = new THREE.Color(0x4f7a3a);
  const rock = new THREE.Color(0x6b6660);
  const gravel = new THREE.Color(0x8d8873);
  const shade = new THREE.Color();

  for (let index = 0; index < position.count; index += 1) {
    const x = position.getX(index);
    const z = position.getZ(index);
    const height = terrainHeight(x, z);
    position.setY(index, height);

    const slope = Math.max(
      Math.abs(terrainHeight(x + 1, z) - height),
      Math.abs(terrainHeight(x, z + 1) - height),
    );
    shade.copy(grass).lerp(rock, THREE.MathUtils.clamp(slope / 1.4, 0, 1));
    shade.lerp(gravel, THREE.MathUtils.clamp((2 - height) / 8, 0, 0.35));
    colours[index * 3] = shade.r;
    colours[index * 3 + 1] = shade.g;
    colours[index * 3 + 2] = shade.b;
  }
  geometry.setAttribute('color', new THREE.BufferAttribute(colours, 3));
  geometry.computeVertexNormals();

  // A procedural PBR set supplies the close-up detail the 180-segment mesh
  // cannot, and `vertexColors` multiplies over it so the height-and-slope
  // palette survives. Replacing the colours with the texture instead would
  // throw away the only thing telling the player where the rock is.
  const material = createSurfaceMaterial({
    pattern: A3GameSurfacePattern.CONCRETE,
    repeat: WORLD_HALF * 0.9,
    cells: 3,
    color: 0xb9b3a4,
    jointColor: 0x8f8b7e,
    roughness: [0.86, 0.98],
    normalStrength: 0.7,
    seed: 21,
    material: { vertexColors: true },
  });

  const mesh = new THREE.Mesh(geometry, material);
  mesh.name = 'terrain';
  mesh.receiveShadow = true;
  mesh.userData.dispose = () => {
    geometry.dispose();
    material.userData.surface?.dispose();
    material.dispose();
  };
  return mesh;
}

/**
 * Scatter prop transforms across the buildable ground.
 *
 * Seeded, so the world is identical on every run: a scatter driven by
 * `Math.random` makes a bug report unreproducible and a test impossible.
 *
 * @param {{count?: number, seed?: number, minRadius?: number,
 *          maxRadius?: number, maxSlope?: number}} [options]
 * @returns {{x: number, y: number, z: number, rotation: number,
 *            scale: number}[]}
 */
export function scatterProps(options = {}) {
  const count = Math.max(0, Math.floor(Number(options.count ?? 60)));
  const random = createSeededRandom(Number(options.seed ?? 3));
  const minRadius = Number(options.minRadius ?? 16);
  const maxRadius = Number(options.maxRadius ?? WORLD_HALF * 0.62);
  const placed = [];
  // Bounded attempts, not a while-loop: a slope threshold that rejects
  // everything must fail as "fewer props" and never as a hang.
  for (let attempt = 0; attempt < count * 12 && placed.length < count; attempt += 1) {
    const angle = random() * Math.PI * 2;
    const radius = minRadius + random() * (maxRadius - minRadius);
    const x = Math.cos(angle) * radius;
    const z = Math.sin(angle) * radius;
    if (!isBuildable(x, z, Number(options.maxSlope ?? 0.42))) continue;
    placed.push({
      x,
      y: terrainHeight(x, z),
      z,
      rotation: random() * Math.PI * 2,
      scale: 0.85 + random() * 0.45,
    });
  }
  return placed;
}
