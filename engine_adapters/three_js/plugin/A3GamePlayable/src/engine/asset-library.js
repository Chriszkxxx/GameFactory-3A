/**
 * Loads the adapter-written asset manifest and resolves artifacts into
 * three.js objects.
 *
 * Generated gameplay must reference assets by `artifact_id` or
 * `asset_id` from `/assets/manifest.json`. Hard-coded URLs break when
 * the adapter re-stages content.
 */

import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { KTX2Loader } from 'three/addons/loaders/KTX2Loader.js';
import { FBXLoader } from 'three/addons/loaders/FBXLoader.js';
import { OBJLoader } from 'three/addons/loaders/OBJLoader.js';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { HDRLoader } from 'three/addons/loaders/HDRLoader.js';
import { clone as cloneSkinned } from 'three/addons/utils/SkeletonUtils.js';
import { orientModel, prepareModel } from './visual-kit.js';

export class A3GameAssetLibrary {
  /**
   * @param {{manifestUrl?: string, dracoDecoderPath?: string,
   *          ktx2TranscoderPath?: string,
   *          requireManifest?: boolean,
   *          renderer?: THREE.WebGLRenderer}} [options]
   */
  constructor(options = {}) {
    this.manifestUrl = options.manifestUrl ?? '/assets/manifest.json';
    this.dracoDecoderPath = options.dracoDecoderPath ?? '/draco/';
    this.ktx2TranscoderPath = options.ktx2TranscoderPath ?? '/basis/';
    this.renderer = options.renderer ?? null;
    // A procedurally built game imports no artifact, so a project may
    // legitimately have no manifest yet. Set `requireManifest: true`
    // when the game genuinely cannot run without imported content.
    this.requireManifest = Boolean(options.requireManifest);

    /** @type {object | null} */
    this.manifest = null;
    /** Whether a manifest was found and indexed. */
    this.available = false;
    /** @type {string[]} */
    this.warnings = [];
    /** @type {Map<string, object>} */
    this.byArtifactId = new Map();
    /** @type {Map<string, object[]>} */
    this.byAssetId = new Map();
    /** @type {Map<string, object[]>} */
    this.byType = new Map();
    /** @type {Map<string, Promise<object>>} */
    this.cache = new Map();

    this.textureLoader = new THREE.TextureLoader();
    this.hdrLoader = new HDRLoader();
    this.audioLoader = new THREE.AudioLoader();
    this.fileLoaders = {
      glb: this.#createGltfLoader(),
      gltf: this.#createGltfLoader(),
      fbx: new FBXLoader(),
      obj: new OBJLoader(),
      stl: new STLLoader(),
    };
  }

  /**
   * Fetch and index the manifest.
   *
   * A missing manifest is not fatal unless `requireManifest` was set:
   * generated gameplay that builds its content from three.js primitives
   * still needs a library instance for the few artifacts it may later
   * receive. Inspect `available` and `warnings` to branch on it.
   */
  async load() {
    this.warnings = [];
    let manifest = null;
    try {
      const response = await fetch(this.manifestUrl, { cache: 'no-cache' });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      manifest = await response.json();
    } catch (error) {
      const reason =
        `Asset manifest is unavailable at ${this.manifestUrl}: ` +
        String(error?.message ?? error);
      if (this.requireManifest) throw new Error(reason);
      this.warnings.push(
        `${reason}; continuing with an empty asset library`,
      );
      this.manifest = null;
      this.available = false;
      this.byArtifactId.clear();
      this.byAssetId.clear();
      this.byType.clear();
      return this;
    }
    this.manifest = manifest;
    this.available = true;
    this.byArtifactId.clear();
    this.byAssetId.clear();
    this.byType.clear();
    for (const entry of Object.values(manifest?.assets ?? {})) {
      this.byArtifactId.set(entry.artifact_id, entry);
      const assetGroup = this.byAssetId.get(entry.asset_id) ?? [];
      assetGroup.push(entry);
      this.byAssetId.set(entry.asset_id, assetGroup);
      const typeGroup = this.byType.get(entry.type) ?? [];
      typeGroup.push(entry);
      this.byType.set(entry.type, typeGroup);
    }
    return this;
  }

  /** @returns {boolean} whether a reference resolves to a staged entry. */
  has(reference) {
    return this.findEntry(reference) !== null;
  }

