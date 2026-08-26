"""Step functions for the 3D object operator."""

from .art_plan import (
    DEFAULT_DECIMATION_TARGET,
    DEFAULT_TEXTURE_SIZE,
    GAME_ART_PLANS,
    GENERATED_FORWARD_AXIS,
    PROMPT_STYLE,
    concept_image,
    describe_plans,
    frame_subject,
    neutral_canvas,
    plan_for_game,
)
from .asset_import import (
    find_project_file,
    import_asset,
    stage_task_output,
)
from .asset_pack import ASSET_PACK, download, fetch_asset_pack
from .code_asset import (
    AXES,
    GATES,
    MAX_ATTEMPTS,
    PRIMITIVES,
    SpecError,
    build_code_asset,
    correct_spec,
    estimate_triangles,
    run_gates,
    spec_bounds,
    suits_code_asset,
    validate_spec,
)
from .mesh_cleanup import strip_ground_plate

__all__ = [
    "ASSET_PACK",
    "AXES",
    "DEFAULT_DECIMATION_TARGET",
    "DEFAULT_TEXTURE_SIZE",
    "GAME_ART_PLANS",
    "GATES",
    "GENERATED_FORWARD_AXIS",
    "MAX_ATTEMPTS",
    "PRIMITIVES",
    "PROMPT_STYLE",
    "SpecError",
    "build_code_asset",
    "concept_image",
    "correct_spec",
    "describe_plans",
    "download",
    "estimate_triangles",
    "fetch_asset_pack",
    "find_project_file",
    "frame_subject",
    "import_asset",
    "neutral_canvas",
    "plan_for_game",
    "run_gates",
    "spec_bounds",
    "stage_task_output",
    "strip_ground_plate",
    "suits_code_asset",
    "validate_spec",
]
