"""Public command-line entry points backed only by UnityClient."""

from __future__ import annotations

import argparse
import json
from typing import Any, Sequence

from engine_adapters.unity3d import UnityClient


def _emit(result: dict[str, Any]) -> int:
    print(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result.get("ok") else 1


def _client(
    args: argparse.Namespace,
    *,
    project_attr: str = "project",
) -> UnityClient:
    return UnityClient(
        project_path=getattr(args, project_attr, ""),
        unity_root=args.unity_root,
        api_version=args.api_version,
        host=getattr(args, "remote_host", None),
        port=getattr(args, "remote_port", None),
        runtime_host=getattr(args, "runtime_host", None),
        runtime_port=getattr(args, "runtime_port", None),
        editor_batchmode_timeout=getattr(
            args,
            "editor_timeout",
            None,
        ),
    )


def _source_descriptor(
    args: argparse.Namespace,
) -> dict[str, str]:
    return {
        key: value
        for key, value in {
            "game_id": args.game_id,
            "run_id": args.run_id,
            "task_kind": args.task_kind,
            "task_id": args.task_id,
            "artifact_key": args.artifact_key,
        }.items()
        if value
    }


def _create_project(args: argparse.Namespace) -> dict[str, Any]:
    client = _client(args, project_attr="project_path")
    created = client.project.create(dry_run=args.dry_run)
    result = {
        "ok": bool(created.get("ok")),
        "operation": "scripts.create_project",
        "artifacts": list(created.get("artifacts") or []),
        "diagnostics": list(
            created.get("diagnostics") or []
        ),
        "warnings": list(created.get("warnings") or []),
        "errors": list(created.get("errors") or []),
        "payload": {
            "create": created,
            "build_requested": not args.skip_build,
            "dry_run": args.dry_run,
        },
    }
    if (
        not created.get("ok")
        or args.dry_run
        or args.skip_build
    ):
        return result

    built = client.build.project(
        target=args.target,
        configuration=args.configuration,
        timeout=args.build_timeout,
    )
    result["payload"]["build"] = built
    result["ok"] = bool(built.get("ok"))
    result["artifacts"].extend(
        built.get("artifacts") or []
    )
    result["diagnostics"].extend(
        built.get("diagnostics") or []
    )
    result["warnings"].extend(
        built.get("warnings") or []
    )
    result["errors"].extend(built.get("errors") or [])
    return result


def _import_asset(args: argparse.Namespace) -> dict[str, Any]:
    client = _client(args)
    source = _source_descriptor(args)
    asset_type = str(args.asset_type).strip().lower()
    if args.dry_run:
        resolved = client.assets.resolve_source(
            source,
            asset_type=asset_type,
        )
        return {
            "ok": bool(resolved.get("ok")),
            "operation": "scripts.import_asset",
            "artifacts": list(
                resolved.get("artifacts") or []
            ),
            "diagnostics": list(
                resolved.get("diagnostics") or []
            ),
            "warnings": list(
                resolved.get("warnings") or []
            ),
            "errors": list(resolved.get("errors") or []),
            "payload": {
                "dry_run": True,
                "source": source,
                "asset_type": asset_type,
                "destination": args.destination,
                "resolved": resolved,
            },
        }

    options = {
        key: value
        for key, value in {
            "category": args.category,
        }.items()
        if value is not None and value != ""
    }
    if asset_type == "scene":
        result = client.world.build(
            source,
            options={
                "world_id": args.world_id,
                "project_id": args.project_id,
                "publish": not args.no_publish,
                "native_scene": args.native_scene,
                "replace_existing": args.replace_existing,
            },
        )
    elif asset_type == "motion":
        result = client.assets.import_motion(
            source,
            skeleton=args.skeleton,
            destination=args.destination,
            options=options,
        )
    else:
        result = client.assets.import_asset(
            source,
            asset_type,
            destination=args.destination,
            options=options,
        )
    return result


def _run_editor(args: argparse.Namespace) -> dict[str, Any]:
    client = _client(args)
    return client.runtime.launch_editor(
        scene_path=args.scene,
        extra_args=args.extra_arg,
        dry_run=args.dry_run,
    )


def _add_client_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    parser.add_argument("--unity-root", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--api-version", default="v1")
    parser.add_argument(
        "--remote-host",
        default="127.0.0.1",
    )
    parser.add_argument(
        "--remote-port",
        type=int,
        default=30010,
    )
    parser.add_argument(
        "--runtime-host",
        default="127.0.0.1",
    )
    parser.add_argument(
        "--runtime-port",
        type=int,
        default=30030,
    )
    parser.add_argument(
        "--editor-timeout",
        type=int,
        default=1800,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="a3game-unity")
    commands = parser.add_subparsers(
        dest="command",
        required=True,
    )

    create = commands.add_parser("create-project")
    create.add_argument("--unity-root", required=True)
    create.add_argument("--project-path", required=True)
    create.add_argument("--api-version", default="v1")
    create.add_argument(
        "--target",
        default="",
        help="Unity BuildTarget; defaults to the current host platform",
    )
    create.add_argument(
        "--configuration",
        default="Development",
    )
    create.add_argument(
        "--build-timeout",
        type=float,
        default=None,
    )
    create.add_argument("--skip-build", action="store_true")
    create.add_argument("--dry-run", action="store_true")

    asset = commands.add_parser("import-asset")
    _add_client_arguments(asset)
    asset.add_argument("--game-id", required=True)
    asset.add_argument("--run-id", default="default")
    asset.add_argument("--task-kind", default="")
    asset.add_argument("--task-id", required=True)
    asset.add_argument("--artifact-key", default="")
    asset.add_argument("--type", dest="asset_type", required=True)
    asset.add_argument("--destination", default="")
    asset.add_argument("--category", default="")
    asset.add_argument("--skeleton", default="")
    asset.add_argument("--world-id", default="")
    asset.add_argument("--project-id", default="")
    asset.add_argument("--no-publish", action="store_true")
    asset.add_argument(
        "--replace-existing",
        action="store_true",
    )
    asset.add_argument("--native-scene", default="")
    asset.add_argument("--dry-run", action="store_true")

    run = commands.add_parser("run")
    _add_client_arguments(run)
    run.add_argument("--scene", default="")
    run.add_argument(
        "--extra-arg",
        action="append",
        default=[],
    )
    run.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if args.command == "create-project":
            return _emit(_create_project(args))
        if args.command == "import-asset":
            return _emit(_import_asset(args))
        if args.command == "run":
            return _emit(_run_editor(args))
        raise AssertionError(args.command)
    except (
        FileExistsError,
        FileNotFoundError,
        RuntimeError,
        TimeoutError,
        ValueError,
    ) as exc:
        return _emit(
            {
                "ok": False,
                "operation": "scripts.error",
                "artifacts": [],
                "diagnostics": [],
                "warnings": [],
                "errors": [
                    f"{type(exc).__name__}: {exc}"
                ],
                "payload": {},
            }
        )


if __name__ == "__main__":
    raise SystemExit(main())
