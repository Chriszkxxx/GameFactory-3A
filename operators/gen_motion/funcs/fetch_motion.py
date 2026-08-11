"""
Bringing a clip in from somewhere other than the generator.

Text-to-motion is good at "a person walks forward and waves" and bad at
"a two-handed greatsword overhead slam with a recovery step". When the
generated clip is not good enough, the fix is not a better prompt — it is a
captured clip from a library, retargeted onto the same rig by the same code.
This module is the front door for that, and the retarget stage downstream does
not care which door the clip came through.

What it will and will not do
----------------------------
It will take a file you already have, prove it is usable, record where it came
from, and hand back the same shape ``generate_motion`` does — so the operator's
next step is identical either way.

It will **not** log into anything. Mixamo, MoCap Online and the rest gate
downloads behind an account and a licence you accept as a person, and a scraper
that pretends to be that person breaks the terms the asset is licensed under.
So sources are marked ``manual`` or ``direct``: ``manual`` sources produce an
error that tells you exactly what to click, and ``direct`` sources are fetched
over plain HTTPS. That line is a licensing decision, not a technical one.

Provenance is not optional
--------------------------
Every clip that lands writes a ``motion_source.json`` next to itself naming the
source, the licence, and the file it came from. A retargeted FBX is
indistinguishable from a generated one once it is in the output directory, and
"which of these can we actually ship" is a question that gets asked late, by
someone who was not here.

The units problem
-----------------
This is what actually breaks a downloaded clip. Mixamo exports centimetres, CMU
BVH is in inches, this repo's own generator is in metres — and a clip retargeted
at the wrong scale does not fail, it produces a character that moon-walks a
hundred metres per step, or vibrates in place. ``suggest_global_scale`` measures
both skeletons and reports the ratio instead of trusting the registry's
per-source default, because a library's nominal units and a given file's actual
units are not the same claim.
"""
from __future__ import annotations

import json
import shutil
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .retarget_utils.mapping_presets import (
    identify_motion_file,
    read_rig_joint_names,
)


#: Extensions the retarget stage can read. Anything else has to be converted
#: first — Blender will open a .blend or a .dae, but the retarget subprocess
#: takes an armature with one action and these are the two that guarantee it.
SUPPORTED_MOTION_FORMATS = (".bvh", ".fbx")

#: Refuse to stream more than this from a URL. A motion clip is kilobytes to a
#: few megabytes; a gigabyte means the URL points at a whole library archive,
#: and silently filling a disk is a worse outcome than a clear failure.
MAX_DOWNLOAD_BYTES = 512 * 1024 * 1024


@dataclass(frozen=True)
class MotionSource:
    """One external library, and the terms on which a clip leaves it."""

    name: str
    title: str
    url: str
    formats: tuple[str, ...]
    skeleton: str | None
    access: str
    licence: str
    nominal_units: str
    how_to_download: str
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "title": self.title,
            "url": self.url,
            "formats": list(self.formats),
            "skeleton": self.skeleton,
            "access": self.access,
            "licence": self.licence,
            "nominal_units": self.nominal_units,
            "how_to_download": self.how_to_download,
            "notes": list(self.notes),
        }


