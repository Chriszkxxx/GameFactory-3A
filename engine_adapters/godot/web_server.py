"""Static HTTP server with the isolation headers Godot Web exports need."""

from __future__ import annotations

import argparse
import datetime
import email.utils
import errno
import os
import stat
import urllib.parse
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ._internal import validate_regular_directory_tree


class UnsafeGodotWebPathError(PermissionError):
    """A request attempted to traverse an unsafe Web export path."""


_DIRECTORY_DESCRIPTOR_OPEN_SUPPORTED = (
    os.open in os.supports_dir_fd
    and hasattr(os, "O_DIRECTORY")
    and hasattr(os, "O_NOFOLLOW")
)
_BASE_OPEN_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_BINARY", 0)
    | getattr(os, "O_CLOEXEC", 0)
    | getattr(os, "O_NONBLOCK", 0)
)
_UNSAFE_OPEN_ERRNOS = {
    errno.EACCES,
    errno.ELOOP,
    errno.ENOTDIR,
    errno.EPERM,
}


def _absolute_without_resolving(path: Path) -> Path:
    """Make a path absolute while retaining link components for validation."""

    return Path(os.path.abspath(str(path.expanduser())))


def validate_web_tree(root: Path) -> Path:
    """Validate and return a canonical tree containing only regular nodes."""

    lexical_root = _absolute_without_resolving(Path(root))
    validate_regular_directory_tree(
        lexical_root,
        label="Godot Web export",
    )
    return lexical_root.resolve(strict=True)


def validate_web_root(root: Path) -> Path:
    """Validate and return a canonical, link-free Godot Web export root."""

    validated_root = validate_web_tree(root)
    index = validated_root / "index.html"
    try:
        index_mode = index.lstat().st_mode
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Godot Web export has no index.html: {validated_root}"
        ) from exc
    if not stat.S_ISREG(index_mode):
        raise ValueError(f"Godot Web export index must be a regular file: {index}")
    return validated_root


def _validate_request_target(root: Path, target: Path) -> None:
    """Reject request targets that escape the root or traverse unsafe nodes."""

    try:
        root_mode = root.lstat().st_mode
    except OSError as exc:
        raise UnsafeGodotWebPathError("Godot Web root is unavailable") from exc
    if stat.S_ISLNK(root_mode) or not stat.S_ISDIR(root_mode):
        raise UnsafeGodotWebPathError("Godot Web root is not a regular directory")

    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        raise UnsafeGodotWebPathError("Godot Web request escaped its root") from exc

    current = root
    for part in relative.parts:
        current /= part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            break
        except (OSError, ValueError) as exc:
            raise UnsafeGodotWebPathError(
                "Godot Web request path could not be validated"
            ) from exc
        if stat.S_ISLNK(mode):
            raise UnsafeGodotWebPathError(
                "Godot Web requests must not traverse symbolic links"
            )
        if current == target:
            if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                raise UnsafeGodotWebPathError(
                    "Godot Web requests require a regular file or directory"
                )
        elif not stat.S_ISDIR(mode):
            raise UnsafeGodotWebPathError(
                "Godot Web request parent is not a regular directory"
            )

    try:
        resolved = target.resolve(strict=False)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise UnsafeGodotWebPathError(
            "Godot Web request resolved outside its root"
        ) from exc


