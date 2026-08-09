/**
 * Look-and-feel building blocks shared by every generated game.
 *
 * A generated three.js game usually has no imported art, so its content
 * comes from primitives. Primitives are not the reason such a game looks
 * like programmer art — these four things are:
 *
 *   1. no image-based lighting, so PBR materials have nothing to reflect
 *      and read as flat plastic;
 *   2. hard 90-degree edges, which never occur on a manufactured object;
 *   3. default material parameters, i.e. `roughness: 1, metalness: 0`
 *      for every surface in the scene;
 *   4. an unfitted shadow camera, which yields either no shadow or a
 *      blocky one.
 *
 * This module fixes 2-4 and is game-neutral;
 * `A3GameRuntimeHost.setEnvironment({ preset })` fixes 1.
 *
 * It also owns the utilities that make an *imported* model usable, since
 * every glTF arrives in whatever unit its author chose.
 */

import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

/**
 * Physically plausible starting points for the materials a game needs.
 *
 * The numbers matter more than they look: `roughness` below ~0.05 is
 * mirror-like and reads as a bug, and a `metalness` between 0.1 and 0.9
 * describes no real material — a surface is either a conductor or it is
 * not. Dielectrics therefore stay at `metalness: 0` and get their shine
 * from `clearcoat` instead.
 */
export const A3GameMaterialPreset = Object.freeze({
  METAL: 'metal',
  PAINTED_METAL: 'painted_metal',
  GUNMETAL: 'gunmetal',
  PLASTIC: 'plastic',
  RUBBER: 'rubber',
  CLOTH: 'cloth',
  LEATHER: 'leather',
  WOOD: 'wood',
  STONE: 'stone',
  CONCRETE: 'concrete',
  TARMAC: 'tarmac',
  GRASS: 'grass',
  SAND: 'sand',
  GLASS: 'glass',
  EMISSIVE: 'emissive',
});

const PRESET_PARAMETERS = Object.freeze({
  metal: { metalness: 1, roughness: 0.28 },
  painted_metal: {
    metalness: 0,
    roughness: 0.42,
    clearcoat: 1,
    clearcoatRoughness: 0.12,
  },
  gunmetal: { metalness: 1, roughness: 0.42 },
  plastic: {
    metalness: 0,
    roughness: 0.55,
    clearcoat: 0.6,
    clearcoatRoughness: 0.3,
  },
  rubber: { metalness: 0, roughness: 0.92 },
  cloth: { metalness: 0, roughness: 0.86, sheen: 0.5 },
  leather: { metalness: 0, roughness: 0.7, sheen: 0.2 },
  wood: { metalness: 0, roughness: 0.62 },
  stone: { metalness: 0, roughness: 0.85 },
  concrete: { metalness: 0, roughness: 0.9 },
  tarmac: { metalness: 0, roughness: 0.78 },
  grass: { metalness: 0, roughness: 0.95 },
  sand: { metalness: 0, roughness: 0.98 },
  glass: {
    metalness: 0,
    roughness: 0.05,
    transmission: 0.95,
    thickness: 0.4,
    transparent: true,
  },
  emissive: { metalness: 0, roughness: 0.4, emissiveIntensity: 2 },
});

/** Presets that need `MeshPhysicalMaterial` rather than the standard one. */
const PHYSICAL_PRESETS = new Set([
  'painted_metal',
  'plastic',
  'cloth',
  'leather',
  'glass',
]);

/**
 * Build a material from a preset.
 *
 * @param {string} preset a value of `A3GameMaterialPreset`
 * @param {object} [overrides] any material parameter, e.g. `{ color }`
 * @returns {THREE.MeshStandardMaterial | THREE.MeshPhysicalMaterial}
 */
export function createMaterial(preset, overrides = {}) {
  const key = String(preset ?? '').toLowerCase();
  const base = PRESET_PARAMETERS[key];
  if (!base) {
    throw new Error(
      `Unknown material preset ${String(preset)}; expected one of ` +
        Object.values(A3GameMaterialPreset).join(', '),
    );
  }
  const parameters = { color: 0xffffff, ...base, ...overrides };
  if (parameters.emissive === undefined && key === 'emissive') {
    parameters.emissive = parameters.color;
  }
  const Material = PHYSICAL_PRESETS.has(key)
    ? THREE.MeshPhysicalMaterial
    : THREE.MeshStandardMaterial;
  const material = new Material(parameters);
  material.name = `A3Game_${key}`;
  return material;
}

/**
 * A box with bevelled edges.
 *
 * A bevel is the cheapest possible upgrade to a blocky prop: a real
 * edge catches a highlight, and a mathematically sharp one cannot.
 *
 * @param {{width?: number, height?: number, depth?: number,
 *          radius?: number, segments?: number,
 *          material?: THREE.Material, preset?: string,
 *          color?: number | string,
 *          castShadow?: boolean, receiveShadow?: boolean,
 *          name?: string}} [options]
 * @returns {THREE.Mesh}
 */