MOTION_SOURCES: dict[str, MotionSource] = {
    "mixamo": MotionSource(
        name="mixamo",
        title="Adobe Mixamo",
        url="https://www.mixamo.com/",
        formats=(".fbx",),
        skeleton="mixamo",
        access="manual",
        licence=(
            "Free with an Adobe account; royalty-free for use in your own "
            "projects. Redistributing the raw clips is not permitted, so keep "
            "downloads out of the repository."
        ),
        nominal_units="centimetres",
        how_to_download=(
            "Sign in at mixamo.com, pick an animation, press Download, and "
            "choose Format=FBX Binary, Skin='Without Skin', Frames per "
            "Second=30, Keyframe Reduction=none. Pass the saved .fbx as "
            "source_motion_path (or fetch_motion(source='mixamo', "
            "path=...))."
        ),
        notes=(
            "'Without Skin' gives the armature only, which is what "
            "retargeting wants and a tenth of the file size.",
            "In-place variants exist for locomotion clips; take them when the "
            "game drives movement itself and set in_place accordingly.",
        ),
    ),
    "mocap_online": MotionSource(
        name="mocap_online",
        title="MoCap Online",
        url="https://mocaponline.com/pages/free-animations",
        formats=(".fbx", ".bvh"),
        skeleton="ue5_mannequin",
        access="manual",
        licence=(
            "Free sample packs require checkout at zero cost; paid packs "
            "carry a commercial licence. Read the pack's own terms."
        ),
        nominal_units="centimetres",
        how_to_download=(
            "Add the free sample pack to the cart, complete the zero-cost "
            "checkout, download the FBX or BVH archive, then pass the "
            "archive with member='<clip>.fbx' or the extracted file."
        ),
        notes=(
            "Ships against the UE5 mannequin skeleton, so it retargets to a "
            "Puppeteer rig the same way any other humanoid does.",
        ),
    ),
    "cmu_bvh": MotionSource(
        name="cmu_bvh",
        title="CMU Graphics Lab Motion Capture Database (BVH conversion)",
        url="http://mocap.cs.cmu.edu/",
        formats=(".bvh",),
        skeleton="cmu_bvh",
        access="direct",
        licence=(
            "Free for all uses, including commercial; CMU asks for a credit. "
            "Created with funding from NSF EIA-0196217."
        ),
        nominal_units="inches",
        how_to_download=(
            "Fetched directly: pass url= pointing at a .bvh or a .zip plus "
            "member='<clip>.bvh'. Community mirrors of the BVH conversion "
            "are the usual host."
        ),
        notes=(
            "2500+ clips of very uneven quality — preview before committing "
            "one to a character.",
            "Carries helper bones (LHipJoint, LowerBack) that no anatomical "
            "slot maps to. Unmapped source bones are ignored, so this is "
            "harmless.",
        ),
    ),
    "bandai_namco": MotionSource(
        name="bandai_namco",
        title="Bandai Namco Research Motion Dataset",
        url=(
            "https://github.com/BandaiNamcoResearchInc/"
            "Bandai-Namco-Research-Motiondataset"
        ),
        formats=(".bvh",),
        skeleton=None,
        access="direct",
        licence=(
            "CC BY-NC-ND 4.0 — non-commercial, no derivatives. Usable for "
            "research and evaluation, not for a shipped game."
        ),
        nominal_units="centimetres",
        how_to_download=(
            "Fetched directly from the GitHub raw URL of a dataset .bvh."
        ),
        notes=(
            "Clips are labelled by style (elderly, tired, proud), which "
            "makes it a good source for evaluating style preservation.",
            "The no-derivatives clause covers retargeted output. Keep it out "
            "of anything shipped.",
        ),
    ),
    "local": MotionSource(
        name="local",
        title="A file you already have",
        url="",
        formats=SUPPORTED_MOTION_FORMATS,
        skeleton=None,
        access="manual",
        licence="Whatever the file came with — record it in the task.",
        nominal_units="unknown",
        how_to_download=(
            "Nothing to download; pass path= to a .bvh or .fbx on disk."
        ),
        notes=(
            "The escape hatch for a hand-authored clip or a library not "
            "listed here. Everything downstream behaves identically.",
        ),
    ),
}


def list_motion_sources() -> list[dict]:
    """Every known external library as plain data, for an agent or a CLI."""
    return [source.as_dict() for source in MOTION_SOURCES.values()]


def get_motion_source(name: str) -> MotionSource:
    """Look up one source, listing the alternatives on a miss."""
    try:
        return MOTION_SOURCES[str(name).lower()]
    except KeyError:
        available = ", ".join(sorted(MOTION_SOURCES))
        raise KeyError(
            f"Unknown motion source {name!r}. Known: {available}"
        ) from None


# ── acquisition ───────────────────────────────────────────────────────────────


def fetch_motion(
    *,
    source: str = "local",
    path: str | Path | None = None,
    url: str | None = None,
    member: str | None = None,
    dest_dir: str | Path,
    name: str | None = None,
) -> dict:
    """
    Put one external clip where the retarget stage can read it.

    Exactly one of ``path`` or ``url`` says where the clip comes from; the
    ``source`` names which library, which is what decides whether a URL may be
    fetched at all and what gets written into the provenance record.

    Args:
        source: A key of `MOTION_SOURCES`. ``local`` for a file with no
            library behind it.
        path: A ``.bvh``/``.fbx`` on disk, or a ``.zip`` holding one.
        url: An https URL to the same. Only for ``direct`` sources.
        member: Which file to take out of a zip. Optional when the archive
            holds exactly one usable clip.
        dest_dir: Where the clip and its provenance record land.
        name: Filename to save under; defaults to the source file's name.

    Returns:
        ``{"motion_path", "provenance_path", "source", "skeleton",
        "identified", "licence"}``.
    """
    library = get_motion_source(source)
    if bool(path) == bool(url):
        raise ValueError(
            "fetch_motion needs exactly one of path= or url=; got "
            f"path={path!r}, url={url!r}"
        )

    destination = Path(dest_dir)
    destination.mkdir(parents=True, exist_ok=True)

    if url:
        if library.access != "direct":
            raise PermissionError(_manual_source_message(library, url))
        origin = _download(url, destination / "_download")
    else:
        origin = Path(path).expanduser().resolve()
        if not origin.is_file() or origin.stat().st_size == 0:
            raise FileNotFoundError(f"Motion file is missing or empty: {origin}")

    clip = _extract_clip(origin, member, destination, name)
    identified = identify_motion_file(clip)
    provenance = _write_provenance(
        clip,
        library=library,
        origin=str(url or origin),
        member=member,
        identified=identified,
    )
    return {
        "motion_path": str(clip),
        "provenance_path": str(provenance),
        "source": library.name,
        "skeleton": identified.get("skeleton") or library.skeleton,
        "identified": identified,
        "licence": library.licence,
    }