def _open_web_root_descriptor(root: Path) -> int | None:
    """Pin the validated Web root so later path replacements cannot redirect it."""

    if not _DIRECTORY_DESCRIPTOR_OPEN_SUPPORTED:
        return None
    if not root.is_absolute():
        raise UnsafeGodotWebPathError("Godot Web root must be absolute")
    flags = _BASE_OPEN_FLAGS | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor: int | None = None
    try:
        descriptor = os.open(root.anchor, flags)
        for part in root.parts[1:]:
            next_descriptor = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
    except OSError as exc:
        if descriptor is not None:
            os.close(descriptor)
        if exc.errno in _UNSAFE_OPEN_ERRNOS:
            raise UnsafeGodotWebPathError(
                "Godot Web root could not be opened safely"
            ) from exc
        raise
    if descriptor is None:  # pragma: no cover - every absolute path has an anchor
        raise UnsafeGodotWebPathError("Godot Web root could not be opened safely")
    try:
        opened = os.fstat(descriptor)
        current = root.stat(follow_symlinks=False)
        if not stat.S_ISDIR(opened.st_mode) or not os.path.samestat(opened, current):
            raise UnsafeGodotWebPathError(
                "Godot Web root changed while it was being opened"
            )
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _open_from_root_descriptor(
    root_descriptor: int,
    relative_parts: tuple[str, ...],
) -> tuple[int, os.stat_result]:
    """Open one node beneath a pinned root without following path-component links."""

    descriptor = os.dup(root_descriptor)
    try:
        for index, part in enumerate(relative_parts):
            flags = _BASE_OPEN_FLAGS | os.O_NOFOLLOW
            if index < len(relative_parts) - 1:
                flags |= os.O_DIRECTORY
            next_descriptor = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        opened = os.fstat(descriptor)
        if not (stat.S_ISREG(opened.st_mode) or stat.S_ISDIR(opened.st_mode)):
            raise UnsafeGodotWebPathError(
                "Godot Web requests require a regular file or directory"
            )
        return descriptor, opened
    except OSError as exc:
        os.close(descriptor)
        if exc.errno in _UNSAFE_OPEN_ERRNOS:
            raise UnsafeGodotWebPathError(
                "Godot Web request path changed or contains a symbolic link"
            ) from exc
        raise
    except BaseException:
        os.close(descriptor)
        raise


def _open_and_verify_by_path(
    root: Path, target: Path
) -> tuple[int | None, os.stat_result]:
    """Portable fallback that verifies the exact node bound to an opened handle."""

    try:
        descriptor = os.open(target, _BASE_OPEN_FLAGS)
    except OSError:
        # Some platforms do not allow directory handles through os.open().
        # Directories are never returned as response bodies; their index file is
        # opened and verified independently below.
        current = target.stat(follow_symlinks=False)
        if not stat.S_ISDIR(current.st_mode):
            raise
        _validate_request_target(root, target)
        confirmed = target.stat(follow_symlinks=False)
        if not os.path.samestat(current, confirmed):
            raise UnsafeGodotWebPathError(
                "Godot Web request directory changed while it was being checked"
            )
        return None, confirmed

    try:
        opened = os.fstat(descriptor)
        if not (stat.S_ISREG(opened.st_mode) or stat.S_ISDIR(opened.st_mode)):
            raise UnsafeGodotWebPathError(
                "Godot Web requests require a regular file or directory"
            )
        _validate_request_target(root, target)
        resolved = target.resolve(strict=True)
        resolved.relative_to(root)
        current = target.stat(follow_symlinks=False)
        if not os.path.samestat(opened, current):
            raise UnsafeGodotWebPathError(
                "Godot Web request path changed while it was being opened"
            )
        return descriptor, opened
    except (OSError, ValueError) as exc:
        os.close(descriptor)
        if isinstance(exc, UnsafeGodotWebPathError):
            raise
        raise UnsafeGodotWebPathError(
            "Godot Web request could not be verified after opening"
        ) from exc
    except BaseException:
        os.close(descriptor)
        raise


def _open_request_target(
    root: Path,
    target: Path,
    root_descriptor: int | None,
) -> tuple[int | None, os.stat_result]:
    """Validate and open a request target as one safe operation."""

    _validate_request_target(root, target)
    try:
        relative = target.relative_to(root)
    except ValueError as exc:
        raise UnsafeGodotWebPathError("Godot Web request escaped its root") from exc
    if root_descriptor is not None:
        return _open_from_root_descriptor(root_descriptor, relative.parts)
    return _open_and_verify_by_path(root, target)


