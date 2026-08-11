/**
 * Node-side inspector for generated meshes destined for three.js.
 *
 * Counterpart of `engine_adapters/ue5/import_generated/import_mesh.py`.
 * Where Unreal needs an in-editor Python importer, the web needs no
 * import step at all: a glTF/GLB file is already the runtime format. What
 * it does need is proof the file will actually load, plus the triangle,
 * material, animation, and bounds figures the pipeline records.
 *
 * This script runs under plain Node with only `three` installed, so it
 * validates with the same loader the game will use at runtime.
 *
 * Usage:
 *   node import_mesh.mjs --source <file.glb> \
 *       --usage {asset,vfx_standalone,vfx_particle} \
 *       [--report report.json] [--draco-decoder <dir>]
 *
 * It writes a JSON report and exits non-zero when the file cannot load.
 */

import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { basename, dirname, extname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const USAGE_TIERS = new Set(['asset', 'vfx_standalone', 'vfx_particle']);

const USAGE_BUDGETS = {
  asset: {
    maxTriangles: 250000,
    maxTextures: 24,
    maxBytes: 40 * 1024 * 1024,
  },
  vfx_standalone: {
    maxTriangles: 60000,
    maxTextures: 12,
    maxBytes: 12 * 1024 * 1024,
  },
  vfx_particle: {
    maxTriangles: 4000,
    maxTextures: 4,
    maxBytes: 2 * 1024 * 1024,
  },
};

function parseArguments(argv) {
  const args = { usage: 'asset' };
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token.startsWith('--')) continue;
    const key = token.slice(2).replace(/-/g, '_');
    const next = argv[index + 1];
    if (next === undefined || next.startsWith('--')) {
      args[key] = true;
      continue;
    }
    args[key] = next;
    index += 1;
  }
  return args;
}

function emit(report) {
  process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
  return report.ok ? 0 : 1;
}

async function loadThree() {
  try {
    return {
      THREE: await import('three'),
      GLTFLoader: (
        await import('three/addons/loaders/GLTFLoader.js')
      ).GLTFLoader,
      DRACOLoader: (
        await import('three/addons/loaders/DRACOLoader.js')
      ).DRACOLoader,
    };
  } catch (error) {
    throw new Error(
      'three is not installed for this Node process; run ' +
        `project.install_dependencies() first (${error.message})`,
    );
  }
}

function summarize(gltf, THREE) {
  let triangles = 0;
  let meshes = 0;
  let skinnedMeshes = 0;
  const materials = new Set();
  const textures = new Set();
  gltf.scene.traverse((child) => {
    if (!child.isMesh) return;
    meshes += 1;
    if (child.isSkinnedMesh) skinnedMeshes += 1;
    const geometry = child.geometry;
    const count = geometry?.index
      ? geometry.index.count
      : (geometry?.attributes?.position?.count ?? 0);
    triangles += Math.floor(count / 3);
    const list = Array.isArray(child.material)
      ? child.material
      : child.material
        ? [child.material]
        : [];
    for (const material of list) {
      materials.add(material.name || material.uuid);
      for (const value of Object.values(material)) {
        if (value?.isTexture) textures.add(value.uuid);
      }
    }
  });
  const box = new THREE.Box3().setFromObject(gltf.scene);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  return {
    meshes,
    skinnedMeshes,
    triangles,
    materialCount: materials.size,
    materials: [...materials],
    textureCount: textures.size,
    animationCount: gltf.animations.length,
    animations: gltf.animations.map((clip) => clip.name),
    bounds: {
      min: box.min.toArray().map((value) => Number(value.toFixed(5))),
      max: box.max.toArray().map((value) => Number(value.toFixed(5))),
      size: size.toArray().map((value) => Number(value.toFixed(5))),
      center: center.toArray().map((value) => Number(value.toFixed(5))),
    },
  };
}

async function main() {
  const args = parseArguments(process.argv.slice(2));
  const operation = 'import_generated.import_mesh';
  const warnings = [];
  const errors = [];

  const sourceArgument = typeof args.source === 'string' ? args.source : '';
  if (!sourceArgument) {
    return emit({
      ok: false,
      operation,
      errors: ['--source is required'],
      warnings,
      payload: {},
    });
  }
  const usage = String(args.usage ?? 'asset');
  if (!USAGE_TIERS.has(usage)) {
    return emit({
      ok: false,
      operation,
      errors: [
        `--usage must be one of: ${[...USAGE_TIERS].join(', ')}`,
      ],
      warnings,
      payload: {},
    });
  }

  const source = resolve(sourceArgument);
  const suffix = extname(source).toLowerCase();
  if (!['.glb', '.gltf'].includes(suffix)) {
    return emit({
      ok: false,
      operation,
      errors: [
        `three.js consumes glTF at runtime; convert ${suffix || 'this file'}` +
          ' to .glb before import',
      ],
      warnings,
      payload: { source, usage },
    });
  }

  let bytes = 0;
  let THREE;
  let summary;
  try {
    const data = await readFile(source);
    bytes = data.byteLength;
    const three = await loadThree();
    THREE = three.THREE;
    const loader = new three.GLTFLoader();
    if (typeof args.draco_decoder === 'string') {
      const draco = new three.DRACOLoader();
      draco.setDecoderPath(
        pathToFileURL(resolve(args.draco_decoder)).href.replace(/\/?$/, '/'),
      );
      loader.setDRACOLoader(draco);
    }
    const gltf = await loader.parseAsync(
      data.buffer.slice(
        data.byteOffset,
        data.byteOffset + data.byteLength,
      ),
      pathToFileURL(`${dirname(source)}/`).href,
    );
    summary = summarize(gltf, THREE);
  } catch (error) {
    return emit({
      ok: false,
      operation,
      errors: [`${error.name}: ${error.message}`],
      warnings,
      payload: { source, usage, bytes },
    });
  }

  const budget = USAGE_BUDGETS[usage];
  if (summary.triangles > budget.maxTriangles) {
    errors.push(
      `Triangle count ${summary.triangles} exceeds the ${usage} budget ` +
        `of ${budget.maxTriangles}`,
    );
  }
  if (summary.textureCount > budget.maxTextures) {
    warnings.push(
      `Texture count ${summary.textureCount} exceeds the ${usage} budget ` +
        `of ${budget.maxTextures}`,
    );
  }
  if (bytes > budget.maxBytes) {
    warnings.push(
      `File size ${bytes} bytes exceeds the ${usage} budget of ` +
        `${budget.maxBytes} bytes`,
    );
  }
  if (summary.meshes === 0) {
    errors.push('glTF contains no mesh; nothing would render');
  }
  if (usage === 'asset' && summary.skinnedMeshes === 0 && args.expect_skin) {
    warnings.push(
      'No skinned mesh was found; imported motion cannot bind to this file',
    );
  }

  const report = {
    ok: errors.length === 0,
    operation,
    errors,
    warnings,
    payload: {
      source,
      asset_name: basename(source, suffix),
      usage,
      bytes,
      budget,
      ...summary,
    },
  };
  if (typeof args.report === 'string') {
    const target = resolve(args.report);
    await mkdir(dirname(target), { recursive: true });
    await writeFile(target, `${JSON.stringify(report, null, 2)}\n`, 'utf8');
    report.payload.report_path = target;
  }
  return emit(report);
}

if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  process.exitCode = await main();
}

export { main, summarize, USAGE_BUDGETS, USAGE_TIERS };
