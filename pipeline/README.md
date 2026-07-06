# pipeline/

Full-chain runners, organized by function. Each task directory contains two
entry points:

- **`run.py`** — generation only (demo / production)
- **`eval.py`** — evaluation only (benchmark scoring)

## Structure

```
pipeline/
├── assets_gen/                              # Asset generation tasks
│   ├── gen_3d_object/{run.py, eval.py}      #   image / text → 3D object
│   ├── gen_3d_scene/{run.py, eval.py}       #   text → 3D scene
│   ├── gen_motion/{run.py, eval.py}         #   text + skeleton → animation
│   ├── gen_cg_video/{run.py, eval.py}       #   text / frame → CG video
│   └── retarget/{run.py, eval.py}           #   motion + skeleton → retargeted motion
│
├── mechanic/{run.py, eval.py}               # spec + engine template → code + trace
├── ui/{run.py, eval.py}                     # UI spec → UI code + screenshots
└── full_pipeline/{run.py, eval.py}          # design doc → playable vertical slice
```

## Responsibilities

### `run.py`
1. Load required models (from `models/`)
2. Instantiate operator (from `operators/`)
3. Take a single input → produce a single output artifact
4. No scoring, no metric computation

### `eval.py`
1. Iterate the test set from `test_data/test_samples/*_tasks.jsonl`
   (or the cross-game `*_collect.jsonl`)
2. Reuse `run.py`'s generation function (`from .run import generate`)
3. Invoke `operators/<task>/metrics/` on each output
4. Write per-task scores + aggregate summary

## Convention

```python
# pipeline/assets_gen/gen_3d_object/run.py
def generate(prompt: str, ref_image=None, ...) -> dict:
    ...

# pipeline/assets_gen/gen_3d_object/eval.py
from .run import generate
from operators.gen_3d_object.metrics import evaluate
```
