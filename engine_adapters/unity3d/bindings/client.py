"""Stable material and asset binding operations for UnityClient v1."""

from __future__ import annotations

from typing import Any, Mapping

from .._internal.transport.unity_editor import UnityEditorTransport
from ..assets import UnityAssetsClient
from ..contracts import UnityOperationResult


class UnityBindingsClient:
    def __init__(
        self,
        transport: UnityEditorTransport,
        assets: UnityAssetsClient,
    ) -> None:
        self._transport = transport
        self._assets = assets

    def bind_pbr_material(
        self,
        *,
        asset_id: str,
        source: Mapping[str, Any],
        mesh_assets: list[str],
        destination: str,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            resolved = self._assets._resolve_source(
                source,
                "material",
            )
        except Exception as exc:
            return UnityOperationResult.failure(
                "bindings.bind_pbr_material",
                f"{type(exc).__name__}: {exc}",
                payload={"source": dict(source)},
            ).to_dict()
        try:
            report = self._transport.execute_method(
                "ImportGeneratedMaterial.RunFromCLI",
                args={
                    "src": str(resolved.path),
                    "dest": destination,
                    "asset_id": asset_id,
                    "mesh_assets": list(mesh_assets),
                    **dict(options or {}),
                },
            )
        except Exception as exc:
            return UnityOperationResult.failure(
                "bindings.bind_pbr_material",
                f"{type(exc).__name__}: {exc}",
                payload={
                    "asset_id": asset_id,
                    "source": resolved.descriptor(),
                },
            ).to_dict()
        if not isinstance(report, dict):
            report = {"ok": False, "error": "Invalid report from Unity"}
        report["source"] = resolved.descriptor()
        return UnityOperationResult(
            operation="bindings.bind_pbr_material",
            ok=bool(report.get("ok", False)),
            warnings=tuple(
                str(item)
                for item in report.get("warnings") or []
            ),
            errors=tuple(
                str(item)
                for item in [report.get("error", "")] + list(report.get("errors") or [])
                if str(item)
            ),
            payload={
                key: value
                for key, value in report.items()
                if key not in {"ok", "warnings", "errors", "error"}
            },
        ).to_dict()