  /** @returns {object} the manifest entry, or throws when unknown. */
  requireEntry(reference) {
    const entry = this.findEntry(reference);
    if (!entry) {
      throw new Error(
        `Unknown asset reference ${String(reference)}; the adapter must ` +
          'import and register it first',
      );
    }
    return entry;
  }

  /**
   * @returns {object | null}
   *
   * An **array** is a preference list: the first staged candidate wins.
   * That is what lets a game name the art it wants without knowing what
   * was actually produced — `['explorer_ranger', 'robot_expressive']`
   * uses the generated ranger when one exists, the CC0 stand-in when it
   * does not, and returns null so the caller falls back to a primitive
   * when neither has been staged. Nothing about that decision belongs in
   * gameplay code, and none of it needs a manifest to be present.
   */
  findEntry(reference) {
    if (Array.isArray(reference)) {
      for (const candidate of reference) {
        const entry = this.findEntry(candidate);
        if (entry) return entry;
      }
      return null;
    }
    const key = String(reference ?? '');
    if (this.byArtifactId.has(key)) return this.byArtifactId.get(key);
    const group = this.byAssetId.get(key);
    return group && group.length > 0 ? group[0] : null;
  }

  /** @returns {object[]} every entry of one asset type. */
  listByType(type) {
    return [...(this.byType.get(String(type)) ?? [])];
  }

