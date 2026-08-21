"""Godot browser backend implemented only through public GodotClient."""

from __future__ import annotations

import socket
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from time import sleep, time
from typing import Any
from uuid import uuid4

from engine_adapters.godot import GodotClient
from engine_adapters.godot.web_server import validate_web_root, validate_web_tree

from ..config import BrowserServingConfig
from ..contracts import (
    AssetImportRequest,
    AssetRecord,
    EngineCapabilities,
    EngineDescriptor,
    WorldRecord,
    serving_result,
)


def _port_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, int(port))) != 0


def _payload(result: Mapping[str, Any]) -> dict[str, Any]:
    return dict(result.get("payload") or {})


def _errors(result: Mapping[str, Any]) -> list[str]:
    return [str(item) for item in result.get("errors") or []]


def _asset(item: Mapping[str, Any], asset_type: str = "") -> dict[str, Any]:
    value = dict(item)
    primary = dict(value.get("primary_asset") or {})
    backend_path = str(
        value.get("backend_path") or value.get("path") or primary.get("path") or ""
    )
    backend_class = str(
        value.get("backend_class") or value.get("class") or primary.get("class") or ""
    )
    return AssetRecord(
        artifact_id=str(value.get("artifact_id") or backend_path),
        asset_id=str(value.get("asset_id") or Path(backend_path).stem),
        artifact_type=str(value.get("type") or asset_type),
        engine="godot",
        state=str(value.get("state") or "ready"),
        capabilities={
            str(key): bool(flag)
            for key, flag in dict(value.get("runtime_capabilities") or {}).items()
        },
        native={
            "backend": "godot",
            "class": backend_class,
            "path": backend_path,
            "primary_asset": primary,
            "runtime": dict(value.get("runtime") or {}),
        },
        metadata=dict(value.get("metadata") or {}),
    ).to_dict()


def _world(item: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(item)
    metadata = dict(value.get("metadata") or {})
    return WorldRecord(
        package_id=str(metadata.get("package_id") or value.get("artifact_id") or ""),
        world_id=str(metadata.get("world_id") or value.get("asset_id") or ""),
        project_id=str(metadata.get("project_id") or ""),
        engine="godot",
        state=str(metadata.get("status") or value.get("state") or "published"),
        manifest=metadata,
    ).to_dict()


@dataclass
class GodotBrowserSession:
    session_id: str
    participant_id: str
    user_id: str
    state: str
    web_port: int
    stream_url: str
    client: Any = field(repr=False)
    character: dict[str, Any] = field(default_factory=dict)
    world_id: str = ""
    project_id: str = ""
    package_id: str = ""
    server_pid: int = 0
    server_process: subprocess.Popen[Any] | None = field(default=None, repr=False)
    created_at: float = field(default_factory=time)
    updated_at: float = field(default_factory=time)
    last_input: dict[str, Any] = field(default_factory=dict)
    last_command: str = ""
    recovered_external: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "participant_id": self.participant_id,
            "user_id": self.user_id,
            "state": self.state,
            "web_port": self.web_port,
            "stream_url": self.stream_url,
            "pixel_streaming_url": "",
            "streaming_transport": "godot_web_http",
            "input_transport": "browser_canvas",
            "runtime_kind": "godot_web",
            "character": dict(self.character),
            "world_id": self.world_id,
            "project_id": self.project_id,
            "runtime_package_id": self.package_id,
            "server_pid": self.server_pid,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_input": dict(self.last_input),
            "last_command": self.last_command,
            "recovered_external": self.recovered_external,
        }


