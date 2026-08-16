# Audio generation and QA Skill

Use this Skill when a game plan requires **dialogue, voice lines, sound effects,
foley, ambience, or other offline WAV assets**. This is asset generation, not a
runtime audio-playback contract; use the selected engine context after an asset
has passed review.

## Scope and output

The audio chain is:

```text
Task dict / JSONL → GenAudioOperator → selected audio model → WAV + meta.json
```

- Model implementations: `models/gen_audio/`
- Task and artifact handling: `operators/gen_audio/`
- Runner and batch execution: `pipeline/assets_gen/gen_audio/`
- Free smoke checks: `test/harness/`
- Generated results: `test_data/outputs/<game_id>/<run_id>/assets/audio/<task_id>/`

Use `pipeline/common/paths.py` for output locations. Do not revive the obsolete
flat `test_data/outputs/mechanic/` or `test_data/outputs/ui/` directories.

## Plan before generating

For every audio task, record:

1. the game moment and source (player, enemy, world, UI, cinematic);
2. asset type: `dialogue` or `sound_effect`;
3. duration, language/voice requirements, emotional delivery, distance,
   perspective, and any diegetic context;
4. style references, loudness/mixing intent, looping need, and acceptance
   criteria;
5. backend choice, expected cost, and licence/provenance.

Do not ask a generator to imitate a named living performer or use reference
recordings without the required rights. Never commit audio API keys or private
reference recordings.

## Backend selection

| Need | Preferred route | Notes |
|---|---|---|
| Character dialogue / TTS | Qwen3-TTS or Seed Audio | Choose a voice that is licensed and suitable for the game; record speaker configuration. |
| Sound effects / foley / ambience | Sony Woosh-DFlow or Seed Audio | Generate a focused one-shot first; layer and mix only after QA. |
| Fast cloud dialogue or SFX | Seed Audio 1.0 | One API supports both slots and outputs an offline WAV asset. |

Use a local/open backend when offline execution, privacy, reproducibility, or
budget requires it. Use a cloud backend when it is permitted and gives the
planned quality. Do not silently substitute one backend for another: report the
fallback and its implications.

## Environment setup

### Shared cloud API dependency

```bash
bash scripts/asset_env_setup/audio/cloud_api_install.sh
```

### Local Woosh-DFlow sound-effect checkpoints

The first local Woosh-DFlow run can download checkpoints automatically. To use
preinstalled checkpoints, configure:

```bash
export WOOSH_DFLOW_CKPT=/path/to/Woosh-DFlow
export WOOSH_AE_CKPT=/path/to/Woosh-AE
export WOOSH_TEXT_CONDITIONER_CKPT=/path/to/TextConditionerA
# Optional release download location override:
export WOOSH_RELEASE_BASE_URL=https://...
```

For offline or pre-provisioned machines, disable automatic downloads:

```bash
python pipeline/assets_gen/gen_audio/run.py \
  --only-audio-type sound_effect \
  --no-auto-download
```

Keep large checkpoints and installer packages under `third_party/` or an
externally configured model cache; do not commit them to source control.

## Seed Audio 1.0 cloud backend

Seed Audio can occupy either existing slot without changing the task JSON:

- `audio_type=dialogue`: character speech;
- `audio_type=sound_effect`: one-shots, foley, and ambience.

It is synchronous at the pipeline boundary and creates an offline WAV asset.
The default China endpoint is
`https://openspeech.bytedance.com/api/v3/tts/create`.

### Credentials and optional configuration

```bash
export SEED_AUDIO_API_KEY=<your-volcengine-seed-audio-api-key>
export AAAGF_API_CACHE=test_data/outputs/_api_cache

# Optional:
export SEED_AUDIO_MODEL=seed-audio-1.0
export SEED_AUDIO_API_BASE=https://openspeech.bytedance.com
export SEED_AUDIO_SPEAKER_ID=<registered-seed-audio-speaker-resource-id>
export AAAGF_DIALOGUE_BACKEND=seed_audio
export AAAGF_SOUND_EFFECT_BACKEND=seed_audio
```

The task's Qwen-style `speaker_id` values (for example `Vivian`) are not sent
to Seed Audio. Use `SEED_AUDIO_SPEAKER_ID` for a registered Seed Audio speaker.
When `reference_audio_path` is supplied, its in-memory audio takes precedence
over that speaker id. Only use a reference recording when its rights permit the
intended use.

### Seed Audio commands

Generate dialogue:

```bash
python pipeline/assets_gen/gen_audio/run.py \
  --dialogue-backend seed_audio \
  --audio-type dialogue \
  --text "发现目标" \
  --task-id spotted_target
```

Generate a sound effect:

```bash
python pipeline/assets_gen/gen_audio/run.py \
  --sound-effect-backend seed_audio \
  --audio-type sound_effect \
  --prompt "a single close futuristic rifle shot, dry, no music" \
  --duration-sec 2 \
  --task-id rifle_shot
```

Generate both types from a JSONL batch:

```bash
python pipeline/assets_gen/gen_audio/run.py \
  --dialogue-backend seed_audio \
  --sound-effect-backend seed_audio \
  --game gameA_cyberpunk_shooter
```

## QA and validation

1. Run free checks before any paid cloud call:

   ```bash
   python test/harness/smoke.py --kind audio --backend seed_audio
   python test/test_api_audio.py
   ```

   The API contract test uses a fake HTTP client and consumes no credits.

2. Inspect the WAV before integration: no unintended music in a one-shot, no
   clipping, abrupt cut, dominant background noise, or unsuitable duration.
3. Integrate the asset in the target game and exercise the related action or
   scene. Check trigger timing, attenuation, looping, dialogue intelligibility,
   spatial placement, mix balance, and consistency with the requested style.
4. Capture a representative low-resolution gameplay video where audio capture
   is available; report any platform limitation if it is not.
5. Preserve provider/model, prompt or text, source/reference rights, backend
   configuration, cache status, and review result in the task metadata.

Do not claim success merely because a WAV exists. The asset is accepted only
when its in-game behavior and style meet the planned acceptance criteria.
