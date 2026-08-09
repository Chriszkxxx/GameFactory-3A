/**
 * Owns the WebGL renderer, scene, camera, controls, and frame loop.
 *
 * Unreal supplies this natively; on the web the framework must own it.
 * `A3GameRuntimeHost` is deliberately game-neutral: it renders, ticks,
 * resizes, picks, and disposes. It defines no player, weapon, vehicle,
 * or combat rule.
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { PointerLockControls } from 'three/addons/controls/PointerLockControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { Sky } from 'three/addons/objects/Sky.js';

/**
 * Procedural environments, so image-based lighting needs no `.hdr`.
 *
 * Without an environment map a PBR material has nothing to reflect: it
 * loses every highlight and reads as flat plastic no matter how the
 * lights are placed. This is the largest single difference between a
 * generated three.js scene that looks cheap and one that does not, and
 * both of these presets are generated on the GPU at boot from geometry
 * three.js already ships.
 */
export const A3GameEnvironmentPreset = Object.freeze({
  /** Neutral studio box. Interiors, arenas, menus, product-like views. */
  ROOM: 'room',
  /** Physical sky with a sun. Outdoor games. */
  SKY: 'sky',
  /** No environment map. */
  NONE: 'none',
});

const TONE_MAPPINGS = Object.freeze({
  NoToneMapping: THREE.NoToneMapping,
  LinearToneMapping: THREE.LinearToneMapping,
  ReinhardToneMapping: THREE.ReinhardToneMapping,
  CineonToneMapping: THREE.CineonToneMapping,
  ACESFilmicToneMapping: THREE.ACESFilmicToneMapping,
  AgXToneMapping: THREE.AgXToneMapping,
  NeutralToneMapping: THREE.NeutralToneMapping,
});

const resolveElement = (target) => {
  if (!target) return null;
  if (typeof target === 'string') return document.querySelector(target);
  return target;
};

export class A3GameRuntimeHost {
  /**
   * @param {{container: string | HTMLElement,
   *          hudContainer?: string | HTMLElement,
   *          antialias?: boolean,
   *          shadows?: boolean,
   *          pixelRatioCap?: number,
   *          clearColor?: number | string,
   *          toneMapping?: keyof typeof TONE_MAPPINGS,
   *          toneMappingExposure?: number,
   *          cameraType?: 'perspective' | 'orthographic',
   *          frustumHeight?: number,
   *          fov?: number, near?: number, far?: number,
   *          fixedTimeStep?: number}} options
   */
  constructor(options = {}) {
    this.options = {
      antialias: true,
      shadows: true,
      pixelRatioCap: 2,
      clearColor: 0x101014,
      toneMapping: 'NeutralToneMapping',
      toneMappingExposure: 1,
      cameraType: 'perspective',
      frustumHeight: 12,
      fov: 50,
      near: 0.1,
      far: 2000,
      fixedTimeStep: 0,
      ...options,
    };
    this.container = resolveElement(options.container);
    this.hudContainer = resolveElement(options.hudContainer);

    /** @type {THREE.WebGLRenderer | null} */
    this.renderer = null;
    /** @type {THREE.Scene | null} */
    this.scene = null;
    /** @type {THREE.PerspectiveCamera | THREE.OrthographicCamera | null} */
    this.camera = null;
    /** @type {OrbitControls | PointerLockControls | null} */
    this.controls = null;
    /**
     * Environment map built by a preset, owned by this host.
     *
     * @type {THREE.Texture | null}
     */
    this.generatedEnvironment = null;
    this.clock = new THREE.Clock();
    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();

    this.frameHandle = null;
    this.running = false;
    this.frameCount = 0;
    this.elapsedSeconds = 0;
    this.accumulator = 0;

    /** @type {Set<(delta: number, elapsed: number) => void>} */
    this.tickListeners = new Set();
    /** @type {Set<(size: {width: number, height: number}) => void>} */
    this.resizeListeners = new Set();
    /** @type {Map<string, THREE.Object3D>} */
    this.namedRoots = new Map();
    this.resizeObserver = null;
    this.onWindowResize = null;
  }