class GodotExampleBackend:
    def __init__(
        self,
        config: BrowserServingConfig,
        *,
        client_factory: Callable[..., Any] = GodotClient,
    ) -> None:
        self.config = config
        self._client_factory = client_factory
        self._sessions: dict[str, GodotBrowserSession] = {}
        self._lock = RLock()
        self._descriptor = EngineDescriptor(
            engine_id="godot",
            display_name="Godot 4",
            backend_kind="example_backend",
            capabilities=EngineCapabilities(
                asset_upload=True,
                asset_import=True,
                asset_inspection=True,
                world_build=True,
                world_catalog=True,
                runtime_sessions=True,
                runtime_character_configuration=False,
                runtime_world_loading=False,
                runtime_input=False,
                skeletal_animation=False,
                streaming=True,
                pixel_streaming=False,
                preview_camera=False,
            ),
        )
        self._admin_client = self._new_client(config.base_runtime_port)

    @property
    def descriptor(self) -> EngineDescriptor:
        return self._descriptor

    def _new_client(self, runtime_port: int):
        return self._client_factory(
            project_path=self.config.godot_project,
            godot_executable=self.config.godot_executable,
            runtime_host=self.config.godot_runtime_host,
            runtime_port=runtime_port,
        )

    def status(self) -> dict[str, Any]:
        environment = self._admin_client.get_environment_info()
        info = _payload(environment)
        editor_configured = bool(
            info.get("project_exists")
            and info.get("godot_executable_exists")
            and info.get("engine_version_supported")
        )
        configured_build = self.config.godot_web_build
        if (
            configured_build is not None
            and configured_build.name.lower() == "index.html"
        ):
            configured_build = configured_build.parent
        web_build_error = ""
        web_build_configured = False
        if configured_build is not None:
            try:
                validate_web_root(configured_build)
                web_build_configured = True
            except (OSError, ValueError) as exc:
                web_build_error = str(exc)
        configured = editor_configured or web_build_configured
        warnings = []
        if web_build_error:
            warnings.append(web_build_error)
        if not configured:
            warnings.append("Godot browser backend is not configured")
        return serving_result(
            "engine.status",
            engine="godot",
            ok=configured,
            payload={
                "configured": configured,
                "editor_configured": editor_configured,
                "web_build_configured": web_build_configured,
                "web_build_error": web_build_error,
                "environment": environment,
                "message": (
                    "Godot editor backend configured"
                    if editor_configured
                    else (
                        "Godot prebuilt Web backend configured"
                        if web_build_configured
                        else "Set A3GAME_GODOT_PROJECT and A3GAME_GODOT_EXECUTABLE, "
                        "or A3GAME_GODOT_WEB_BUILD"
                    )
                ),
            },
            warnings=warnings,
        )

    def import_asset(self, request: AssetImportRequest) -> dict[str, Any]:
        asset_type = request.asset_type
        method_name = {
            "avatar": "import_avatar",
            "motion": "import_motion",
            "scene": "import_scene",
            "effect": "import_effect",
            "material": "import_material",
            "prop": "import_prop",
            "object": "import_prop",
            "static_mesh": "import_prop",
            "texture": "import_texture",
            "weapon": "import_weapon",
            "audio": "import_audio",
        }.get(asset_type, "import_asset")
        method = getattr(self._admin_client.assets, method_name)
        options = {**dict(request.options), "dry_run": self.config.dry_run}
        if method_name == "import_asset":
            result = method(
                request.descriptor,
                asset_type,
                destination=request.destination,
                options=options,
            )
        elif method_name == "import_motion":
            result = method(
                request.descriptor,
                skeleton=str(options.pop("skeleton", "")),
                destination=request.destination,
                options=options,
            )
        else:
            result = method(
                request.descriptor,
                destination=request.destination,
                options=options,
            )
        return self._translate("assets.import", result, asset_type)

    def inspect_asset(self, artifact_id: str) -> dict[str, Any]:
        return self._translate(
            "assets.inspect", self._admin_client.assets.get_metadata(artifact_id)
        )

    def list_assets(
        self,
        asset_type: str = "",
        *,
        root_uri: str = "",
    ) -> list[dict[str, Any]]:
        result = self._admin_client.assets.list(
            asset_type, root=root_uri or "assets/imported"
        )
        if not result.get("ok"):
            result = self._admin_client.assets.list_registered(asset_type)
        return [
            _asset(item, asset_type)
            for item in result.get("artifacts") or []
            if isinstance(item, Mapping)
        ]

    def build_world(self, request: AssetImportRequest) -> dict[str, Any]:
        result = self._admin_client.world.build(
            request.descriptor,
            options={**dict(request.options), "dry_run": self.config.dry_run},
        )
        return self._translate("worlds.build", result, "scene")

    def list_worlds(self, *, project_id: str = "") -> list[dict[str, Any]]:
        result = self._admin_client.world.list_packages(project_id=project_id)
        return [
            _world(item)
            for item in result.get("artifacts") or []
            if isinstance(item, Mapping)
        ]

    def create_session(self, request: Mapping[str, Any]) -> dict[str, Any]:
        requested_character = {
            str(key): value
            for key, value in dict(request.get("character") or {}).items()
            if value not in (None, "")
        }
        if requested_character:
            return serving_result(
                "sessions.create",
                engine="godot",
                ok=False,
                errors=[
                    (
                        "Godot Web sessions cannot inject a character after export; "
                        "configure the project before creating the Web build"
                    )
                ],
                payload={"created": False, "character": requested_character},
            )
        session_id = f"bs_{uuid4().hex[:10]}"
        user_id = str(request.get("user_id") or "")
        participant_id = str(
            request.get("participant_id") or f"participant_{user_id or session_id}"
        )
        with self._lock:
            slot, web_port = self._allocate_port()
            client = self._new_client(self.config.base_runtime_port + slot)
            session = GodotBrowserSession(
                session_id=session_id,
                participant_id=participant_id,
                user_id=user_id,
                state="CREATED",
                web_port=web_port,
                stream_url=f"http://{self.config.pixel_host}:{web_port}/index.html",
                client=client,
                character={},
            )
            self._sessions[session_id] = session
        try:
            session.state = "BOOTING_WEB"
            if not self.config.dry_run:
                web_root = self._ensure_web_build(client)
                session.server_process = self._start_server(web_root, web_port)
                session.server_pid = session.server_process.pid
                self._wait_for_http(session)
            session.state = "WEB_READY"
        except Exception:
            self._stop_process(session)
            with self._lock:
                self._sessions.pop(session_id, None)
            raise
        return serving_result(
            "sessions.create",
            engine="godot",
            payload={"slot": slot, **session.to_dict()},
        )

    def list_sessions(self) -> dict[str, Any]:
        return serving_result(
            "sessions.list",
            engine="godot",
            payload={"sessions": [item.to_dict() for item in self._sessions.values()]},
        )

    def get_session(self, session_id: str) -> dict[str, Any]:
        return serving_result(
            "sessions.get", engine="godot", payload=self._require(session_id).to_dict()
        )

    def recover_session(self, snapshot: Mapping[str, Any]) -> dict[str, Any]:
        session_id = str(snapshot.get("session_id") or "").strip()
        if not session_id:
            raise ValueError("session_id is required")
        if session_id in self._sessions:
            return self.get_session(session_id)
        web_port = int(snapshot.get("web_port") or 0)
        stream_url = str(snapshot.get("stream_url") or "").strip()
        parsed_stream = urllib.parse.urlsplit(stream_url)
        if parsed_stream.scheme not in {"http", "https"} or not parsed_stream.netloc:
            raise ValueError("Recovered Godot Web session requires an HTTP stream_url")
        if not self.config.dry_run:
            try:
                with urllib.request.urlopen(stream_url, timeout=2.0) as response:
                    if int(response.status) >= 500:
                        raise RuntimeError(
                            f"Stored Godot Web page returned HTTP {response.status}"
                        )
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                raise RuntimeError(
                    f"Stored Godot Web page is not reachable: {stream_url}"
                ) from exc
        session = GodotBrowserSession(
            session_id=session_id,
            participant_id=str(
                snapshot.get("participant_id") or f"participant_{session_id}"
            ),
            user_id=str(snapshot.get("user_id") or ""),
            state=str(snapshot.get("state") or "WEB_READY"),
            web_port=web_port,
            stream_url=stream_url,
            client=self._new_client(self.config.base_runtime_port),
            character=dict(snapshot.get("character") or {}),
            world_id=str(snapshot.get("world_id") or ""),
            project_id=str(snapshot.get("project_id") or ""),
            package_id=str(snapshot.get("runtime_package_id") or ""),
            recovered_external=True,
        )
        self._sessions[session_id] = session
        return serving_result(
            "sessions.recover",
            engine="godot",
            payload={"recovered": True, **session.to_dict()},
        )

    def session_catalog(self, *, project_id: str = "") -> dict[str, Any]:
        return serving_result(
            "sessions.catalog",
            engine="godot",
            payload={
                "avatars": self.list_assets("avatar"),
                "motions": self.list_assets("motion"),
                "worlds": self.list_worlds(project_id=project_id),
                "runtime_ready": True,
                "runtime_controls": {
                    "character_configuration": False,
                    "world_loading": False,
                    "normalized_input": False,
                    "native_canvas_input": True,
                },
                "project_id": project_id,
            },
        )

    def configure_session(
        self,
        session_id: str,
        character: Mapping[str, Any],
    ) -> dict[str, Any]:
        return self._unsupported_web_control(
            "sessions.configure",
            self._require(session_id),
            "character configuration",
            {"requested_character": dict(character)},
        )

    def play_preview_animation(
        self,
        session_id: str,
        animation: str,
        *,
        loop: bool = True,
        play_rate: float = 1.0,
    ) -> dict[str, Any]:
        return self._unsupported_web_control(
            "sessions.play_preview_animation",
            self._require(session_id),
            "preview animation",
            {
                "animation": str(animation),
                "loop": bool(loop),
                "play_rate": float(play_rate),
            },
        )

    def load_world(
        self,
        session_id: str,
        *,
        package_id: str = "",
        world_id: str = "",
        project_id: str = "",
    ) -> dict[str, Any]:
        return self._unsupported_web_control(
            "sessions.load_world",
            self._require(session_id),
            "dynamic World loading",
            {
                "package_id": str(package_id),
                "world_id": str(world_id),
                "project_id": str(project_id),
            },
        )

    def join_world(self, session_id: str, *, server_uri: str = "") -> dict[str, Any]:
        return self._unsupported_web_control(
            "sessions.join_world",
            self._require(session_id),
            "dynamic World joining",
            {"server_uri": str(server_uri)},
        )

    def leave_world(self, session_id: str) -> dict[str, Any]:
        return self._unsupported_web_control(
            "sessions.leave_world",
            self._require(session_id),
            "dynamic World leaving",
        )

    def apply_input(
        self,
        session_id: str,
        input_state: Mapping[str, Any],
    ) -> dict[str, Any]:
        return self._unsupported_web_control(
            "sessions.apply_input",
            self._require(session_id),
            "server-side normalized input",
            {
                "accepted": False,
                "recorded": False,
                "applied": False,
                "input": dict(input_state),
            },
        )

    def apply_preview_camera(
        self,
        session_id: str,
        camera_input: Mapping[str, Any],
    ) -> dict[str, Any]:
        return self._unsupported_web_control(
            "sessions.apply_preview_camera",
            self._require(session_id),
            "server-side preview camera input",
            {"applied": False, "input": dict(camera_input)},
        )

    def handle_runtime_event(
        self,
        session_id: str,
        event: str,
        *,
        world_name: str = "",
        entity_name: str = "",
    ) -> dict[str, Any]:
        session = self._require(session_id)
        normalized = str(event or "").strip().upper()
        if normalized in {"SESSION_READY", "RENDER_READY"}:
            session.state = "IN_WORLD"
        elif normalized == "PREVIEW_READY":
            session.state = "PREVIEW_READY"
        elif normalized == "SESSION_ERROR":
            session.state = "ERROR"
        session.last_command = normalized
        session.updated_at = time()
        return serving_result(
            "sessions.runtime_event",
            engine="godot",
            payload={
                "event": normalized,
                "world_name": world_name,
                "entity_name": entity_name,
                **session.to_dict(),
            },
        )

    def stop_session(self, session_id: str) -> dict[str, Any]:
        session = self._require(session_id)
        snapshot = session.to_dict()
        self._stop_process(session)
        session.state = "DESTROYED"
        with self._lock:
            self._sessions.pop(session_id, None)
        return serving_result(
            "sessions.stop",
            engine="godot",
            payload={"removed": True, "session": snapshot, **snapshot},
        )

    def debug(
        self,
        operation: str,
        payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = dict(payload or {})
        normalized = (
            str(operation or "").strip().lower().replace("/", "_").replace("-", "_")
        )
        session = next(iter(self._sessions.values()), None)
        if normalized == "viewer_config":
            return serving_result(
                "debug.viewer_config",
                engine="godot",
                payload={
                    "stream_url": session.stream_url if session else "",
                    "streaming_transport": "godot_web_http",
                    "input_transport": "browser_canvas",
                    "viewer_host": self.config.gateway_host,
                    "viewer_port": self.config.gateway_port,
                },
            )
        if normalized == "pixel_status":
            url = session.stream_url if session else ""
            reachable = False
            if url:
                try:
                    with urllib.request.urlopen(url, timeout=2.0) as response:
                        reachable = int(response.status) < 500
                except (urllib.error.URLError, TimeoutError, OSError):
                    reachable = False
            return serving_result(
                "debug.pixel_status",
                engine="godot",
                payload={
                    "reachable": reachable,
                    "stream_ready": reachable,
                    "url": url,
                    "message": "reachable" if reachable else "no active Godot Web page",
                    "transport": "godot_web_http",
                },
            )
        if normalized == "runtime_world_state":
            result = self._admin_client.runtime.sessions.snapshot(
                world_id=str(data.get("world_id") or "")
            )
            return self._translate("debug.runtime_world_state", result)
        return serving_result(
            f"debug.{normalized or 'unknown'}",
            engine="godot",
            ok=False,
            errors=[f"Unsupported Godot debug operation: {operation}"],
        )

    def _ensure_web_build(self, client: Any) -> Path:
        configured = self.config.godot_web_build
        project_root = self.config.godot_project
        if project_root is not None and project_root.name.lower() == "project.godot":
            project_root = project_root.parent
        root = configured or (
            project_root / "builds" / "web" if project_root is not None else None
        )
        if root is None:
            raise ValueError(
                "A3GAME_GODOT_WEB_BUILD or A3GAME_GODOT_PROJECT is required"
            )
        root = root.expanduser()
        if root.name.lower() == "index.html":
            root = root.parent
        if root.exists() or root.is_symlink():
            root = validate_web_tree(root)
        if (root / "index.html").is_file():
            return validate_web_root(root)
        result = client.build.project(
            preset=self.config.godot_web_preset,
            output_path=root / "index.html",
            allow_external_output=True,
        )
        if not result.get("ok"):
            raise RuntimeError("; ".join(_errors(result)) or "Godot Web export failed")
        return validate_web_root(root)

    def _start_server(self, root: Path, port: int) -> subprocess.Popen[Any]:
        root = validate_web_root(root)
        if not _port_free(self.config.pixel_host, port):
            raise OSError(
                f"Godot Web port is already in use: {self.config.pixel_host}:{port}"
            )
        return subprocess.Popen(
            [
                sys.executable,
                "-m",
                "engine_adapters.godot.web_server",
                "--root",
                str(root),
                "--host",
                self.config.pixel_host,
                "--port",
                str(port),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    def _allocate_port(self) -> tuple[int, int]:
        used = {item.web_port for item in self._sessions.values()}
        for slot in range(self.config.max_sessions):
            port = (
                self.config.base_pixel_http_port
                + slot * self.config.session_port_stride
            )
            if port not in used and (
                self.config.dry_run or _port_free(self.config.pixel_host, port)
            ):
                return slot, port
        raise RuntimeError("No free Godot browser serving session ports")

    def _wait_for_http(self, session: GodotBrowserSession) -> None:
        deadline = time() + self.config.pixel_start_timeout
        while time() < deadline:
            process = session.server_process
            if process is not None and process.poll() is not None:
                raise RuntimeError(
                    f"Godot Web server exited during startup (code {process.returncode})"
                )
            try:
                with urllib.request.urlopen(
                    session.stream_url, timeout=1.0
                ) as response:
                    if int(response.status) < 500:
                        return
            except (urllib.error.URLError, TimeoutError, OSError):
                sleep(0.05)
        raise TimeoutError(
            f"Timed out waiting for Godot Web page: {session.stream_url}"
        )

    def _stop_process(self, session: GodotBrowserSession) -> None:
        process = session.server_process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    def _require(self, session_id: str) -> GodotBrowserSession:
        try:
            return self._sessions[str(session_id)]
        except KeyError as exc:
            raise KeyError(f"Unknown browser session: {session_id}") from exc

    @staticmethod
    def _unsupported_web_control(
        operation: str,
        session: GodotBrowserSession,
        feature: str,
        details: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return serving_result(
            operation,
            engine="godot",
            ok=False,
            errors=[
                (
                    f"Godot Web does not support {feature} after export; configure "
                    "the project and export again"
                )
            ],
            payload={
                "supported": False,
                "delivery": "browser_canvas",
                **dict(details or {}),
                **session.to_dict(),
            },
        )

    @staticmethod
    def _translate(
        operation: str,
        result: Mapping[str, Any],
        asset_type: str = "",
    ) -> dict[str, Any]:
        value = dict(result)
        godot_payload = _payload(value)
        artifacts = [
            _asset(item, asset_type)
            for item in value.get("artifacts") or []
            if isinstance(item, Mapping)
        ]
        return serving_result(
            operation,
            engine="godot",
            ok=bool(value.get("ok", False)),
            payload={
                "godot_operation": value.get("operation", ""),
                "godot_payload": godot_payload,
                **godot_payload,
            },
            artifacts=artifacts,
            warnings=[str(item) for item in value.get("warnings") or []],
            errors=_errors(value),
        )


def create_godot_example_backend(
    config: BrowserServingConfig | None = None,
) -> GodotExampleBackend:
    return GodotExampleBackend(config or BrowserServingConfig.from_environment())