def _manual_source_message(library: MotionSource, url: str) -> str:
    return (
        f"{library.title} does not allow automated downloads, so "
        f"fetch_motion will not request {url}. Its clips are licensed to a "
        "signed-in account, and fetching them with a script is a licence "
        "violation rather than a technical problem.\n\n"
        f"Download it by hand instead:\n  {library.how_to_download}\n\n"
        "Then pass the saved file as path=."
    )


def _download(url: str, into: Path) -> Path:
    """Fetch one https URL to disk, refusing anything unreasonable."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Only http(s) URLs can be fetched, got {url!r}")

    into.mkdir(parents=True, exist_ok=True)
    filename = Path(urllib.parse.unquote(parsed.path)).name or "download.bin"
    target = into / filename
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "AAAGameForge/gen_motion"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            declared = int(response.headers.get("Content-Length") or 0)
            if declared > MAX_DOWNLOAD_BYTES:
                raise ValueError(
                    f"{url} is {declared} bytes, over the "
                    f"{MAX_DOWNLOAD_BYTES} limit. Download the archive "
                    "yourself and pass path= with member=."
                )
            written = 0
            with open(target, "wb") as handle:
                while chunk := response.read(1 << 20):
                    written += len(chunk)
                    if written > MAX_DOWNLOAD_BYTES:
                        handle.close()
                        target.unlink(missing_ok=True)
                        raise ValueError(
                            f"{url} exceeded the {MAX_DOWNLOAD_BYTES} byte "
                            "download limit."
                        )
                    handle.write(chunk)
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not download {url}: {exc}") from exc
    if target.stat().st_size == 0:
        raise RuntimeError(f"{url} returned an empty file.")
    return target


def _extract_clip(
    origin: Path,
    member: str | None,
    destination: Path,
    name: str | None,
) -> Path:
    """Resolve a file or an archive down to one clip in ``destination``."""
    if origin.suffix.lower() == ".zip":
        source_name, payload = _read_zip_member(origin, member)
        clip = destination / (name or Path(source_name).name)
        clip.write_bytes(payload)
    else:
        _validate_motion_suffix(origin)
        clip = destination / (name or origin.name)
        if origin.resolve() != clip.resolve():
            shutil.copyfile(origin, clip)
    _validate_motion_suffix(clip)
    if clip.stat().st_size == 0:
        raise RuntimeError(f"Extracted an empty motion clip: {clip}")
    return clip


def _read_zip_member(archive: Path, member: str | None) -> tuple[str, bytes]:
    with zipfile.ZipFile(archive) as bundle:
        candidates = [
            info.filename
            for info in bundle.infolist()
            if not info.is_dir()
            and Path(info.filename).suffix.lower() in SUPPORTED_MOTION_FORMATS
        ]
        if member:
            matches = [
                item
                for item in candidates
                if item == member or Path(item).name == member
            ]
            if not matches:
                raise KeyError(
                    f"{member!r} is not a motion clip inside {archive.name}. "
                    f"It holds {len(candidates)}: {candidates[:8]}"
                )
            chosen = matches[0]
        elif len(candidates) == 1:
            chosen = candidates[0]
        elif not candidates:
            raise ValueError(
                f"{archive.name} contains no .bvh or .fbx clip."
            )
        else:
            raise ValueError(
                f"{archive.name} holds {len(candidates)} clips; pass "
                f"member= to choose one. First few: {candidates[:8]}"
            )
        return chosen, bundle.read(chosen)


def _validate_motion_suffix(path: Path) -> None:
    if path.suffix.lower() not in SUPPORTED_MOTION_FORMATS:
        raise ValueError(
            "Motion clips must be "
            f"{' or '.join(SUPPORTED_MOTION_FORMATS)}, got {path.name}"
        )


def _write_provenance(
    clip: Path,
    *,
    library: MotionSource,
    origin: str,
    member: str | None,
    identified: dict,
) -> Path:
    record = {
        "clip": str(clip),
        "source": library.name,
        "source_title": library.title,
        "source_url": library.url,
        "licence": library.licence,
        "origin": origin,
        "archive_member": member,
        "nominal_units": library.nominal_units,
        "declared_skeleton": library.skeleton,
        "identified_skeleton": identified.get("skeleton"),
        "identification_confidence": identified.get("confidence"),
        "notes": list(library.notes),
    }
    path = clip.with_name(f"{clip.stem}_motion_source.json")
    path.write_text(
        json.dumps(record, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


# ── units ─────────────────────────────────────────────────────────────────────


def measure_bvh_extent(bvh_path: str | Path) -> float:
    """
    Height of a BVH's rest pose, in whatever units the file is written in.

    Walks the hierarchy accumulating OFFSET vectors, so this is the rest-pose
    joint cloud rather than the animation — cheap, and the only part of the
    file that describes the skeleton's proportions. Returns the vertical
    extent; BVH is Y-up by convention and every library here follows it.
    """
    positions: list[tuple[float, float, float]] = []
    stack: list[tuple[float, float, float]] = []
    current = (0.0, 0.0, 0.0)
    pending = False

    with open(bvh_path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            token = line.split()
            if not token:
                continue
            head = token[0].upper()
            if head == "MOTION":
                break
            if head in {"ROOT", "JOINT", "END"}:
                pending = True
            elif head == "OFFSET" and len(token) >= 4:
                offset = tuple(float(value) for value in token[1:4])
                if pending:
                    current = tuple(
                        base + delta for base, delta in zip(current, offset)
                    )
                    positions.append(current)  # type: ignore[arg-type]
                    pending = False
            elif head == "{":
                stack.append(current)
            elif head == "}":
                current = stack.pop() if stack else (0.0, 0.0, 0.0)
    if not positions:
        return 0.0
    heights = [position[1] for position in positions]
    return max(heights) - min(heights)


def measure_rig_extent(rig_path: str | Path) -> float:
    """Height of a Puppeteer rig's joint cloud, in metres."""
    heights = []
    with open(rig_path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            token = line.split()
            if len(token) >= 5 and token[0] == "joints":
                heights.append(float(token[4]))
    return max(heights) - min(heights) if heights else 0.0


def suggest_global_scale(
    motion_path: str | Path,
    rig_path: str | Path,
) -> dict:
    """
    Measure both skeletons and report the scale that makes them agree.

    This is the single most common failure of an imported clip, and the one
    that is hardest to read from the output: at the wrong scale the pose is
    still correct, so the character animates properly while travelling a
    hundred metres a step — or not moving at all.

    Only the root *translation* is affected. World-delta retargeting transfers
    rotations, which are scale-free, so a wrong scale never breaks the pose
    itself. That is precisely why it survives review.

    Returns a suggestion, not a setting: ``ratio`` is measured, ``confident``
    says whether both measurements were usable, and an FBX source cannot be
    measured here at all — the registry's ``nominal_units`` is the fallback
    for those (Mixamo centimetres against a metre rig means 0.01).
    """
    motion = Path(motion_path)
    rig_extent = measure_rig_extent(rig_path)
    joint_count = len(read_rig_joint_names(rig_path))

    if motion.suffix.lower() != ".bvh":
        return {
            "suggested_global_scale": None,
            "confident": False,
            "motion_extent": None,
            "rig_extent": rig_extent or None,
            "rig_joint_count": joint_count,
            "reason": (
                "Only BVH can be measured without Blender. For FBX, start "
                "from the source's nominal units (Mixamo exports "
                "centimetres, so 0.01 against a metre-scale rig) and check "
                "the retargeted root travel."
            ),
        }

    motion_extent = measure_bvh_extent(motion)
    if motion_extent <= 1e-6 or rig_extent <= 1e-6:
        return {
            "suggested_global_scale": None,
            "confident": False,
            "motion_extent": motion_extent or None,
            "rig_extent": rig_extent or None,
            "rig_joint_count": joint_count,
            "reason": (
                "One of the two skeletons measured as flat, so the ratio "
                "would be meaningless. Retarget at 1.0 and inspect."
            ),
        }

    ratio = rig_extent / motion_extent
    return {
        "suggested_global_scale": round(ratio, 6),
        "confident": True,
        "motion_extent": round(motion_extent, 6),
        "rig_extent": round(rig_extent, 6),
        "rig_joint_count": joint_count,
        "reason": (
            f"Rest-pose height {motion_extent:.4g} in the clip against "
            f"{rig_extent:.4g} m in the rig."
        ),
    }


__all__ = [
    "MAX_DOWNLOAD_BYTES",
    "MOTION_SOURCES",
    "MotionSource",
    "SUPPORTED_MOTION_FORMATS",
    "fetch_motion",
    "get_motion_source",
    "list_motion_sources",
    "measure_bvh_extent",
    "measure_rig_extent",
    "suggest_global_scale",
]
