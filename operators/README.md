# operators/

Task **operators** — one per WorldFlex-GameBenchmark task type.

Each operator directory has a uniform layout:

```
operators/<task>/
├── __init__.py
├── operator.py       # Top-level class, e.g. Gen3DObjectOperator
├── funcs/            # Decoupled steps (one file per logical function)
└── metrics/          # Task-specific evaluation code
```

`metrics/` is co-located with each operator on purpose — the evaluation logic
is tightly coupled to that operator's outputs (e.g., CG needs temporal-consistency
metrics; 3D-object needs Chamfer + PBR checks; retarget needs foot-skate + jerk).

## Operators

| Operator         | Layer | Description                                                | Typical metrics                                |
|------------------|-------|------------------------------------------------------------|------------------------------------------------|
| `process_input`  | pre   | Parse text, preprocess image, extract character            | schema-conformance                             |
| `gen_3d_object`  | A     | Generate a single 3D asset from image / text               | Chamfer, CLIP, tri-count, PBR completeness     |
| `gen_3d_scene`   | A     | Generate a whole 3D scene (terrain + layout + lighting)    | scene-scale, occlusion, coverage, CLIP         |
| `gen_motion`     | A     | Generate skeletal animation                                | FID-motion, foot-skate, jerk, loop continuity  |
| `gen_cg_video`   | A     | Generate CG / cutscene video                               | temporal consistency, optical-flow, CLIP       |
| `gen_audio`      | A     | Generate character dialogue and game sound effects          | intelligibility, prompt alignment, fidelity, loudness |
| `retarget`       | A     | Retarget motion between skeletons                          | foot-skate, hand-drift, source-timing preservation |
| `gen_mechanic`   | B     | Generate mechanic code for UE5 / Unity3D                   | build-ok, trace-replay, rubric-judge           |
| `gen_ui`         | C     | Generate front-end / HUD code                              | resolution robustness, navigability, rubric-judge |
