# CG video generation

AAAGameForge exposes CG video generation through the same three-layer asset
chain used by 3D generation:

```mermaid
flowchart LR
    A["Task dict / JSONL"] --> B["GenCGVideoOperator"]
    B --> C["VideoGenerationInput"]
    C --> D["Video model"]
    D --> E["MP4 bytes"]
    E --> F["video.mp4 + meta.json"]
```

The backend slot is model-agnostic so local and cloud video models can be added
without changing task parsing, artifact placement, or batch execution.

## Code layout

| Layer | Location | Responsibility |
|---|---|---|
| Model | `models/gen_cg_video/` | Model-native inference, transport encoding, lifecycle |
| Operator | `operators/gen_cg_video/` | Task fields, local image loading, artifact path and metadata |
| Pipeline | `pipeline/assets_gen/gen_cg_video/` | Backend selection, CLI, JSONL batches and summaries |
| Harness | `test/harness/` | CPU-only, network-free chain validation |

Dependencies point downward. Models never import operators or pipelines, and
the operator receives an already constructed model. The only wiring point is
`run.py::make_operator()`.

## Shared model contract

All backends in the CG-video slot implement:

```python
infer(request: VideoGenerationInput) -> bytes
infer_and_save(request: VideoGenerationInput, output_path: str) -> str
```

`VideoGenerationInput` contains provider-neutral task data:

```python
VideoGenerationInput(
    mode=VideoGenerationMode.TEXT_TO_VIDEO,
    prompt="A knight walks through a rainy neon city.",
    duration_sec=5,
    seed=42,
    first_frame=None,
    last_frame=None,
    reference_images=(),
)
```

The four currently defined modes are shared task capabilities. A backend only
implements the subset its underlying model actually supports:

| Mode | Required images | Meaning |
|---|---|---|
| `text_to_video` | none | Generate from text only |
| `first_frame_to_video` | `first_frame` | Animate one starting frame |
| `first_last_frame_to_video` | `first_frame`, `last_frame` | Generate a transition between two keyframes |
| `reference_to_video` | one or more `reference_images` | Use ordered images as visual references |

The input type validates the exact image combination for each mode. Image order
is preserved for reference generation.

| Backend | `text_to_video` | `first_frame_to_video` | `first_last_frame_to_video` | `reference_to_video` |
|---|---:|---:|---:|---:|
| Seedance 2.0 | yes | yes | yes | yes |
| MiniMax H3 (`local`) | yes | yes | yes | yes |
| MiniMax Hailuo 2.3 (`api`) | yes | yes | no | no |

Selecting `--backend` chooses the model implementation; `mode` is then sent to
that model. An unsupported pair fails explicitly and is never silently rerouted
to a different provider.

## Input boundary

Task dictionaries and JSONL files use local paths because they must be
serializable. The operator resolves those paths from any working directory,
opens them as `PIL.Image.Image`, and builds `VideoGenerationInput`. A model never
receives a local path.

| Task field | Model field |
|---|---|
| `first_frame_path` | `first_frame: PIL.Image.Image` |
| `last_frame_path` | `last_frame: PIL.Image.Image` |
| `reference_image_paths` | `reference_images: tuple[PIL.Image.Image, ...]` |

Python callers that already hold PIL images may use `first_frame`, `last_frame`,
or `reference_images` directly. Do not provide both an object field and its path
field in the same task.

## Operator usage

```python
from models.gen_cg_video import SeedanceModel
from operators.gen_cg_video import GenCGVideoOperator

model = SeedanceModel(cache_dir="test_data/outputs/_api_cache")
operator = GenCGVideoOperator(model=model, run_id="demo")

result = operator.run({
    "game_id": "gameA_cyberpunk_shooter",
    "task_id": "opening_shot",
    "mode": "first_last_frame_to_video",
    "prompt": "The hero turns toward the camera while rain falls.",
    "duration_sec": 5,
    "seed": 42,
    "first_frame_path": "assets/opening.png",
    "last_frame_path": "assets/ending.png",
})
print(result["video_path"])
```

Without `output_dir`, artifacts use the standard per-game layout:

```text
test_data/outputs/<game_id>/<run_id>/assets/cg_video/<task_id>/
├── video.mp4
└── meta.json
```

Passing `output_dir="..."` enables the legacy flat layout and writes
`<output_dir>/<task_id>.mp4` without `meta.json`.

## Pipeline CLI

Text-to-video single-task mode:

```bash
python pipeline/assets_gen/gen_cg_video/run.py \
  --backend seedance \
  --prompt "A paper dragon flies over misty mountains." \
  --mode text_to_video \
  --duration-sec 5 \
  --task-id paper_dragon \
  --game gameA_cyberpunk_shooter \
  --run-id auto \
  --cache-dir test_data/outputs/_api_cache
```

Frame-conditioned modes add the corresponding flags:

```bash
# First frame
python pipeline/assets_gen/gen_cg_video/run.py \
  --prompt "The character walks forward." \
  --mode first_frame_to_video \
  --first-frame /absolute/path/first.png

# First and last frames
python pipeline/assets_gen/gen_cg_video/run.py \
  --prompt "Transition naturally between the two frames." \
  --mode first_last_frame_to_video \
  --first-frame /absolute/path/first.png \
  --last-frame /absolute/path/last.png

# Ordered reference images; repeat the flag
python pipeline/assets_gen/gen_cg_video/run.py \
  --prompt "Keep the character and environment consistent." \
  --mode reference_to_video \
  --reference-image /absolute/path/character.png \
  --reference-image /absolute/path/environment.png
```

Without `--prompt`, the runner enters batch mode:

```bash
python pipeline/assets_gen/gen_cg_video/run.py \
  --tasks /absolute/path/cg_tasks.jsonl \
  --run-id auto
```

Example JSONL line:

```json
{"game_id":"gameA_cyberpunk_shooter","task_id":"shot_001","mode":"first_frame_to_video","prompt":"The camera slowly moves closer.","duration_sec":5,"seed":42,"first_frame_path":"gameA_cyberpunk_shooter/cg_video/shot_001.png"}
```

Relative image paths are resolved through `pipeline.common.paths`, not against
the shell's current directory.

## Shared and backend-specific parameters

Task-level parameters belong to `VideoGenerationInput`: mode, prompt, duration,
seed and images. Provider/runtime controls such as resolution, aspect ratio,
audio generation, watermarking, timeout and cache location belong to the model
constructor and pipeline flags. They are deliberately not added to the shared
input type.

This separation lets a future local backend implement the same task modes while
retaining its native controls, such as frame count or sampling settings.

## Validation

The free harness exercises construction, both output layouts, artifact writing,
metadata and summaries without loading a model or contacting a provider:

```bash
python test/harness/smoke.py --kind cg_video
```

## Backends

- [Seedance](seedance.md) — Volcengine Ark cloud API.
- [MiniMax H3 / Hailuo 2.3](minimax_h3.md) — one backend for the cloud API and local ComfyUI INT8 checkpoints.
