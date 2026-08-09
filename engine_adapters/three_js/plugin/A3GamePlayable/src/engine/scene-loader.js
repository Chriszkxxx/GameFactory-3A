/**
 * Builds a three.js scene from the adapter's published world scene
 * graph (`/assets/worlds/<world_id>.json`).
 *
 * The scene graph schema is owned by
 * `engine_adapters/three_js/world/_internal/specs.py`. This loader is
 * the only supported consumer; generated gameplay should call it instead
 * of hand-building environments.
 */

import * as THREE from 'three';

const LIGHT_FACTORIES = {
  AmbientLight: (spec) =>
    new THREE.AmbientLight(new THREE.Color(spec.color), spec.intensity),
  HemisphereLight: (spec) =>
    new THREE.HemisphereLight(
      new THREE.Color(spec.color),
      new THREE.Color(spec.options?.groundColor ?? '#404040'),
      spec.intensity,
    ),
  DirectionalLight: (spec) =>
    new THREE.DirectionalLight(new THREE.Color(spec.color), spec.intensity),
  PointLight: (spec) =>
    new THREE.PointLight(
      new THREE.Color(spec.color),
      spec.intensity,
      spec.options?.distance ?? 0,
      spec.options?.decay ?? 2,
    ),
  SpotLight: (spec) =>
    new THREE.SpotLight(
      new THREE.Color(spec.color),
      spec.intensity,
      spec.options?.distance ?? 0,
      spec.options?.angle ?? Math.PI / 6,
      spec.options?.penumbra ?? 0.2,
      spec.options?.decay ?? 2,
    ),
  RectAreaLight: (spec) =>
    new THREE.RectAreaLight(
      new THREE.Color(spec.color),
      spec.intensity,
      spec.options?.width ?? 4,
      spec.options?.height ?? 4,
    ),
};

const applyTransform = (object, transform) => {
  const { position, rotation, scale } = transform ?? {};
  if (position) object.position.set(position.x, position.y, position.z);
  if (rotation) object.rotation.set(rotation.x, rotation.y, rotation.z);
  if (scale) object.scale.set(scale.x, scale.y, scale.z);
  return object;
};

export class A3GameSceneLoader {
  /**
   * @param {{host: object, assets: object}} options
   */
  constructor(options) {
    if (!options?.host || !options?.assets) {
      throw new TypeError('A3GameSceneLoader requires { host, assets }');
    }
    this.host = options.host;
    this.assets = options.assets;
    /** @type {object | null} */
    this.sceneGraph = null;
    /** @type {Map<string, THREE.Object3D>} */
    this.entityObjects = new Map();
    /** @type {THREE.Object3D[]} */
    this.collisionTargets = [];
    /** @type {object[]} */
    this.spawnPoints = [];
    this.warnings = [];
  }

  /**
   * Load and build one published world.
   *
   * @param {string} sceneUrl for example `/assets/worlds/world_001.json`
   */
  async loadWorld(sceneUrl) {
    const response = await fetch(sceneUrl, { cache: 'no-cache' });
    if (!response.ok) {
      throw new Error(
        `World scene graph is unavailable at ${sceneUrl}: ` +
          `HTTP ${response.status}`,
      );
    }
    return this.buildWorld(await response.json());
  }

  /**
   * Build a world from an already-decoded scene graph document.
   *
   * @param {object} sceneGraph
   */
  async buildWorld(sceneGraph) {
    this.sceneGraph = sceneGraph;
    this.warnings = [];
    this.entityObjects.clear();
    this.collisionTargets = [];
    this.spawnPoints = (sceneGraph.spawn_points ?? []).map((item) => ({
      name: String(item.name ?? ''),
      position: { ...item.position },
      rotation: { ...item.rotation },
    }));

    await this.#applyEnvironment(sceneGraph.environment ?? {});
    this.#applyCamera(sceneGraph.camera ?? {});
    this.#applyLights(sceneGraph.lights ?? []);
    await this.#applyEntities(sceneGraph.entities ?? []);

    return {
      worldId: String(sceneGraph.world_id ?? ''),
      entityCount: this.entityObjects.size,
      collisionTargetCount: this.collisionTargets.length,
      spawnPoints: this.spawnPoints,
      warnings: [...this.warnings],
    };
  }

