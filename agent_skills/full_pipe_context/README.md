For asset generation and user testing, import the matching
`pipeline.assets_gen.<task>.run` module and use its public lifecycle:
`load_*()` → `make_operator()` → `generate(inp, operator)`. `generate()` is a
thin single-asset wrapper and does not load models itself, so callers can reuse
loaded models across tasks. `operator.run(inp)` is the lower-level API when
models are already injected. `run.py` batch-drives generation for Benchmark;
`eval.py` only evaluates existing artifacts.

For T-pose assets, use
`pipeline.assets_gen.gen_tpose_image.run.{load_gen_model,load_mask_model,make_operator,generate}`.
Its concrete wrappers are `models.gen_image.qwen_edit_model.QwenEditModel` and
`models.tools.image_matting.{rmbg_model,depth_anything_model}`.
