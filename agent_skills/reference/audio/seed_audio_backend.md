# Seed Audio API backends

Seed Audio 1.0 can fill either existing AudioGen slot without changing task
JSON: `audio_type=dialogue` uses it for character speech, while
`audio_type=sound_effect` uses it for one-shots, foley, and ambience. The API is
synchronous and produces an offline WAV asset; it is not runtime game audio.
The China service sends `POST` requests to
`https://openspeech.bytedance.com/api/v3/tts/create` by default.

Set credentials without committing them:

```bash
export SEED_AUDIO_API_KEY=<your Volcengine Seed Audio API key>
export AAAGF_API_CACHE=test_data/outputs/_api_cache
```

The cloud backends use the shared HTTP dependency:

```bash
bash scripts/installing/cloud_api_install.sh
```

Generate one dialogue asset:

```bash
python pipeline/assets_gen/gen_audio/run.py \
  --dialogue-backend seed_audio \
  --audio-type dialogue \
  --text "发现目标" \
  --task-id spotted_target
```

Generate one sound-effect asset:

```bash
python pipeline/assets_gen/gen_audio/run.py \
  --sound-effect-backend seed_audio \
  --audio-type sound_effect \
  --prompt "a single close futuristic rifle shot, dry, no music" \
  --duration-sec 2 \
  --task-id rifle_shot
```

Use both API routes for a JSONL batch:

```bash
python pipeline/assets_gen/gen_audio/run.py \
  --dialogue-backend seed_audio \
  --sound-effect-backend seed_audio \
  --game gameA_cyberpunk_shooter
```

Optional configuration:

- `SEED_AUDIO_MODEL` (default `seed-audio-1.0`)
- `SEED_AUDIO_API_BASE` (default `https://openspeech.bytedance.com`)
- `SEED_AUDIO_SPEAKER_ID` (Seed Audio speaker resource id for dialogue)
- `AAAGF_DIALOGUE_BACKEND` and `AAAGF_SOUND_EFFECT_BACKEND`

The task's Qwen `speaker_id` values such as `Vivian` are deliberately not sent
to the Seed Audio API. Configure `SEED_AUDIO_SPEAKER_ID` when a registered
Seed Audio speaker is required. If `reference_audio_path` is present, the in-memory
reference audio is base64-encoded and takes precedence over that speaker id.

Run the offline API contract test and the no-network harness check:

```bash
python test/test_api_audio.py
python test/harness/smoke.py --kind audio --backend seed_audio
```

The API test replaces the HTTP client with a fake; it consumes no credits.