  /** Create renderer, scene, and camera. Call before `start()`. */
  async init() {
    if (!this.container) {
      throw new Error(
        'A3GameRuntimeHost requires an existing container element',
      );
    }
    const { clientWidth, clientHeight } = this.#size();

    this.renderer = new THREE.WebGLRenderer({
      antialias: this.options.antialias,
      alpha: false,
      powerPreference: 'high-performance',
      preserveDrawingBuffer: true,
    });
    this.renderer.setClearColor(new THREE.Color(this.options.clearColor));
    this.renderer.setPixelRatio(
      Math.min(window.devicePixelRatio || 1, this.options.pixelRatioCap),
    );
    this.renderer.setSize(clientWidth, clientHeight);
    this.renderer.toneMapping =
      TONE_MAPPINGS[this.options.toneMapping] ?? THREE.NeutralToneMapping;
    this.renderer.toneMappingExposure = this.options.toneMappingExposure;
    this.renderer.shadowMap.enabled = Boolean(this.options.shadows);
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.container.appendChild(this.renderer.domElement);

    this.scene = new THREE.Scene();
    this.scene.name = 'A3GameWorld';

    this.camera = this.#createCamera(
      this.options.cameraType,
      clientWidth / Math.max(1, clientHeight),
    );
    this.camera.name = 'A3GameCamera';
    this.camera.position.set(0, 2, 8);
    this.camera.lookAt(0, 1, 0);

