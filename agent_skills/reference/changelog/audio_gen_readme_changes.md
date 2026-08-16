# Deferred AudioGen README changes

This temporary note records the documentation updates that should be applied
after the parallel pull requests have landed. The AudioGen pull request keeps
the shared README files unchanged to avoid unnecessary merge conflicts.

| Target README | Change to apply during the final documentation pass |
|---|---|
| `README.md` | Add `audio` to the generated-asset directory tree; document first-run Woosh checkpoint download and the `WOOSH_DFLOW_CKPT`, `WOOSH_AE_CKPT`, `WOOSH_TEXT_CONDITIONER_CKPT`, and `WOOSH_RELEASE_BASE_URL` overrides; list `gen_audio` as an implemented end-to-end asset chain. |
| `models/README.md` | List Qwen3-TTS and Sony Woosh-DFlow as the dialogue and sound-effect backends under `models/gen_audio/`. |
| `operators/README.md` | Describe the `gen_audio` dialogue/SFX routing and defer the benchmark-metric list until AudioGen evaluation metrics are implemented. |
| `pipeline/README.md` | Clarify that asset `eval.py` evaluates artifacts from the selected `run_id` rather than regenerating them. |
| `test_data/outputs/README.md` | Add `assets/audio/<task_id>/audio.wav` and `meta.json` to the output tree; update the documented asset-kind count from six to seven. |
| `test_data/test_samples/README.md` | Mark `audio/` and `audio_gen_collect.jsonl` as populated test inputs rather than documentation-only templates. |

## AudioGen commands to document

```bash
# Generate only sound effects. Missing Woosh checkpoints are downloaded first.
python pipeline/assets_gen/gen_audio/run.py --only-audio-type sound_effect

# Use preinstalled checkpoints.
WOOSH_DFLOW_CKPT=/path/to/Woosh-DFlow \
WOOSH_AE_CKPT=/path/to/Woosh-AE \
WOOSH_TEXT_CONDITIONER_CKPT=/path/to/TextConditionerA \
python test/test_audio_gen.py

# Disable automatic downloads for an offline or pre-provisioned environment.
python pipeline/assets_gen/gen_audio/run.py \
  --only-audio-type sound_effect \
  --no-auto-download
```