export function createRoundedBox(options = {}) {
  const width = Number(options.width ??1);
  const height = Number(options.height ?? 1);
  const depth = Number(options.depth ?? 1);
  // A radius at or above half of the smallest side collapses the box, so
  // clamp instead of letting the geometry degenerate.
  const smallest = Math.min(width, height, depth);
  const radius = Math.min(
    Number(options.radius ?? Math.min(0.06, smallest * 0.18)),
    smallest * 0.499,
  );
  const geometry = new RoundedBoxGeometry(
    width,
    height,
    depth,
    Number(options.segments ?? 3),
    radius,
  );
  const material =
    options.material ??
    createMaterial(options.preset ?? A3GameMaterialPreset.PLASTIC, {
      color: options.color ?? 0xb9c0cc,
    });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.castShadow = options.castShadow !== false;
  mesh.receiveShadow = options.receiveShadow !== false;
  if (options.name) mesh.name = options.name;
  return mesh;
}

/**
 * A directional "sun" whose shadow camera actually fits the play area.
 *
 * The default `DirectionalLight` shadow camera is a 10-metre box at the
 * origin. A200-metre race track therefore gets no shadow at all, and
 * shrinking the map to fit is not an option — so the extent is an
 * explicit parameter here.
 *
 * `normalBias` is set rather than `bias`: it scales with the geometry and
 * removes the shadow acne that a flat `bias` fixes only for one distance.
 *
 * @param {{color?: number | string, intensity?: number,
 *          position?: {x: number, y: number, z: number},
 *          target?: {x: number, y: number, z: number},
 *          radius?: number, mapSize?: number,
 *          near?: number, far?: number,
 *          castShadow?: boolean}} [options]
 * @returns {THREE.DirectionalLight}
 */
export function createSunLight(options = {}) {
  const light = new THREE.DirectionalLight(
    options.color ?? 0xfff3e0,
    Number(options.intensity ?? 2.4),
  );
  const position = options.position ?? { x: 40, y: 70, z: 30 };
  light.position.set(position.x, position.y, position.z);
  const target = options.target ?? { x: 0, y: 0, z: 0 };
  light.target.position.set(target.x, target.y, target.z);
  light.name = 'A3GameSun';

  light.castShadow = options.castShadow !== false;
  if (light.castShadow) {
    const radius = Math.max(1, Number(options.radius ?? 40));
    const mapSize = Number(options.mapSize ?? 2048);
    light.shadow.mapSize.set(mapSize, mapSize);
    light.shadow.camera.left = -radius;
    light.shadow.camera.right = radius;
    light.shadow.camera.top = radius;
    light.shadow.camera.bottom = -radius;
    light.shadow.camera.near = Number(options.near ?? 0.5);
    light.shadow.camera.far = Number(
      options.far ?? light.position.length() + radius * 2,
    );
    light.shadow.normalBias = 0.035;
    light.shadow.bias = -0.0002;
    light.shadow.camera.updateProjectionMatrix();
  }
  return light;
}

/**
 * Sky and bounce fill, so surfaces facing away from the sun are not
 * black.
 *
 * This is not a substitute for an environment map — it has no
 * reflections — but it is what keeps the *unlit* side of an object
 * readable, and it costs one draw of nothing.
 *
 * @param {{skyColor?: number | string, groundColor?: number | string,
 *          intensity?: number}} [options]
 * @returns {THREE.HemisphereLight}
 */
export function createFillLight(options = {}) {
  const light = new THREE.HemisphereLight(
    options.skyColor ?? 0x9fc4ff,
    options.groundColor ?? 0x4a4034,
    Number(options.intensity ?? 0.6),
  );
  light.name = 'A3GameFill';
  return light;
}

/**
 * Measure an object's world-space bounding box.
 *
 * @param {THREE.Object3D} object
 * @returns {THREE.Box3}
 */
export function measureObject(object) {
  object.updateMatrixWorld(true);
  return new THREE.Box3().setFromObject(object);
}

/**
 * Scale an object uniformly so that it stands a given number of metres
 * tall.
 *
 * Every glTF arrives in whatever unit its author used, and the spread is
 * not subtle: of three CC0 models staged for these games, one is6.6
 * units tall, one is 1.5, and one is 0.07. Dropping any of them into a
 * scene unscaled produces either a skyscraper or an invisible speck, so
 * normalising by a gameplay dimension — not by a magic constant — is the
 * only reliable way to place imported content.
 *
 * @param {THREE.Object3D} object
 * @param {number} metres desired world-space height
 * @returns {THREE.Object3D} the same object, scaled
 */
export function fitToHeight(object, metres) {
  const target = Number(metres);
  if (!Number.isFinite(target) || target <= 0) {
    throw new RangeError('fitToHeight requires a positive height');
  }
  const size = measureObject(object).getSize(new THREE.Vector3());
  if (!(size.y > 1e-9)) return object;
  const factor = target / size.y;
  object.scale.multiplyScalar(factor);
  object.updateMatrixWorld(true);
  return object;
}

