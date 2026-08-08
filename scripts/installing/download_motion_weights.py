"""Safely download only the Puppeteer and HumanML3D weights used by AAAGF.

Unlike MoMask's upstream ``download_models.sh``, this script never deletes an
existing checkpoints directory and never downloads KIT-ML/evaluator/GloVe data.
"""
from __future__ import annotations

import argparse
import os
import time
import zipfile
from pathlib import Path


PUPPETEER_FILES = (
    (
        "facebook/opt-350m",
        "config.json",
        "skeleton/third_partys/opt-350m",
    ),
    (
        "Maikou/Michelangelo",
        "checkpoints/aligned_shape_latents/shapevae-256.ckpt",
        "skeleton/third_partys/Michelangelo",
    ),
    (
        "Seed3D/Puppeteer",
        "skeleton_ckpts/puppeteer_skeleton_w_diverse_pose.pth",
        "skeleton",
    ),
    (
        "mikaelaangel/partfield-ckpt",
        "model_objaverse.ckpt",
        "skinning/third_partys/PartField/ckpt",
    ),
    (
        "Seed3D/Puppeteer",
        "skinning_ckpts/puppeteer_skin_w_diverse_pose_depth1.pth",
        "skinning",
    ),
)
MOMASK_HUMANML3D_FILE_ID = "1vXS7SHJBgWPt59wupQ5UUzhFObrnGkQ0"
MOMASK_HUMANML3D_URL = (
    "https://drive.usercontent.google.com/download"
    f"?id={MOMASK_HUMANML3D_FILE_ID}&export=download&confirm=t"
)


def _safe_extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    destination_root = destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for item in bundle.infolist():
            target = (destination / item.filename).resolve()
            if destination_root not in target.parents and target != destination_root:
                raise RuntimeError(
                    f"Unsafe path in MoMask archive: {item.filename}"
                )
        bundle.extractall(destination)


def _download_puppeteer(source: Path) -> None:
    from huggingface_hub import hf_hub_download

    for repo_id, filename, relative_root in PUPPETEER_FILES:
        local_dir = source / relative_root
        local_dir.mkdir(parents=True, exist_ok=True)
        print(f"[weights] {repo_id}/{filename}")
        hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=local_dir,
        )


def _download_momask(source: Path, cache: Path) -> None:
    import requests

    archive = cache / "momask_humanml3d_models.zip"
    if not archive.is_file() or archive.stat().st_size == 0:
        archive.parent.mkdir(parents=True, exist_ok=True)
        partial = archive.with_suffix(".zip.partial")
        print("[weights] MoMask HumanML3D archive")
        for attempt in range(1, 6):
            try:
                if partial.is_file() and zipfile.is_zipfile(partial):
                    break
                offset = partial.stat().st_size if partial.is_file() else 0
                headers = {"Range": f"bytes={offset}-"} if offset else {}
                with requests.get(
                    MOMASK_HUMANML3D_URL,
                    headers=headers,
                    stream=True,
                    timeout=(30, 120),
                ) as response:
                    if response.status_code not in (200, 206):
                        response.raise_for_status()
                        raise RuntimeError(
                            f"unexpected HTTP status {response.status_code}"
                        )
                    append = bool(offset and response.status_code == 206)
                    if not append:
                        offset = 0
                    expected = int(response.headers.get("Content-Length", "0"))
                    expected = offset + expected if expected else 0
                    written = offset
                    with partial.open("ab" if append else "wb") as handle:
                        for chunk in response.iter_content(chunk_size=8 * 1024 * 1024):
                            if not chunk:
                                continue
                            handle.write(chunk)
                            written += len(chunk)
                    print(
                        f"[weights] MoMask archive received {written} bytes"
                        + (f" / {expected}" if expected else ""),
                        flush=True,
                    )
                if zipfile.is_zipfile(partial):
                    break
                raise RuntimeError("downloaded file is not a valid ZIP")
            except Exception as exc:
                if attempt == 5:
                    raise RuntimeError(
                        "MoMask HumanML3D download did not complete after "
                        f"{attempt} attempts. Partial file: {partial}"
                    ) from exc
                delay = 3 * attempt
                print(
                    f"[weights] MoMask download attempt {attempt}/5 failed: "
                    f"{exc}; retrying in {delay}s"
                )
                time.sleep(delay)
        partial.replace(archive)

    destination = source / "checkpoints" / "t2m"
    print(f"[weights] extracting HumanML3D models -> {destination}")
    _safe_extract(archive, destination)


def _link_michelangelo(puppeteer: Path) -> None:
    target = puppeteer / "skinning" / "third_partys" / "Michelangelo"
    source = puppeteer / "skeleton" / "third_partys" / "Michelangelo"
    if target.exists() or target.is_symlink():
        return
    try:
        target.symlink_to(source, target_is_directory=True)
    except OSError as exc:
        raise RuntimeError(
            "Could not create the shared Michelangelo symlink. Run this "
            "download script inside WSL, not Windows."
        ) from exc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime-root",
        default=os.environ.get(
            "AAAGF_RUNTIME_ROOT",
            "/mnt/e/Research/WorldModel/DCAI/AAAGameForge_runtime",
        ),
    )
    parser.add_argument(
        "--skip-puppeteer",
        action="store_true",
    )
    parser.add_argument("--skip-momask", action="store_true")
    args = parser.parse_args()

    root = Path(args.runtime_root).expanduser().resolve()
    puppeteer = root / "sources" / "Puppeteer"
    momask = root / "sources" / "momask-codes"
    if not args.skip_puppeteer:
        _download_puppeteer(puppeteer)
        _link_michelangelo(puppeteer)
    if not args.skip_momask:
        _download_momask(momask, root / "cache")

    required = (
        puppeteer
        / "skeleton"
        / "third_partys"
        / "opt-350m"
        / "config.json",
        puppeteer
        / "skeleton"
        / "skeleton_ckpts"
        / "puppeteer_skeleton_w_diverse_pose.pth",
        puppeteer
        / "skinning"
        / "skinning_ckpts"
        / "puppeteer_skin_w_diverse_pose_depth1.pth",
        puppeteer
        / "skeleton"
        / "third_partys"
        / "Michelangelo"
        / "checkpoints"
        / "aligned_shape_latents"
        / "shapevae-256.ckpt",
        puppeteer
        / "skinning"
        / "third_partys"
        / "PartField"
        / "ckpt"
        / "model_objaverse.ckpt",
        momask
        / "checkpoints"
        / "t2m"
        / "t2m_nlayer8_nhead6_ld384_ff1024_cdp0.1_rvq6ns"
        / "model"
        / "latest.tar",
        momask
        / "checkpoints"
        / "t2m"
        / "tres_nlayer8_ld384_ff1024_rvq6ns_cdp0.2_sw"
        / "model"
        / "net_best_fid.tar",
        momask
        / "checkpoints"
        / "t2m"
        / "rvq_nq6_dc512_nc512_noshare_qdp0.2"
        / "model"
        / "net_best_fid.tar",
        momask
        / "checkpoints"
        / "t2m"
        / "length_estimator"
        / "model"
        / "finest.tar",
    )
    missing = [
        str(path)
        for path in required
        if not path.is_file() or path.stat().st_size == 0
    ]
    if missing:
        raise RuntimeError("Required outputs are missing:\n  - " + "\n  - ".join(missing))
    print("[weights] selected motion weights are ready")


if __name__ == "__main__":
    main()