  /** @returns {THREE.Object3D | null} */
  getEntityObject(entityId) {
    return this.entityObjects.get(String(entityId)) ?? null;
  }

  /**
   * Resolve a spawn transform for a new participant.
   *
   * @param {number} [index] rotates through declared spawn points
   */
  resolveSpawnTransform(index = 0) {
    if (this.spawnPoints.length === 0) {
      return {
        position: { x: 0, y: 0, z: 0 },
        rotation: { x: 0, y: 0, z: 0 },
        scale: { x: 1, y: 1, z: 1 },
      };
    }
    const point = this.spawnPoints[index % this.spawnPoints.length];
    return {
      position: { ...point.position },
      rotation: { ...point.rotation },
      scale: { x: 1, y: 1, z: 1 },
    };
  }

  async #applyEnvironment(environment) {
    const artifactId = String(
      environment.environment_artifact_id ?? '',
    );
    let environmentTexture;
    if (artifactId) {
      const loaded = await this.assets
        .loadArtifact(artifactId)
        .catch(() => null);
      environmentTexture = loaded?.texture;
      if (!environmentTexture) {
        this.warnings.push(
          `Environment artifact ${artifactId} did not resolve to a ` +
            'texture; the scene keeps its solid background',
        );
      }
    }
    this.host.setEnvironment({
      background: environment.background,
      environmentTexture,
      backgroundIntensity: environment.background_intensity,
      toneMapping: environment.tone_mapping,
      toneMappingExposure: environment.tone_mapping_exposure,
    });
    this.host.setFog(environment.fog ?? {});
    if (this.host.renderer) {
      this.host.renderer.shadowMap.enabled = environment.shadows !== false;
    }
    await this.#applyGround(environment.ground ?? {});
  }

  async #applyGround(ground) {
    if (!ground || Object.keys(ground).length === 0) return;
    const size = Number(ground.size ?? 200);
    let mesh;
    if (ground.artifact_id) {
      const instance = await this.assets
        .instantiate(ground.artifact_id)
        .catch(() => null);
      mesh = instance?.object;
    }
    if (!mesh) {
      const material = new THREE.MeshStandardMaterial({
        color: new THREE.Color(ground.color ?? '#3a3a42'),
        roughness: Number(ground.roughness ?? 0.9),
        metalness: Number(ground.metalness ?? 0.05),
        side: THREE.DoubleSide,
      });
      if (ground.texture_url) {
        const texture = await this.assets.textureLoader.loadAsync(
          ground.texture_url,
        );
        const repeat = Number(ground.texture_repeat ??64);
        texture.wrapS = THREE.RepeatWrapping;
        texture.wrapT = THREE.RepeatWrapping;
        texture.repeat.set(repeat, repeat);
        texture.colorSpace = THREE.SRGBColorSpace;
        texture.anisotropy = 8;
        material.map = texture;
      }
      mesh = new THREE.Mesh(
        new THREE.PlaneGeometry(size, size),
        material,
      );
      mesh.rotation.x = -Math.PI / 2;
    }
    mesh.name = 'A3GameGround';
    mesh.receiveShadow = true;
    this.host.add(mesh, 'environment');
    this.collisionTargets.push(mesh);
  }

  #applyCamera(camera) {
    const target = camera.target ?? { x: 0, y: 1, z: 0 };
    const position = camera.position ?? { x: 0, y: 2, z: 8 };
    // The world spec owns the projection, so honour `camera.type`
    // instead of silently keeping the host's perspective default.
    const requested = String(camera.type ?? '').toLowerCase();
    if (
      requested.startsWith('ortho') &&
      !this.host.camera?.isOrthographicCamera
    ) {
      this.host.useOrthographicCamera({
        frustumHeight: Number(camera.frustum_height ?? 12),
      });
    } else if (
      requested.startsWith('persp') &&
      !this.host.camera?.isPerspectiveCamera
    ) {
      this.host.usePerspectiveCamera({ fov: Number(camera.fov ?? 50) });
    }
    if (this.host.camera) {
      if (this.host.camera.isPerspectiveCamera) {
        this.host.camera.fov = Number(camera.fov ?? this.host.camera.fov);
      }
      this.host.camera.near = Number(camera.near ?? this.host.camera.near);
      this.host.camera.far = Number(camera.far ?? this.host.camera.far);
      this.host.camera.position.set(position.x, position.y, position.z);
      this.host.camera.lookAt(target.x, target.y, target.z);
      this.host.camera.updateProjectionMatrix();
    }
    if (camera.controls === 'OrbitControls') {
      this.host.attachOrbitControls({ target });
    } else if (camera.controls === 'PointerLockControls') {
      this.host.attachPointerLockControls();
    }
  }

  #applyLights(lights) {
    for (const spec of lights) {
      const factory = LIGHT_FACTORIES[spec.type];
      if (!factory) {
        this.warnings.push(`Unsupported light type: ${spec.type}`);
        continue;
      }
      const light = factory(spec);
      light.name = spec.light_id ?? spec.type;
      if (spec.position) {
        light.position.set(
          spec.position.x,
          spec.position.y,
          spec.position.z,
        );
      }
      if (light.target && spec.target) {
        light.target.position.set(
          spec.target.x,
          spec.target.y,
          spec.target.z,
        );
        this.host.add(light.target, 'lights');
      }
      if (spec.cast_shadow && 'castShadow' in light) {
        light.castShadow = true;
        const shadow = light.shadow;
        if (shadow) {
          shadow.mapSize.set(2048, 2048);
          shadow.bias = -0.0005;
          if (shadow.camera?.isOrthographicCamera) {
            const extent = Number(spec.options?.shadow_extent ?? 40);
            shadow.camera.left = -extent;
            shadow.camera.right = extent;
            shadow.camera.top = extent;
            shadow.camera.bottom = -extent;
            shadow.camera.far = Number(
              spec.options?.shadow_far ?? 200,
            );
            shadow.camera.updateProjectionMatrix();
          }
        }
      }
      this.host.add(light, 'lights');
    }
  }

  async #applyEntities(entities) {
    for (const spec of entities) {
      if (spec.role === 'player_start') {
        this.spawnPoints.push({
          name: spec.entity_id,
          position: { ...(spec.transform?.position ?? {}) },
          rotation: { ...(spec.transform?.rotation ?? {}) },
        });
        continue;
      }
      if (!spec.artifact_id) {
        this.warnings.push(
          `Entity ${spec.entity_id} declares no artifact_id and was ` +
            'skipped',
        );
        continue;
      }
      const instance = await this.assets
        .instantiate(spec.artifact_id)
        .catch((error) => {
          this.warnings.push(
            `Entity ${spec.entity_id} failed to load: ${error.message}`,
          );
          return null;
        });
      if (!instance) continue;
      const object = instance.object;
      object.name = spec.entity_id;
      applyTransform(object, spec.transform);
      object.traverse((child) => {
        if (!child.isMesh) return;
        child.castShadow = spec.cast_shadow !== false;
        child.receiveShadow = spec.receive_shadow !== false;
      });
      object.userData.a3gameWorldEntity = {
        entityId: spec.entity_id,
        role: spec.role,
        collision: Boolean(spec.collision),
        parameters: { ...(spec.parameters ?? {}) },
        animations: instance.animations,
        behaviors: spec.behaviors ?? [],
      };
      this.host.add(object, 'environment');
      this.entityObjects.set(spec.entity_id, object);
      if (spec.collision) this.collisionTargets.push(object);
    }
  }
}