class GodotWebHandler(SimpleHTTPRequestHandler):
    def __init__(
        self,
        *args,
        directory: str | None = None,
        root_descriptor: int | None = None,
        **kwargs,
    ) -> None:
        self._root_descriptor = root_descriptor
        super().__init__(*args, directory=directory, **kwargs)

    def send_head(self):
        """Open and serve a file without a validation-to-open path race."""

        root = Path(self.directory)
        target = Path(super().translate_path(self.path))
        descriptor: int | None = None
        try:
            descriptor, opened = _open_request_target(
                root,
                target,
                self._root_descriptor,
            )
        except UnsafeGodotWebPathError:
            self.send_error(HTTPStatus.FORBIDDEN, "Unsafe Godot Web path")
            return None
        except (OSError, ValueError):
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return None

        request_parts = urllib.parse.urlsplit(self.path)
        if stat.S_ISDIR(opened.st_mode):
            if descriptor is not None:
                os.close(descriptor)
                descriptor = None
            if not request_parts.path.endswith("/"):
                self.send_response(HTTPStatus.MOVED_PERMANENTLY)
                redirected = (
                    request_parts[0],
                    request_parts[1],
                    request_parts[2] + "/",
                    request_parts[3],
                    request_parts[4],
                )
                self.send_header("Location", urllib.parse.urlunsplit(redirected))
                self.send_header("Content-Length", "0")
                self.end_headers()
                return None
            for name in ("index.html", "index.htm"):
                candidate = target / name
                try:
                    candidate_descriptor, candidate_stat = _open_request_target(
                        root,
                        candidate,
                        self._root_descriptor,
                    )
                except FileNotFoundError:
                    continue
                except UnsafeGodotWebPathError:
                    self.send_error(HTTPStatus.FORBIDDEN, "Unsafe Godot Web path")
                    return None
                except (OSError, ValueError):
                    continue
                if stat.S_ISREG(candidate_stat.st_mode):
                    descriptor = candidate_descriptor
                    opened = candidate_stat
                    target = candidate
                    break
                if candidate_descriptor is not None:
                    os.close(candidate_descriptor)
            else:
                return self.list_directory(str(target))
        elif request_parts.path.endswith("/"):
            if descriptor is not None:
                os.close(descriptor)
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return None

        if descriptor is None:
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return None
        response_file = os.fdopen(descriptor, "rb")
        try:
            if (
                "If-Modified-Since" in self.headers
                and "If-None-Match" not in self.headers
            ):
                try:
                    modified_since = email.utils.parsedate_to_datetime(
                        self.headers["If-Modified-Since"]
                    )
                except (TypeError, IndexError, OverflowError, ValueError):
                    pass
                else:
                    if modified_since.tzinfo is None:
                        modified_since = modified_since.replace(
                            tzinfo=datetime.timezone.utc
                        )
                    if modified_since.tzinfo is datetime.timezone.utc:
                        last_modified = datetime.datetime.fromtimestamp(
                            opened.st_mtime,
                            datetime.timezone.utc,
                        ).replace(microsecond=0)
                        if last_modified <= modified_since:
                            self.send_response(HTTPStatus.NOT_MODIFIED)
                            self.end_headers()
                            response_file.close()
                            return None

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-type", self.guess_type(str(target)))
            self.send_header("Content-Length", str(opened.st_size))
            self.send_header("Last-Modified", self.date_time_string(opened.st_mtime))
            self.end_headers()
            return response_file
        except BaseException:
            response_file.close()
            raise

    def list_directory(self, path: str):
        self.send_error(HTTPStatus.NOT_FOUND, "Directory listing is disabled")

    def end_headers(self) -> None:
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cross-Origin-Resource-Policy", "cross-origin")
        super().end_headers()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args(argv)
    root = validate_web_root(Path(args.root))
    root_descriptor = _open_web_root_descriptor(root)
    try:
        handler = partial(
            GodotWebHandler,
            directory=str(root),
            root_descriptor=root_descriptor,
        )
        server = ThreadingHTTPServer((args.host, args.port), handler)
        try:
            server.serve_forever()
        finally:
            server.server_close()
    finally:
        if root_descriptor is not None:
            os.close(root_descriptor)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
