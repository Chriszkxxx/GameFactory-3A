# Framework Documentation Update Proposal

The public README and navigation documents remain unchanged from their
upstream versions. This file records small documentation updates that may be
applied later after maintainer review.

Detailed callable Engine APIs do not belong in README files or in this
migration note. They remain in:

```text
agent_skills/engine_context/<engine>_api.md
```

For Unreal Engine, the authoritative Agent-facing API reference is:

```text
agent_skills/engine_context/ue5_api.md
```

## Root README

The repository tree may eventually describe the implemented UE5 adapter more
precisely:

```text
engine_adapters/
    ue5/       UEClient, runtime framework, Preview, and examples
    unity3d/
    blender/
    three_js/
```

The scripts tree may mention that `scripts/ue/` contains platform wrappers
around the public UE adapter CLI:

```text
scripts/
    ue/
    installing/
```

The code-generation overview should be updated only after the repository-wide
navigation is ready to move from the legacy Operator wording. The current
implementation uses an outer-Agent preparation lifecycle:

```text
pipeline/code_gen/gen_mechanic/run.py prepare
    -> prepared task packet, Skill, Prompt, and Engine Context
    -> outer Agent edits task-owned source
    -> pipeline/code_gen/gen_mechanic/run.py finalize
```

The Pipeline does not load a Model, construct an Operator, or launch a nested
Agent. Engine execution and evaluation remain separate responsibilities.

## Agent Skills Setting Overview

The setting overview may later describe `engine_context/` as selectable
per-engine API notes:

```text
agent_skills/
    setting_overview.md
    develop_harness/
    engine_context/
        ue5_api.md
        unity3d_api.md
        blender_api.md
        three_js_api.md
```

Mechanic task data provides an Engine identifier and the Engine Context
directory. The outer Agent selects the matching non-empty API document and
reads it before using concrete engine APIs. Tasks do not hard-code a concrete
API document path.

Keep this overview short. Engine methods, parameters, launch behavior, testing
operations, and implementation details belong in the matching
`agent_skills/engine_context/*_api.md` document.

## Engine Adapters README

The UE5 directory summary may eventually be updated to mention the public
facade and major framework responsibilities:

```text
ue5/
    public UEClient facade
    runtime and World operations
    asset import
    Automation testing
    AAAGamePlayable and Preview support
    read-only reference examples
```

Repository launchers under `scripts/ue/` call the public UE adapter CLI. The
README should not document private transports, internal importer classes, or
the full callable API surface.

Those details are maintained in:

```text
agent_skills/engine_context/ue5_api.md
```

## Files Intentionally Kept At Upstream Content

The following files should remain identical to their upstream versions until a
maintainer approves the proposed navigation updates:

```text
README.md
agent_skills/setting_overview.md
engine_adapters/README.md
```