/**
 * Shift an object so its lowest point sits on y = 0 and it is centred
 * horizontally.
 *
 * A model's origin is wherever its author left it — often the hips, or
 * the corner of the bounding box. Gameplay code, by contrast, always
 * wants to place a character by its feet.
 *
 * @param {THREE.Object3D} object
 * @param {{horizontal?: boolean}} [options]
 * @returns {THREE.Object3D}
 */
export function groundObject(object, options = {}) {
  const box = measureObject(object);
  if (box.isEmpty()) return object;
  object.position.y -= box.min.y;
  if (options.horizontal !== false) {
    const centre = box.getCenter(new THREE.Vector3());
    object.position.x -= centre.x;
    object.position.z -= centre.z;
  }
  object.updateMatrixWorld(true);
  return object;
}

/**
 * Make a freshly loaded model behave like scene content.
 *
 * A glTF mesh does not cast or receive shadows until told to: the format
 * has no such concept, so `GLTFLoader` leaves both flags false. A model
 * that lights correctly but floats shadowless above the floor is the
 * single most common "why does my imported asset look wrong" symptom.
 *
 * @param {THREE.Object3D} object
 * @param {{height?: number, ground?: boolean,
 *          castShadow?: boolean, receiveShadow?: boolean,
 *          envMapIntensity?: number, frustumCulled?: boolean}} [options]
 * @returns {THREE.Object3D} the same object
 */
export function prepareModel(object, options = {}) {
  if (!object) throw new TypeError('prepareModel requires an Object3D');
  if (options.height !== undefined) fitToHeight(object, options.height);
  if (options.ground) groundObject(object, { horizontal: false });

  const cast = options.castShadow !== false;
  const receive = options.receiveShadow !== false;
  object.traverse((child) => {
    if (!child.isMesh && !child.isSkinnedMesh) return;
    child.castShadow = cast;
    child.receiveShadow = receive;
    if (options.frustumCulled !== undefined) {
      // A skinned mesh animated far from its bind pose is culled using
      // stale bounds, which makes a character blink out at screen edges.
      child.frustumCulled = options.frustumCulled;
    }
    const materials = Array.isArray(child.material)
      ? child.material
      : child.material
        ? [child.material]
        : [];
    for (const material of materials) {
      if (options.envMapIntensity !== undefined && 'envMapIntensity' in material) {
        material.envMapIntensity = Number(options.envMapIntensity);
      }
    }
  });
  return object;
}

/**
 * A soft blob of shadow under an object.
 *
 * Real-time shadow maps are expensive and, at a distance, blocky. A
 * radial-gradient decal on the floor grounds an object convincingly for
 * one draw call, which is why almost every mobile game ships one. It also
 * works when shadow maps are disabled entirely.
 *
 * @param {{radius?: number, opacity?: number, color?: number | string,
 *          resolution?: number}} [options]
 * @returns {THREE.Mesh} lying in the XZ plane, to be positioned by caller
 */
export function createContactShadow(options = {}) {
  const radius = Number(options.radius ?? 0.6);
  const resolution = Number(options.resolution ?? 128);
  const texture = createRadialGradientTexture({
    resolution,
    color: options.color ?? '#000000',
  });
  const material = new THREE.MeshBasicMaterial({
    map: texture,
    transparent: true,
    opacity: Number(options.opacity ?? 0.45),
    depthWrite: false,
  });
  const mesh = new THREE.Mesh(
    new THREE.PlaneGeometry(radius * 2, radius * 2),
    material,
  );
  mesh.rotation.x = -Math.PI / 2;
  mesh.renderOrder = -1;
  mesh.name = 'A3GameContactShadow';
  return mesh;
}

/**
 * Draw a radial gradient into a texture.
 *
 * Canvas work must stay inside a factory like this one: a module that
 * touches `document` at import time cannot be loaded by a headless test.
 *
 * @param {{resolution?: number, color?: string}} [options]
 * @returns {THREE.Texture}
 */
export function createRadialGradientTexture(options = {}) {
  const resolution = Number(options.resolution ?? 128);
  const canvas = document.createElement('canvas');
  canvas.width = resolution;
  canvas.height = resolution;
  const context = canvas.getContext('2d');
  const half = resolution / 2;
  const gradient = context.createRadialGradient(half, half, 0, half, half, half);
  const color = String(options.color ?? '#000000');
  gradient.addColorStop(0, color);
  gradient.addColorStop(1, 'rgba(0,0,0,0)');
  context.fillStyle = gradient;
  context.fillRect(0, 0, resolution, resolution);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

/**
 * Deterministic pseudo-random sequence.
 *
 * Procedural scenery must look identical on every reload and in every
 * test run, which `Math.random` cannot promise. Mulberry32 is three
 * lines and has a long enough period for scene dressing.
 *
 * @param {number} seed
 * @returns {() => number} values in [0, 1)
 */
export function createSeededRandom(seed = 1) {
  let state = Number(seed) >>> 0 || 1;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let value = Math.imul(state ^ (state >>> 15), 1 | state);
    value = (value + Math.imul(value ^ (value >>> 7), 61 | value)) ^ value;
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}
