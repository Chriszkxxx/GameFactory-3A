# A3GameForge game-generation agent guide

Read this file first when you are asked to use A3GameForge to create or improve
a game. It routes you to the minimum task-specific Skills and engine API context.
It is for **game-generation work**: generate assets, gameplay, UI, scenes, and
engine-ready projects. It is not a source-code API reference.

## Project goal

A3GameForge helps a coding agent turn a game requirement into a playable game
slice. It supports image and T-pose preparation, 3D objects, 3D scenes, motion,
audio, CG video, gameplay mechanics, UI, and full-pipeline assembly for UE5,
Blender, Unity, and three.js.

## End-to-end game-generation workflow

Follow this order for every game request. Do not jump directly to code or asset
generation before the game has a plan.

1. **Clarify the brief.** Identify the target engine, game genre, player loop,
   target platform, requested deliverables, visual style, references, budget,
   and acceptance criteria. If the user did not specify an engine or visual
   style, ask for them before planning. If only one choice is missing, state a
   reasonable default and ask the user to confirm it before implementation.
2. **Plan the game.** Write a concise, testable plan: core loop; controls;
   camera; player and enemy/vehicle roles; level flow; UI; asset list; motion,
   audio, VFX, and lighting needs; engine integration; and validation scenes.
   Each planned asset must name its purpose, style, source route, and acceptance
   criteria. Keep the plan aligned with the user's requested style.
3. **Produce and review assets.** Generate the planned assets, then run the
   applicable asset QA before integration. For mature asset types, especially
   3D objects, prefer capable closed-source/cloud generation APIs when they are
   available and permitted by the user's budget and privacy constraints. For
   less mature generation types—especially motion and 3D scenes—prefer suitable
   licensed assets from the chosen engine's asset library when that produces a
   more reliable, shippable result. Record provenance and licence information.
4. **Build the game in the selected engine.** Read
   `engine_context/engine_overview.md`; it routes you to the applicable CodeGen
   Skill and then the one matching engine API. Use only that API and the minimum
   relevant same-engine reference code to create the scene, gameplay, UI,
   materials, animation, effects, and engine-specific project structure.
5. **Validate, play, and iterate.** Build and launch the game, then execute the
   majority of the intended player operations rather than checking only startup.
   Use browser serving or the engine's capture path to create a small-resolution
   video for visual review. Inspect it for serious integration faults such as
   reversed mesh orientation, misplaced vehicle wheels, incorrectly attached
   weapons, broken animation, clipping, unusable controls, or missing UI. Also
   review whether VFX are appropriate, background lighting is harmonious, and
   the result follows the requested style. Fix findings and repeat the relevant
   build, play, capture, and review steps until the acceptance criteria pass.

## Start with the task requirement

Before writing or running anything, identify:

1. **Target engine** — `ue5`, `blender`, `unity3d`, or `three_js`.
2. **Requested deliverables** — assets, motion, audio, CG video, gameplay, UI,
   a scene, or a full playable slice.
3. **Acceptance criteria** — visual style, player interactions, platforms,
   performance limits, and the evidence required to call the result complete.
4. **Existing inputs** — requirement text, concept images, reference videos,
   generated artifacts, and any selected engine project.

Do not mix engine APIs. Select one target engine unless the requirement explicitly
asks for multiple independent deliverables.

## Required reading by task

| Work | Read first | Then read when needed |
|---|---|---|
| Generate or select a 3D object | `asset_qa/3d_object/SKILL.md` | `asset_qa/3d_object/orientation_review.md` for imported mesh facing and scale |
| Generate a 3D scene | `asset_qa/3d_scene/SKILL.md` | the selected engine API after the scene strategy is chosen |
| Rig, generate, fetch, or retarget motion | `asset_qa/motion/SKILL.md` | the selected engine API before importing the motion |
| Prepare a character image or T-pose | `asset_qa/image/SKILL.md` | the selected 3D-object or motion skill after preprocessing |
| Generate dialogue or sound effects | `asset_qa/audio/SKILL.md` | the selected engine API before in-game integration |
| Generate CG video | `asset_qa/cg_video/SKILL.md` | the selected engine API when the video is used in-game |
| Generate gameplay mechanics | `engine_context/engine_overview.md` | `code_gen/mechanic/game_generation.md`, then the selected engine API |
| Generate UI or browser play | `engine_context/engine_overview.md` | `code_gen/ui/game_ui_generation.md`, then the selected engine API and `engine_context/browser_serving_api.md` |
| Build a full game slice | this file, then `engine_context/engine_overview.md` | the required asset Skills, CodeGen Skills, and selected engine context routed by those documents |

## Select exactly one engine context

For Mechanic, UI, or full Engine integration, do not select an API directly
from this table before reading `engine_context/engine_overview.md`. That routing
document selects the applicable CodeGen Skill first and then exactly one matching
API context:

| Engine identifier | Required API context | Reference code |
|---|---|---|
| `ue5` | `engine_context/ue5_api.md` | `engine_adapters/ue5/` |
| `blender` | `engine_context/blender_api.md` | `engine_adapters/blender/` |
| `unity3d` | `engine_context/unity3d_api.md` | `engine_adapters/unity3d/` |
| `three_js` | `engine_context/three_js_api.md` | `engine_adapters/three_js/` |

Use public client APIs and documented launch paths only. Treat engine reference
projects as read-only implementation references unless the task explicitly grants
permission to edit them.

## Asset decision policy

For every requested asset, follow this order:

1. **Generate it** from the requirement. Prefer a suitable cloud model when it
   is available; use a local/open model when the requirement, budget, privacy,
   or offline execution calls for it. Ask the user when cost or provider choice
   materially changes the result.
2. **Use a licensed source or fallback** when generation quality is not suitable.
   Preserve source and licence/provenance information with the artifact. Do not
   bypass login-gated or licensed sources with scraping.
3. **Report the gap** when neither generation nor an allowed source can provide
   a shippable asset. State the missing capability, attempted route, and a safe
   fallback for the game.

Run the relevant visual QA skill for generated or imported 3D content before
claiming it is ready for a game. A structurally valid mesh can still face the
wrong direction, have implausible scale, or be visually unusable.

## Completion rules

- Preserve the task's acceptance criteria; do not substitute a different game
  or engine because it is easier to run.
- Use `pipeline/common/paths.py` for generated artifact paths; do not hand-build
  paths below `test_data/outputs/`.
- Keep generated assets, gameplay, UI, and engine integration as separate
  deliverables until their required validation has passed.
- Never claim that a game is playable solely because source code was written.
  Build, launch, representative player-operation checks, and visual review are
  separate evidence.
- For a game-delivery task, retain or report the final low-resolution review
  video and its reviewed flows. Verify mesh orientation, transforms, attachment
  points, animation, collision, camera, controls, VFX, UI, lighting, and style
  before declaring the game ready.
- Keep credentials in environment variables or local secret stores. Never commit
  API keys, tokens, or private media.
