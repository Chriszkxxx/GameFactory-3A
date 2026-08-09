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

  /** @returns {object | null} */
  findEntry(reference) {
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

  #createGltfLoader() {
    const loader = new GLTFLoader();
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
