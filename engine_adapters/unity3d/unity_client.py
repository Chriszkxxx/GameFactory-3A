"""Stable Agent-facing facade for Unity3D engine environment operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ._internal.transport import UnityEditorTransport
from .assets import UnityAssetsClient
from .animation import UnityAnimationClient
from .bindings import UnityBindingsClient
from .build import UnityBuildClient
from .config import DEFAULT_API_VERSION, UnityClientConfig
from .observe import UnityObserveClient
from .project import UnityProjectClient
from .plugin import UnityPluginClient
from .reflection import UnityReflectionClient
from .runtime import UnityRuntimeClient
from .testing import UnityTestingClient
from .world import UnityWorldClient


class UnityClient:
    """
    Stable Unity3D engine environment API.

    Agent code must construct UnityClient from `engine_adapters.unity3d` and
    use its public namespace clients. Internal modules are version-specific
    and are not part of the API contract.
    """

    def __init__(
        self,
        project_path: str | Path | None = None,
        unity_root: str | Path | None = None,
        api_version: str = DEFAULT_API_VERSION,
        *,
        host: str | None = None,
        port: int | None = None,
        runtime_host: str | None = None,
        runtime_port: int | None = None,
        editor_batchmode_timeout: int | None = None,
    ) -> None:
        self._config = UnityClientConfig.resolve(
            project_path=project_path,
            unity_root=unity_root,
            api_version=api_version,
            host=host,
            port=port,
            runtime_host=runtime_host,
            runtime_port=runtime_port,
            editor_batchmode_timeout=editor_batchmode_timeout,
        )
        transport = UnityEditorTransport(self._config)

        self.project = UnityProjectClient(self._config)
        self.build = UnityBuildClient(self._config)
        self.testing = UnityTestingClient(self._config)
        self.plugin = UnityPluginClient(self._config)
        self.assets = UnityAssetsClient(
            self._config,
            transport,
        )
        self.animation = UnityAnimationClient(self.assets)
        self.bindings = UnityBindingsClient(
            transport,
            self.assets,
        )
        self.world = UnityWorldClient(
            self._config,
            transport,
            self.assets,
        )
        self.reflection = UnityReflectionClient(
            transport,
            self.assets,
        )
        self.runtime = UnityRuntimeClient(
            self._config,
            self.assets,
        )
        self.observe = UnityObserveClient(
            self._config,
            transport,
        )

    @property
    def api_version(self) -> str:
        return self._config.api_version

    def get_environment_info(self) -> dict[str, Any]:
        info = self.project.get_info()
        info["operation"] = "client.get_environment_info"
        info["payload"]["remote_url"] = (
            self._config.remote_url
        )
        info["payload"]["runtime_input_host"] = (
            self._config.runtime_host
        )
        info["payload"]["runtime_input_port"] = (
            self._config.runtime_port
        )
        info["payload"]["editor_batchmode_timeout"] = (
            self._config.editor_batchmode_timeout
        )
        return info
