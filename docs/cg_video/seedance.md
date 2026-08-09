# Seedance backend

`SeedanceModel` wraps the Volcengine Ark asynchronous video-generation API. It
submits a task, polls until completion, downloads the MP4, and exposes the whole
operation as one synchronous `infer()` call.

Official API reference:
[Volcengine video generation API](https://www.volcengine.com/docs/82379/1520757).

## Installation and authentication

Install the shared cloud-API dependency:

```bash
bash scripts/installing/cloud_api_install.sh
```

Create an Ark API key and expose it through the environment:

```bash
export ARK_API_KEY="your-api-key"
```

The key is resolved lazily on the first non-cached request. Constructing or
importing `SeedanceModel` does not require credentials or network access. An Ark
endpoint identifier such as `ark-e...` is not a substitute for the API key used
in the `Authorization` header.

Optional environment variables:

```bash
export ARK_API_BASE="https://ark.cn-beijing.volces.com/api/v3"
export SEEDANCE_MODEL="doubao-seedance-2-0-260128"
export AAAGF_API_CACHE="test_data/outputs/_api_cache"
```

Never commit API keys or place them in JSONL, metadata, cache keys, or command
examples checked into the repository.

## Constructor

```python
from models.gen_cg_video import SeedanceModel

model = SeedanceModel(
    model_path="doubao-seedance-2-0-260128",
    resolution="720p",
    ratio="16:9",
    generate_audio=False,
    watermark=False,
    timeout=1800,
    poll_interval=3,
    max_retries=3,
    cache_dir="test_data/outputs/_api_cache",
)
```

| Argument | Default | Purpose |
|---|---|---|
| `model_path` | `doubao-seedance-2-0-260128` | Ark model version identifier |
| `device` | `cuda` | Interface compatibility only; ignored by the cloud backend |
| `timeout` | `1800` | Maximum seconds to wait for one provider task |
| `poll_interval` | `3.0` | Seconds between task-status requests |
| `max_retries` | `3` | Extra attempts for retryable HTTP failures |
| `cache_dir` | `None` | Content-addressed response cache; disabled when omitted |
| `output_format` | `mp4` | Only MP4 is accepted |
| `resolution` | `720p` | Requested output resolution |
| `ratio` | `adaptive` | Requested aspect ratio; the CLI defaults to `16:9` |
| `generate_audio` | `True` | Ask supported model versions to generate audio |
| `watermark` | `False` | Provider watermark control |
| `api_base` | Ark Beijing API | Override the API root |
| `http_timeout` | `60` | Per-request socket timeout, not generation timeout |
| `verbose` | `False` | Print polling progress when enabled |

`model_path` is a provider version identifier, not a local checkpoint. `device`
is retained so the pipeline can construct cloud and local backends through one
model slot.

## Direct Python usage

### Text to video

```python
from models.gen_cg_video import (
    SeedanceModel,
    VideoGenerationInput,
    VideoGenerationMode,
)

model = SeedanceModel(
    generate_audio=False,
    cache_dir="test_data/outputs/_api_cache",
)

request = VideoGenerationInput(
    mode=VideoGenerationMode.TEXT_TO_VIDEO,
    prompt="A paper dragon flies over misty mountains, cinematic lighting.",
    duration_sec=5,
    seed=42,
)

video_bytes = model.infer(request)
path = model.infer_and_save(request, "outputs/paper_dragon.mp4")
model.unload()
```

Calling both methods with the same cache enabled does not submit the same paid
request twice: `infer_and_save()` reuses the response cached by `infer()`.

### First frame to video

```python
from PIL import Image

first = Image.open("/absolute/path/first.png").convert("RGB")
request = VideoGenerationInput(
    mode=VideoGenerationMode.FIRST_FRAME_TO_VIDEO,
    prompt="The character slowly turns toward the camera.",
    duration_sec=5,
    seed=42,
    first_frame=first,
)
model.infer_and_save(request, "outputs/first_frame.mp4")
```

### First and last frames to video

```python
first = Image.open("/absolute/path/first.png").convert("RGB")
last = Image.open("/absolute/path/last.png").convert("RGB")
request = VideoGenerationInput(
    mode=VideoGenerationMode.FIRST_LAST_FRAME_TO_VIDEO,
    prompt="Move continuously from the first composition to the last.",
    duration_sec=5,
    seed=42,
    first_frame=first,
    last_frame=last,
)
model.infer_and_save(request, "outputs/first_last.mp4")
```

### Reference images to video

```python
character = Image.open("/absolute/path/character.png").convert("RGB")
environment = Image.open("/absolute/path/environment.png").convert("RGB")
request = VideoGenerationInput(
    mode=VideoGenerationMode.REFERENCE_TO_VIDEO,
    prompt=(
        "Use image 1 as the character design and image 2 as the environment. "
        "The character waves toward the camera."
    ),
    duration_sec=5,
    seed=42,
    reference_images=(character, environment),
)
model.infer_and_save(request, "outputs/reference.mp4")
```

Reference-image order is preserved. Describe the intended role of each image in
the prompt when the composition depends on a specific mapping.

## Image transport

Direct model calls accept PIL images, not local path strings. The wrapper uses
`models.common.cloud_api` to encode each normalized image as a PNG Base64 Data
URI in the provider request. Operator and pipeline callers should continue to
pass local path fields; the operator performs the path-to-PIL boundary exactly
once.

## Pipeline flags

Seedance-specific runner flags are model construction parameters and do not
change `VideoGenerationInput`:

```bash
python pipeline/assets_gen/gen_cg_video/run.py \
  --backend seedance \
  --ckpt doubao-seedance-2-0-260128 \
  --resolution 720p \
  --ratio 16:9 \
  --no-generate-audio \
  --no-watermark \
  --timeout 1800 \
  --poll-interval 3 \
  --max-retries 3 \
  --cache-dir test_data/outputs/_api_cache \
  --prompt "A cinematic establishing shot of a floating city."
```

The checkpoint precedence is:

```text
--ckpt > SEEDANCE_MODEL > doubao-seedance-2-0-260128
```

## Cache, retries and errors

- Cache keys include model version, mode, prompt, image hashes, generation
  parameters and output format. API keys and raw image bytes are excluded.
- A cache hit returns without creating an HTTP client or sending network traffic.
- HTTP 429, 5xx and transport timeouts use exponential-backoff retries.
- Bad parameters, authentication failures and insufficient balance are terminal
  and are not retried.
- Generation timeout errors retain the provider task id so a task that finishes
  server-side can be recovered manually.
- `last_call_info` records provider, model, mode, task id, elapsed time, output
  bytes, cache status and provider usage when available. The operator copies it
  into `meta.json`.

Because provider calls may be billed, use a persistent `cache_dir` for manual
testing and batch runs.

## Testing

Free structural validation:

```bash
python test/harness/smoke.py --kind cg_video
```

The real integration test is disabled by default and must be explicitly opted
in. Start with text-to-video only:

```bash
export ARK_API_KEY="your-api-key"
export AAAGF_RUN_SEEDANCE_LIVE=1
export SEEDANCE_LIVE_MODES="text_to_video"
export SEEDANCE_RESOLUTION="480p"
export SEEDANCE_GENERATE_AUDIO=0
python -m unittest test.test_api_cg_video -v
```

To test image modes, additionally set absolute input paths as described in
`test/test_api_cg_video.py`. Identical requests reuse the response cache unless
`AAAGF_SEEDANCE_DISABLE_CACHE=1` is deliberately set.

Do not enable the paid test in CI or run every mode merely to validate local
code changes. Use the harness first, then make one intentional provider call.