    this.#observeResize();
    return this;
  }

  /**
   * Replace the active camera with a perspective camera.
   *
   * The new camera inherits the current position and any parent, so a
   * game may switch projection at runtime without re-parenting.
   *
   * @param {{fov?: number, near?: number, far?: number}} [options]
   */
  usePerspectiveCamera(options = {}) {
    Object.assign(this.options, {
      cameraType: 'perspective',
      fov: Number(options.fov ?? this.options.fov),
      near: Number(options.near ?? this.options.near),
      far: Number(options.far ?? this.options.far),
    });
    return this.#swapCamera('perspective');
  }

  /**
   * Replace the active camera with an orthographic camera.
   *
   * `frustumHeight` is the number of world-space metres visible
   * vertically; width follows the container aspect ratio. This is what a
   * side-scrolling or isometric game needs, and it is what the world
   * spec's `camera.type = 'orthographic'` selects.
   *
   * @param {{frustumHeight?: number, near?: number, far?: number}} [options]
   */
  useOrthographicCamera(options = {}) {
    Object.assign(this.options, {
      cameraType: 'orthographic',
      frustumHeight: Math.max(
        0.01,
        Number(options.frustumHeight ?? this.options.frustumHeight),
      ),
      near: Number(options.near ?? -this.options.far),
      far: Number(options.far ?? this.options.far),
    });
    return this.#swapCamera('orthographic');
  }

  /** Begin the render loop. Safe to call once. */
  start() {
    if (this.running) return this;
    if (!this.renderer || !this.scene || !this.camera) {
      throw new Error('A3GameRuntimeHost.init() must run before start()');
    }
    this.running = true;
    this.clock.start();
    const loop = () => {
      if (!this.running) return;
      this.frameHandle = requestAnimationFrame(loop);
      this.tick();
    };
    this.frameHandle = requestAnimationFrame(loop);
    return this;
  }

  /** Pause the render loop without releasing GPU resources. */
  stop() {
    this.running = false;
    if (this.frameHandle !== null) {
      cancelAnimationFrame(this.frameHandle);
      this.frameHandle = null;
    }
    return this;
  }

  /**
   * Advance and render exactly one frame.
   *
   * Exposed so headless tests can step the simulation deterministically
   * without a real animation frame.
   *
   * @param {number} [forcedDelta] seconds
   */
  tick(forcedDelta) {
    const delta =
      forcedDelta === undefined
        ? Math.min(this.clock.getDelta(), 0.1)
        : Math.max(0, Number(forcedDelta) || 0);
    this.elapsedSeconds += delta;
    this.frameCount += 1;

    const step = this.options.fixedTimeStep;
    if (step > 0) {
      this.accumulator += delta;
      while (this.accumulator >= step) {
        this.#emitTick(step);
        this.accumulator -= step;
      }
    } else {
      this.#emitTick(delta);
    }

    if (this.controls && typeof this.controls.update === 'function') {
      this.controls.update(delta);
    }
    this.renderer?.render(this.scene, this.camera);
    return this;
  }

  /**
   * Subscribe to the frame tick.
   *
   * @param {(delta: number, elapsed: number) => void} listener
   * @returns {() => void} unsubscribe
   */
  onTick(listener) {
    if (typeof listener !== 'function') {
      throw new TypeError('onTick requires a function');
    }
    this.tickListeners.add(listener);
    return () => this.tickListeners.delete(listener);
  }

  /** @param {(size: {width: number, height: number}) => void} listener */
  onResize(listener) {
    if (typeof listener !== 'function') {
      throw new TypeError('onResize requires a function');
    }
    this.resizeListeners.add(listener);
    return () => this.resizeListeners.delete(listener);
  }

  /** Add an object under a stable named root, creating the root once. */
  add(object, rootName = 'entities') {
    if (!this.scene) throw new Error('init() must run before add()');
    let root = this.namedRoots.get(rootName);
    if (!root) {
      root = new THREE.Group();
      root.name = `A3Game_${rootName}`;
      this.scene.add(root);
      this.namedRoots.set(rootName, root);
    }
    root.add(object);
    return object;
  }

  remove(object) {
    object?.parent?.remove(object);
    return this;
  }

  /** @returns {THREE.Group} the named root group, created on demand. */
  getRoot(rootName = 'entities') {
    if (!this.namedRoots.has(rootName)) {
      this.add(new THREE.Group(), rootName);
    }
    return this.namedRoots.get(rootName);
  }

  /**
   * Attach orbit controls for a spectator or third-person camera.
   *
   * @param {{target?: {x: number, y: number, z: number},
   *          enableDamping?: boolean, maxPolarAngle?: number,
   *          minDistance?: number, maxDistance?: number}} [options]
   */
  attachOrbitControls(options = {}) {
    this.detachControls();
    const controls = new OrbitControls(
      this.camera,
      this.renderer.domElement,
    );
    controls.enableDamping = options.enableDamping !== false;
    controls.dampingFactor = 0.08;
    controls.screenSpacePanning = false;
    if (options.maxPolarAngle !== undefined) {
      controls.maxPolarAngle = options.maxPolarAngle;
    }
    if (options.minDistance !== undefined) {
      controls.minDistance = options.minDistance;
    }
    if (options.maxDistance !== undefined) {
      controls.maxDistance = options.maxDistance;
    }
    const target = options.target ?? { x: 0, y: 1, z: 0 };
    controls.target.set(target.x, target.y, target.z);
    controls.update();
    this.controls = controls;
    return controls;
  }

  /**
   * Attach pointer-lock controls for a first-person camera.
   *
   * Use this only when `PointerLockControls` should own the camera
   * orientation. A game that derives yaw/pitch from the normalized input
   * frame must call `requestPointerLock()` instead, otherwise both the
   * controls and the game write to the same camera every frame.
   */
  attachPointerLockControls() {
    this.detachControls();
    const controls = new PointerLockControls(this.camera, this.container);
    this.controls = controls;
    return controls;
  }

  /**
   * Capture the mouse without installing any camera controller.
   *
   * This is the primitive an FPS built on `A3GameInputRouter` needs: the
   * browser delivers relative `movementX/movementY`, the router turns
   * them into yaw/pitch, and gameplay stays the only camera author.
   *
   * The Pointer Lock API requires a user gesture, so call this from a
   * click or key handler, never at boot.
   *
   * @returns {Promise<boolean>} whether the lock was granted
   */
  async requestPointerLock() {
    const element = this.container;
    if (!element?.requestPointerLock) return false;
    try {
      const result = element.requestPointerLock({
        unadjustedMovement: true,
      });
      if (result && typeof result.then === 'function') await result;
      return true;
    } catch {
      // Older browsers reject the options object; retry bare.
      try {
        element.requestPointerLock();
        return true;
      } catch {
        return false;
      }
    }
  }

  /** Release the mouse captured by `requestPointerLock()`. */
  exitPointerLock() {
    if (document.pointerLockElement) document.exitPointerLock?.();
    return this;
  }

  /** @returns {boolean} whether this host's container owns the mouse. */
  isPointerLocked() {
    return document.pointerLockElement === this.container;
  }

  /**
   * Resize the orthographic view without rebuilding the camera.
   *
   * A 2D game zooms out as players separate, so this has to be cheap
   * enough to call every frame.
   *
   * @param {number} frustumHeight world-space metres visible vertically
   */
  setFrustumHeight(frustumHeight) {
    const height = Math.max(0.01, Number(frustumHeight) || 0);
    if (height === this.options.frustumHeight) return this;
    this.options.frustumHeight = height;
    if (this.camera?.isOrthographicCamera) this.#applyViewport();
    return this;
  }

  detachControls() {
    if (this.controls && typeof this.controls.dispose === 'function') {
      this.controls.dispose();
    }
    this.controls = null;
    return this;
  }

  /**
   * Configure background, environment map, and tone mapping.
   *
   * Pass `preset` to generate image-based lighting procedurally; pass
   * `environmentTexture` to supply an imported `.hdr` instead. A game
   * that does neither gets no reflections, and its PBR materials will
   * look flat however many lights it adds.
   *
   * @param {{background?: number | string,
   *          preset?: 'room' | 'sky' | 'none',
   *          environmentTexture?: THREE.Texture,
   *          environmentIntensity?: number,
   *          backgroundIntensity?: number,
   *          showSky?: boolean,
   *          sunPosition?: {x: number, y: number, z: number},
   *          turbidity?: number, rayleigh?: number,
   *          toneMapping?: keyof typeof TONE_MAPPINGS,
   *          toneMappingExposure?: number}} options
   */
  setEnvironment(options = {}) {
    if (!this.scene) throw new Error('init() must run before setEnvironment()');
    if (options.preset !== undefined) {
      this.#applyEnvironmentPreset(options);
    }
    if (options.background !== undefined) {
      this.scene.background = new THREE.Color(options.background);
    }
    if (options.environmentTexture) {
      options.environmentTexture.mapping =
        THREE.EquirectangularReflectionMapping;
      this.#releaseGeneratedEnvironment();
      this.scene.environment = options.environmentTexture;
    }
    if (options.environmentIntensity !== undefined) {
      this.scene.environmentIntensity = Number(options.environmentIntensity);
    }
    if (options.backgroundIntensity !== undefined) {
      this.scene.backgroundIntensity = Number(options.backgroundIntensity);
    }
    if (options.toneMapping && TONE_MAPPINGS[options.toneMapping]) {
      this.renderer.toneMapping = TONE_MAPPINGS[options.toneMapping];
    }
    if (options.toneMappingExposure !== undefined) {
      this.renderer.toneMappingExposure = Number(
        options.toneMappingExposure,
      );
    }
    return this;
  }

  /**
   * Build the environment map for a preset and install it.
   *
   * `PMREMGenerator` is used once at boot and then disposed: it holds
   * render targets and shader programs that are worthless afterwards.
   * The resulting texture is owned by this host so `dispose()` can free
   * it — nothing else in the scene graph references it.
   */
  #applyEnvironmentPreset(options) {
    const preset = String(options.preset ?? 'none').toLowerCase();
    if (preset === A3GameEnvironmentPreset.NONE) {
      this.#releaseGeneratedEnvironment();
      this.scene.environment = null;
      return;
    }
    if (!this.renderer) {
      throw new Error('init() must run before an environment preset is set');
    }

    const generator = new THREE.PMREMGenerator(this.renderer);
    let source = null;
    let sky = null;
    try {
      if (preset === A3GameEnvironmentPreset.SKY) {
        sky = new Sky();
        sky.scale.setScalar(this.options.far * 0.9);
        const sun = options.sunPosition ?? { x: 0.4, y: 0.22, z: -1 };
        const direction = new THREE.Vector3(sun.x, sun.y, sun.z).normalize();
        sky.material.uniforms.sunPosition.value.copy(direction);
        sky.material.uniforms.turbidity.value = Number(options.turbidity ?? 6);
        sky.material.uniforms.rayleigh.value = Number(options.rayleigh ?? 2);
        sky.material.uniforms.mieCoefficient.value = 0.005;
        sky.material.uniforms.mieDirectionalG.value = 0.8;
        source = new THREE.Scene();
        source.add(sky);
      } else if (preset === A3GameEnvironmentPreset.ROOM) {
        source = new RoomEnvironment();
      } else {
        throw new Error(
          `Unknown environment preset ${String(options.preset)}; expected ` +
            'room, sky, or none',
        );
      }
      const texture = generator.fromScene(source, 0.04).texture;
      this.#releaseGeneratedEnvironment();
      this.generatedEnvironment = texture;
      this.scene.environment = texture;
      if (preset === A3GameEnvironmentPreset.SKY && options.showSky !== false) {
        // The sky is also the backdrop, so a second instance is added to
        // the live scene. The one above was consumed by the generator and
        // is disposed with it.
        this.#installSkyDome(options);
      } else if (options.background === undefined) {
        this.scene.background = texture;
      }
    } finally {
      // `RoomEnvironment` is a Scene of meshes; the Sky holds a shader
      // material. Both are throwaway sources for the convolution.
      source?.traverse?.((child) => {
        child.geometry?.dispose?.();
        const materials = Array.isArray(child.material)
          ? child.material
          : child.material
            ? [child.material]
            : [];
        for (const material of materials) material.dispose?.();
      });
      generator.dispose();
    }
  }

  /** Add the visible sky dome under a dedicated root. */
  #installSkyDome(options) {
    const previous = this.namedRoots.get('sky');
    if (previous) {
      disposeObject3D(previous);
      this.namedRoots.delete('sky');
    }
    const sky = new Sky();
    sky.scale.setScalar(this.options.far * 0.9);
    const sun = options.sunPosition ?? { x: 0.4, y: 0.22, z: -1 };
    sky.material.uniforms.sunPosition.value
      .set(sun.x, sun.y, sun.z)
      .normalize();
    sky.material.uniforms.turbidity.value = Number(options.turbidity ?? 6);
    sky.material.uniforms.rayleigh.value = Number(options.rayleigh ?? 2);
    sky.name = 'A3GameSky';
    this.add(sky, 'sky');
    this.scene.background = null;
    return sky;
  }

  #releaseGeneratedEnvironment() {
    if (this.generatedEnvironment) {
      this.generatedEnvironment.dispose();
      this.generatedEnvironment = null;
    }
  }

  /**
   * Configure scene fog.
   *
   * @param {{type?: 'none' | 'Fog' | 'FogExp2', color?: number | string,
   *          near?: number, far?: number, density?: number}} options
   */
  setFog(options = {}) {
    if (!this.scene) throw new Error('init() must run before setFog()');
    const type = options.type ?? 'none';
    if (type === 'none') {
      this.scene.fog = null;
      return this;
    }
    const color = new THREE.Color(options.color ?? 0x101014);
    this.scene.fog =
      type === 'FogExp2'
        ? new THREE.FogExp2(color, options.density ?? 0.001)
        : new THREE.Fog(color, options.near ?? 1, options.far ?? 200);
    return this;
  }

  /**
   * Pick the first object hit under a pointer event.
   *
   * @param {PointerEvent | MouseEvent} event
   * @param {THREE.Object3D[]} [targets] defaults to the whole scene
   * @returns {THREE.Intersection | null}
   */
  raycastFromPointer(event, targets) {
    if (!this.renderer || !this.camera) return null;
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const list = this.raycaster.intersectObjects(
      targets ?? this.scene.children,
      true,
    );
    return list.length > 0 ? list[0] : null;
  }

  /**
   * Cast a ray from an origin along a direction.
   *
   * @param {THREE.Vector3} origin
   * @param {THREE.Vector3} direction normalized
   * @param {{targets?: THREE.Object3D[], far?: number, near?: number}} [options]
   * @returns {THREE.Intersection[]}
   */
  raycast(origin, direction, options = {}) {
    this.raycaster.set(origin, direction.clone().normalize());
    this.raycaster.near = options.near ?? 0;
    this.raycaster.far = options.far ?? Infinity;
    return this.raycaster.intersectObjects(
      options.targets ?? this.scene.children,
      true,
    );
  }

  /** @returns {string} a PNG data URL of the current frame. */
  captureFrame() {
    this.renderer?.render(this.scene, this.camera);
    return this.renderer?.domElement.toDataURL('image/png') ?? '';
  }

  /** @returns {object} render statistics for observation and evidence. */
  getStats() {
    const info = this.renderer?.info;
    return {
      frameCount: this.frameCount,
      elapsedSeconds: Number(this.elapsedSeconds.toFixed(3)),
      drawCalls: info?.render?.calls ?? 0,
      triangles: info?.render?.triangles ?? 0,
      geometries: info?.memory?.geometries ?? 0,
      textures: info?.memory?.textures ?? 0,
      programs: info?.programs?.length ?? 0,
      pixelRatio: this.renderer?.getPixelRatio() ?? 0,
      size: this.#size(),
    };
  }

  /** Release renderer, scene, and listener resources. */
  dispose() {
    this.stop();
    this.detachControls();
    this.tickListeners.clear();
    this.resizeListeners.clear();
    if (this.onWindowResize) {
      window.removeEventListener('resize', this.onWindowResize);
      this.onWindowResize = null;
    }
    this.resizeObserver?.disconnect();
    this.resizeObserver = null;
    this.#releaseGeneratedEnvironment();
    if (this.scene) disposeObject3D(this.scene);
    this.scene = null;
    this.namedRoots.clear();
    if (this.renderer) {
      this.renderer.dispose();
      this.renderer.domElement.remove();
      this.renderer = null;
    }
    this.camera = null;
  }

  #emitTick(delta) {
    for (const listener of this.tickListeners) {
      listener(delta, this.elapsedSeconds);
    }
  }

  #size() {
    const width = this.container?.clientWidth || window.innerWidth || 1;
    const height = this.container?.clientHeight || window.innerHeight || 1;
    return { width, height, clientWidth: width, clientHeight: height };
  }

  #createCamera(type, aspect) {
    if (type === 'orthographic') {
      const halfHeight = this.options.frustumHeight / 2;
      const halfWidth = halfHeight * aspect;
      return new THREE.OrthographicCamera(
        -halfWidth,
        halfWidth,
        halfHeight,
        -halfHeight,
        this.options.near,
        this.options.far,
      );
    }
    return new THREE.PerspectiveCamera(
      this.options.fov,
      aspect,
      this.options.near,
      this.options.far,
    );
  }

  #swapCamera(type) {
    if (!this.scene) {
      throw new Error('init() must run before switching cameras');
    }
    const { width, height } = this.#size();
    const previous = this.camera;
    const camera = this.#createCamera(type, width / Math.max(1, height));
    camera.name = previous?.name ?? 'A3GameCamera';
    if (previous) {
      camera.position.copy(previous.position);
      camera.quaternion.copy(previous.quaternion);
      const parent = previous.parent;
      previous.removeFromParent?.();
      if (parent) parent.add(camera);
    }
    this.camera = camera;
    if (this.controls?.object) this.controls.object = camera;
    this.#applyViewport();
    return camera;
  }

  #applyViewport() {
    const { width, height } = this.#size();
    if (!this.camera || !this.renderer) return { width, height };
    const aspect = width / Math.max(1, height);
    if (this.camera.isOrthographicCamera) {
      const halfHeight = this.options.frustumHeight / 2;
      const halfWidth = halfHeight * aspect;
      this.camera.left = -halfWidth;
      this.camera.right = halfWidth;
      this.camera.top = halfHeight;
      this.camera.bottom = -halfHeight;
    } else {
      this.camera.aspect = aspect;
    }
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
    return { width, height };
  }

  #observeResize() {
    const apply = () => {
      const size = this.#applyViewport();
      for (const listener of this.resizeListeners) {
        listener(size);
      }
    };
    this.onWindowResize = apply;
    window.addEventListener('resize', apply);
    if (typeof ResizeObserver === 'function') {
      this.resizeObserver = new ResizeObserver(apply);
      this.resizeObserver.observe(this.container);
    }
    apply();
  }
}

/**
 * Recursively dispose geometries, materials, and textures.
 *
 * three.js never frees GPU memory automatically; generated gameplay must
 * call this when removing content.
 *
 * @param {THREE.Object3D | null} root
 */
export function disposeObject3D(root) {
  if (!root) return;
  const textureKeys = [
    'map',
    'normalMap',
    'roughnessMap',
    'metalnessMap',
    'aoMap',
    'emissiveMap',
    'alphaMap',
    'displacementMap',
    'envMap',
    'lightMap',
    'clearcoatMap',
    'sheenColorMap',
  ];
  root.traverse((child) => {
    if (child.geometry) child.geometry.dispose();
    const materials = Array.isArray(child.material)
      ? child.material
      : child.material
        ? [child.material]
        : [];
    for (const material of materials) {
      for (const key of textureKeys) {
        material[key]?.dispose?.();
      }
      material.dispose?.();
    }
  });
  root.parent?.remove(root);
  root.clear?.();
}
