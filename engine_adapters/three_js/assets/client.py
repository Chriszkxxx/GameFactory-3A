"""Stable asset operations for ThreeClient v1."""

from __future__ import annotations

from typing import Any, Mapping

from ..config import DEFAULT_IMPORT_ROOT, ThreeClientConfig
from ..contracts import ThreeOperationResult
from ._internal import (
    ArtifactRegistry,
    AssetService,
    GeneratedAssetSourceResolver,
    ResolvedAssetSource,
)


class ThreeAssetsClient:
    def __init__(self, config: ThreeClientConfig) -> None:
        self._config = config
        self._sources = GeneratedAssetSourceResolver()
        self._service = AssetService(
            config,
            artifact_registry=ArtifactRegistry(
                config.artifact_registry_path
            ),
        )

    def import_asset(
        self,
        source: Mapping[str, Any],
        asset_type: str,
        *,
        destination: str = "",
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        allow_directory = str(asset_type or "").strip().lower() in {
            "scene",
            "effect",
            "environment",
        }
        try:
            resolved = self._resolve_source(
                source,
                asset_type,
                allow_directory=allow_directory,
            )
        except Exception as exc:
            return self._source_failure(
                "assets.import_asset",
                source,
                exc,
            )
        try:
            payload = self._service.import_asset(
                str(resolved.path),
                asset_type,
                dst_path=destination,
                **dict(options or {}),
            )
        except Exception as exc:
            return ThreeOperationResult.failure(
                "assets.import_asset",
                f"{type(exc).__name__}: {exc}",
                payload={
                    "asset_type": asset_type,
                    "source": resolved.descriptor(),
                },
            ).to_dict()
        result = self._import_result(
            "assets.import_asset",
            payload,
        )
        result["payload"]["source"] = resolved.descriptor()
        return result

    def import_avatar(
        self,
        source: Mapping[str, Any],
        *,
        destination: str = "",
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = self.import_asset(
            source,
            "avatar",
            destination=destination,
            options=options,
        )
        result["operation"] = "assets.import_avatar"
        return result

    def import_motion(
        self,
        source: Mapping[str, Any],
        *,
        skeleton: str = "",
        destination: str = "",
        avatar_name: str = "",
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resolved_options = dict(options or {})
        if skeleton:
            resolved_options["skeleton_artifact_id"] = skeleton
        if avatar_name:
            resolved_options["avatar_name"] = avatar_name
        result = self.import_asset(
            source,
            "motion",
            destination=destination,
            options=resolved_options,
        )
        result["operation"] = "assets.import_motion"
        return result

    def import_scene(
        self,
        source: Mapping[str, Any],
        *,
        destination: str = "",
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = self.import_asset(
            source,
            "scene",
            destination=destination,
            options=options,
        )
        result["operation"] = "assets.import_scene"
        return result

    def import_prop(
        self,
        source: Mapping[str, Any],
        *,
        destination: str = "",
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = self.import_asset(
            source,
            "prop",
            destination=destination,
            options=options,
        )
        result["operation"] = "assets.import_prop"
        return result

    def import_weapon(
        self,
        source: Mapping[str, Any],
        *,
        destination: str = "",
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = self.import_asset(
            source,
            "weapon",
            destination=destination,
            options=options,
        )
        result["operation"] = "assets.import_weapon"
        return result

    def import_material(
        self,
        source: Mapping[str, Any],
        *,
        destination: str = "",
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = self.import_asset(
            source,
            "material",
            destination=destination,
            options=options,
        )
        result["operation"] = "assets.import_material"
        return result

    def import_texture(
        self,
        source: Mapping[str, Any],
        *,
        destination: str = "",
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = self.import_asset(
            source,
            "texture",
            destination=destination,
            options=options,
        )
        result["operation"] = "assets.import_texture"
        return result

    def import_effect(
        self,
        source: Mapping[str, Any],
        *,
        destination: str = "",
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = self.import_asset(
            source,
            "effect",
            destination=destination,
            options=options,
        )
        result["operation"] = "assets.import_effect"
        return result

    def import_audio(
        self,
        source: Mapping[str, Any],
        *,
        destination: str = "",
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = self.import_asset(
            source,
            "audio",
            destination=destination,
            options=options,
        )
        result["operation"] = "assets.import_audio"
        return result

    def validate(
        self,
        source: Mapping[str, Any],
        asset_type: str,
        *,
        destination: str = "",
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        allow_directory = str(asset_type or "").strip().lower() in {
            "scene",
            "effect",
            "environment",
        }
        try:
            resolved = self._resolve_source(
                source,
                asset_type,
                allow_directory=allow_directory,
            )
        except Exception as exc:
            return self._source_failure(
                "assets.validate",
                source,
                exc,
            )
        try:
            validation = self._service.validate_asset(
                str(resolved.path),
                asset_type,
                dst_path=destination,
                **dict(options or {}),
            )
        except Exception as exc:
            return ThreeOperationResult.failure(
                "assets.validate",
                f"{type(exc).__name__}: {exc}",
                payload={
                    "asset_type": asset_type,
                    "source": resolved.descriptor(),
                },
            ).to_dict()
        return ThreeOperationResult(
            operation="assets.validate",
            ok=validation.ok,
            warnings=tuple(validation.warnings),
            errors=tuple(validation.errors),
            payload={
                **dict(validation.payload),
                "asset_type": asset_type,
                "source": resolved.descriptor(),
            },
        ).to_dict()

    def resolve_source(
        self,
        source: Mapping[str, Any],
        *,
        asset_type: str = "",
    ) -> dict[str, Any]:
        try:
            resolved = self._resolve_source(
                source,
                asset_type,
                allow_directory=(
                    str(asset_type or "").strip().lower() == "scene"
                    or str(source.get("task_kind") or "").strip()
                    == "3d_scene"
                ),
            )
        except Exception as exc:
            return self._source_failure(
                "assets.resolve_source",
                source,
                exc,
            )
        return ThreeOperationResult.success(
            "assets.resolve_source",
            payload={
                "source": resolved.descriptor(),
                "path": str(resolved.path),
                "meta_path": str(resolved.meta_path),
                "metadata": dict(resolved.metadata),
            },
        ).to_dict()

    def list(
        self,
        asset_type: str = "",
        *,
        root: str = DEFAULT_IMPORT_ROOT,
    ) -> dict[str, Any]:
        try:
            assets = self._service.list_assets(
                asset_type=asset_type or None,
                root_path=root,
            )
        except Exception as exc:
            return ThreeOperationResult.failure(
                "assets.list",
                f"{type(exc).__name__}: {exc}",
                payload={
                    "asset_type": asset_type,
                    "root": root,
                },
            ).to_dict()
        return ThreeOperationResult.success(
            "assets.list",
            artifacts=[
                self._query_artifact(asset)
                for asset in assets
            ],
            payload={
                "asset_type": asset_type,
                "root": root,
                "count": len(assets),
            },
        ).to_dict()

    def list_registered(
        self,
        asset_type: str = "",
    ) -> dict[str, Any]:
        records = self._service.artifacts.list(
            type=asset_type or None,
        )
        return ThreeOperationResult.success(
            "assets.list_registered",
            artifacts=[
                record.to_dict()
                for record in records
            ],
            payload={
                "asset_type": asset_type,
                "count": len(records),
                "registry_path": str(
                    self._config.artifact_registry_path
                ),
            },
        ).to_dict()

    def get_metadata(
        self,
        artifact_id: str,
    ) -> dict[str, Any]:
        record = self._service.artifacts.get(artifact_id)
        if record is None:
            return ThreeOperationResult.failure(
                "assets.get_metadata",
                f"Unknown artifact_id: {artifact_id}",
            ).to_dict()
        return ThreeOperationResult.success(
            "assets.get_metadata",
            artifacts=[record.to_dict()],
        ).to_dict()

    def write_manifest(self) -> dict[str, Any]:
        try:
            manifest_path = self._service.write_manifest()
        except Exception as exc:
            return ThreeOperationResult.failure(
                "assets.write_manifest",
                f"{type(exc).__name__}: {exc}",
            ).to_dict()
        if manifest_path is None:
            return ThreeOperationResult.failure(
                "assets.write_manifest",
                "project_path is not configured",
            ).to_dict()
        records = self._service.artifacts.list()
        return ThreeOperationResult.success(
            "assets.write_manifest",
            artifacts=[
                {
                    "type": "web_asset_manifest",
                    "path": str(manifest_path),
                    "state": "ready",
                }
            ],
            payload={
                "manifest_path": str(manifest_path),
                "asset_count": len(records),
            },
        ).to_dict()

    def _resolve_source(
        self,
        source: Mapping[str, Any],
        asset_type: str,
        *,
        allow_directory: bool = False,
    ) -> ResolvedAssetSource:
        return self._sources.resolve(
            source,
            asset_type=asset_type,
            allow_directory=allow_directory,
        )

    @staticmethod
    def _source_failure(
        operation: str,
        source: Any,
        exc: Exception,
    ) -> dict[str, Any]:
        descriptor = (
            dict(source)
            if isinstance(source, Mapping)
            else {"value": str(source)}
        )
        return ThreeOperationResult.failure(
            operation,
            f"{type(exc).__name__}: {exc}",
            payload={"source": descriptor},
        ).to_dict()

    @staticmethod
    def _import_result(
        operation: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        artifacts = [
            dict(item)
            for item in payload.get("artifacts") or []
            if isinstance(item, dict)
        ]
        warnings = [
            str(item)
            for item in payload.get("warnings") or []
        ]
        errors = [
            str(item)
            for item in payload.get("errors") or []
        ]
        extra = {
            key: value
            for key, value in payload.items()
            if key not in {
                "ok",
                "artifacts",
                "warnings",
                "errors",
            }
        }
        return ThreeOperationResult(
            operation=operation,
            ok=bool(payload.get("ok", not errors)),
            artifacts=tuple(artifacts),
            warnings=tuple(warnings),
            errors=tuple(errors),
            payload=extra,
        ).to_dict()

    @staticmethod
    def _query_artifact(asset: dict[str, Any]) -> dict[str, Any]:
        path = str(asset.get("path") or "")
        return {
            "artifact_id": path,
            "asset_id": str(
                asset.get("name")
                or path.rsplit("/", 1)[-1]
            ),
            "type": str(asset.get("type") or ""),
            "backend": "web",
            "backend_class": str(asset.get("class") or ""),
            "backend_path": path,
            "metadata": {
                key: value
                for key, value in asset.items()
                if key
                not in {
                    "name",
                    "path",
                    "type",
                    "class",
                }
            },
        }