  /**
   * Load an artifact once and cache the result.
   *
   * Meshes resolve to `{ object, animations, entry }`; textures resolve
   * to `{ texture, entry }`; audio resolves to `{ buffer, entry }`.
   *
   * @param {string} reference artifact_id or asset_id
   */
  async loadArtifact(reference) {
    const entry = this.requireEntry(reference);
    if (this.cache.has(entry.artifact_id)) {
      return this.cache.get(entry.artifact_id);
    }
    const promise = this.#loadEntry(entry).catch((error) => {
      this.cache.delete(entry.artifact_id);
      throw error;
    });
    this.cache.set(entry.artifact_id, promise);
    return promise;
  }

  /**
   * Return an independent instance of a mesh artifact.
   *
   * Skinned hierarchies are cloned with `SkeletonUtils.clone` so each
   * instance keeps its own bones and can play its own animations.
   *
   * @param {string} reference
   * @returns {Promise<{object: THREE.Object3D, animations: THREE.AnimationClip[], entry: object}>}
   */
  async instantiate(reference) {
    const loaded = await this.loadArtifact(reference);
    if (!loaded.object) {
      throw new Error(
        `Asset ${reference} is not an instantiable mesh artifact`,
      );
    }
    const skinned = Boolean(loaded.entry?.capabilities?.skinned);
    const object = skinned
      ? cloneSkinned(loaded.object)
      : loaded.object.clone(true);
    object.name = object.name || loaded.entry.asset_id;
    return {
      object,
      animations: (loaded.animations ?? []).map((clip) => clip.clone()),
      entry: loaded.entry,
    };
  }

  /**
   * Instantiate a model if it was staged, otherwise return `null`.
   *
   * A generated game is written to run with an empty manifest — a
   * mechanic task usually precedes its art — so "use the good model when
   * there is one" is the normal case rather than an edge case. The
   * returned object is scene-ready: rotated to face the runtime forward
   * axis, normalised to `height` if given, and shadow-enabled, which
   * `GLTFLoader` never does on its own.
   *
   * A staged-but-unloadable artifact records a warning and yields `null`
   * rather than throwing, because a broken asset must not cost the player
   * the whole game.
   *
   * @param {string | string[]} reference artifact_id, asset_id, or a
   *        preference list of either
   * @param {{height?: number, ground?: boolean, envMapIntensity?: number,
   *          castShadow?: boolean, receiveShadow?: boolean,
   *          frustumCulled?: boolean, forwardAxis?: string,
   *          yawOffsetDegrees?: number, orient?: boolean}} [options]
   * @returns {Promise<{object: THREE.Object3D,
   *                    animations: THREE.AnimationClip[],
   *                    entry: object,
   *                    orientation: object} | null>}
   */
  async tryInstantiate(reference, options = {}) {
    if (!this.has(reference)) return null;
    try {
      const loaded = await this.instantiate(reference);
      const prepared = this.#prepare(loaded, options);
      return prepared;
    } catch (error) {
      this.warnings.push(
        `Staged asset ${String(reference)} failed to load: ` +
          String(error?.message ?? error),
      );
      return null;
    }
  }

  /**
   * Instantiate a staged model, or build a procedural stand-in.
   *
   * The counterpart to `tryInstantiate` for content whose visual is
   * created from scratch rather than swapped in afterwards. Branching on
   * `has()` at every call site duplicates this logic and usually forgets
   * the shadow flags.
   *
   * @param {string} reference artifact_id or asset_id
   * @param {() => THREE.Object3D} fallback builds the primitive version
   * @param {object} [options] as `tryInstantiate`
   * @returns {Promise<{object: THREE.Object3D,
   *                    animations: THREE.AnimationClip[],
   *                    source: 'asset' | 'fallback',
   *                    entry: object | null}>}
   */
  async instantiateOrBuild(reference, fallback, options = {}) {
    if (typeof fallback !== 'function') {
      throw new TypeError(
        'instantiateOrBuild requires a fallback factory, so a game ' +
          'stays runnable before its art is imported',
      );
    }
    const loaded = await this.tryInstantiate(reference, options);
    if (loaded) return { ...loaded, source: 'asset' };

    // A procedural body is authored by the game, so it already faces the
    // runtime forward axis: no orientation correction applies to it.
    const object = fallback();
    if (!object?.isObject3D) {
      throw new TypeError('The fallback factory must return an Object3D');
    }
    return {
      object,
      animations: [],
      source: 'fallback',
      entry: null,
      orientation: {},
    };
  }

  /**
   * Apply an adapter-written PBR material binding to an object subtree.
   *
   * @param {THREE.Object3D} object
   * @param {string} bindingUrl for example `/assets/bindings/<id>.json`
   */
  async applyMaterialBinding(object, bindingUrl) {
    const response = await fetch(bindingUrl, { cache: 'no-cache' });
    if (!response.ok) {
      throw new Error(
        `Material binding is unavailable at ${bindingUrl}: ` +
          `HTTP ${response.status}`,
      );
    }
    const binding = await response.json();
    const textures = {};
    for (const [slot, url] of Object.entries(binding.textures ?? {})) {
      const texture = await this.textureLoader.loadAsync(url);
      texture.colorSpace =
        slot === 'map' || slot === 'emissiveMap'
          ? THREE.SRGBColorSpace
          : THREE.NoColorSpace;
      textures[slot] = texture;
    }
    object.traverse((child) => {
      if (!child.isMesh) return;
      const materials = Array.isArray(child.material)
        ? child.material
        : [child.material];
      for (const material of materials) {
        if (!material) continue;
        Object.assign(material, textures);
        for (const [key, value] of Object.entries(binding.scalars ?? {})) {
          if (key in material) material[key] = Number(value);
        }
        for (const [key, value] of Object.entries(binding.colors ?? {})) {
          if (material[key]?.isColor) material[key].set(value);
        }
        for (const [key, value] of Object.entries(binding.flags ?? {})) {
          if (key in material) material[key] = value;
        }
        material.needsUpdate = true;
      }
    });
    return binding;
  }

  /** Release every cached GPU resource held by the library. */
  async dispose() {
    for (const promise of this.cache.values()) {
      const loaded = await promise.catch(() => null);
      loaded?.texture?.dispose?.();
      loaded?.object?.traverse?.((child) => {
        child.geometry?.dispose?.();
        const materials = Array.isArray(child.material)
          ? child.material
          : child.material
            ? [child.material]
            : [];
        for (const material of materials) material.dispose?.();
      });
    }
    this.cache.clear();
    this.fileLoaders.glb?.dracoLoader?.dispose?.();
  }

  /**
   * Turn a loaded artifact into scene-ready content.
   *
   * Two facts the adapter recorded are applied here, because neither can
   * be recovered from the glTF at runtime:
   *
   * - **facing**, which is rotated into the runtime convention;
   * - **scale**, when the reviewer recorded a real-world height and the
   *   caller did not override it.
   *
   * The correction is applied to the *model*, inside a wrapper that is
   * handed back as the object. That split is deliberate: gameplay code
   * and world specs both assign `rotation.y` on the object they are
   * given, and rotating the same node the correction lives on would undo
   * it on the first frame. The wrapper is the game's to turn; the model
   * inside it is already facing the right way.
   *
   * With no orientation recorded this reduces to the previous behaviour
   * exactly: no wrapper, no rotation, no implied height.
   */
  #prepare(loaded, options = {}) {
    const orientation = { ...(loaded.entry?.orientation ?? {}) };
    const forwardAxis = options.forwardAxis ?? orientation.forward_axis ?? '';
    const yaw = Number(
      options.yawOffsetDegrees ?? orientation.yaw_offset_degrees ?? 0,
    );
    const pitch = Number(
      options.pitchOffsetDegrees ?? orientation.pitch_offset_degrees ?? 0,
    );
    const roll = Number(
      options.rollOffsetDegrees ?? orientation.roll_offset_degrees ?? 0,
    );
    const rotates =
      options.orient !== false &&
      (Boolean(forwardAxis) || yaw !== 0 || pitch !== 0 || roll !== 0);

    const hint = Number(orientation.scale_hint_metres);
    const height =
      options.height ?? (Number.isFinite(hint) && hint > 0 ? hint : undefined);

    let object = loaded.object;
    if (rotates) {
      const model = object;
      orientModel(model, {
        forwardAxis,
        runtimeForwardAxis: orientation.runtime_forward_axis,
        yawOffsetDegrees: yaw,
        pitchOffsetDegrees: pitch,
        rollOffsetDegrees: roll,
      });
      object = new THREE.Group();
      object.name = `${model.name || loaded.entry?.asset_id || 'asset'}_oriented`;
      object.add(model);
    }

    prepareModel(object, { ...options, height, orientation: {}, forwardAxis: '' });

    if (!forwardAxis && orientation.needs_vision_check) {
      this.warnings.push(
        `Asset ${String(loaded.entry?.asset_id ?? '')} has no verified ` +
          'facing axis, so it is placed exactly as authored. Render it ' +
          'with three.preview.orientation_report and record the answer ' +
          'with three.assets.set_orientation if it faces the wrong way.',
      );
    }
    return { ...loaded, object, model: loaded.object, orientation };
  }

  #createGltfLoader() {    const loader = new GLTFLoader();
    const draco = new DRACOLoader();
    draco.setDecoderPath(this.dracoDecoderPath);
    loader.setDRACOLoader(draco);
    if (this.renderer) {
      const ktx2 = new KTX2Loader()
        .setTranscoderPath(this.ktx2TranscoderPath)
        .detectSupport(this.renderer);
      loader.setKTX2Loader(ktx2);
    }
    return loader;
  }

  async #loadEntry(entry) {
    const url = entry.url;
    const representation = String(entry.representation ?? '');
    if (['png', 'jpeg', 'webp', 'tga'].includes(representation)) {
      const texture = await this.textureLoader.loadAsync(url);
      texture.colorSpace = THREE.SRGBColorSpace;
      return { texture, entry };
    }
    if (['hdr', 'exr'].includes(representation)) {
      const texture = await this.hdrLoader.loadAsync(url);
      texture.mapping = THREE.EquirectangularReflectionMapping;
      return { texture, entry };
    }
    if (['mp3', 'ogg', 'wav', 'm4a'].includes(representation)) {
      const buffer = await this.audioLoader.loadAsync(url);
      return { buffer, entry };
    }
    if (representation === 'json') {
      const response = await fetch(url, { cache: 'no-cache' });
      return { data: await response.json(), entry };
    }

    const suffix = url.split('.').pop()?.toLowerCase() ?? '';
    const loader = this.fileLoaders[suffix];
    if (!loader) {
      throw new Error(
        `No three.js loader is configured for ${url}; convert the ` +
          'artifact to glTF/GLB before runtime use',
      );
    }
    const result = await loader.loadAsync(url);
    if (result?.scene) {
      return {
        object: result.scene,
        animations: result.animations ?? [],
        entry,
        gltf: result,
      };
    }
    if (result?.isBufferGeometry) {
      const mesh = new THREE.Mesh(
        result,
        new THREE.MeshStandardMaterial({ color: 0xcccccc }),
      );
      mesh.name = entry.asset_id;
      return { object: mesh, animations: [], entry };
    }
    return { object: result, animations: result?.animations ?? [], entry };
  }
}
