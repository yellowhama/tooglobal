#!/usr/bin/env python3
"""Stage-sequential storyboard/panel generator — manifest-driven.

Stages:
  1) Composition/layout (Depth ControlNet only, reference screenshot)
  2) Character (Stage1 output as ControlNet ref + Golden shot via IP-Adapter)
  2.5) Optional Kontext refinement (Stage2 consistency/detail cleanup)
  3) Upscale (AnimeSharp 4x -> 1920x1080, no cropping)

Usage:
  python pipeline/stage1_visuals/generate_panels_3stage.py --manifest episodes/ep01/manifest.json
  python pipeline/stage1_visuals/generate_panels_3stage.py --manifest episodes/ep01/manifest.json --stage 1
  python pipeline/stage1_visuals/generate_panels_3stage.py --manifest episodes/ep01/manifest.json --shot s001
  python pipeline/stage1_visuals/generate_panels_3stage.py --manifest episodes/ep01/manifest.json --resume

Notes:
  - 병렬 실행 금지: Stage1이 끝나고 GPU가 비는 걸 확인한 뒤 Stage2를 돌려야 함.
  - 이 러너는 의도적으로 단일 프로세스 + stage-sequential(pass) 방식으로만 동작한다.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "pipeline" / "shared"))

from comfyui_client import ComfyUIClient, load_workflow  # noqa: E402
from project_paths import get_screenshot_root  # noqa: E402
from scene_cluster import search_scenes  # noqa: E402


STAGE1_WORKFLOW_PATH = PROJECT_ROOT / "workflows" / "stage1_composition.json"
STAGE2_WORKFLOW_PATH = PROJECT_ROOT / "workflows" / "stage2_character.json"
STAGE25_WORKFLOW_PATH = PROJECT_ROOT / "workflows" / "stage2_5_kontext.json"
STAGE3_WORKFLOW_PATH = PROJECT_ROOT / "workflows" / "stage3_upscale.json"

CHAR_DIR = PROJECT_ROOT / "assets" / "characters"
SCREENSHOT_ROOT = get_screenshot_root()


@dataclass(frozen=True)
class CutItem:
    shot_id: str
    data: dict
    parent_type: str


def _stable_seed(shot_id: str, stage: int) -> int:
    """Deterministic seed per shot+stage for reproducibility."""
    h = hashlib.md5(f"{shot_id}|stage{stage}".encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _ensure_blank_white(project_root: Path) -> Path:
    blank = project_root / "assets" / "system" / "blank_white.png"
    if blank.exists():
        return blank
    blank.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image
        Image.new("RGB", (1024, 1024), (255, 255, 255)).save(blank)
    except Exception:
        # If PIL isn't available for some reason, keep failing loudly later.
        raise RuntimeError("blank_white.png is missing and PIL is unavailable to create it")
    return blank


def _find_golden_shot(characters: list[str]) -> Path | None:
    for c in characters:
        g = CHAR_DIR / c / f"{c}_golden.png"
        if g.exists():
            return g
    return None


def _infer_characters_for_cut(cut: dict) -> list[str]:
    chars = cut.get("characters")
    if isinstance(chars, list) and chars:
        return [c for c in chars if c and c != "narrator"]
    speaker = cut.get("speaker")
    if speaker and speaker != "narrator":
        return [speaker]
    parent_chars = cut.get("_parent_characters") or []
    if isinstance(parent_chars, list) and parent_chars:
        return [c for c in parent_chars if c and c != "narrator"]
    return []


def _pick_reference_screenshot(cut: dict, parent_type: str) -> Path | None:
    """Best-effort reference selection.

    Priority:
      1) Use manifest-provided storyboard_reference if present.
      2) Use scene_cluster search by cut meta.
    """
    # 1) manifest-provided reference
    ref = cut.get("storyboard_reference") or {}
    frame_file = ref.get("frame_file")
    if frame_file:
        full = SCREENSHOT_ROOT / frame_file
        if full.exists():
            return full

    # 2) scene cluster search
    shot_size = (cut.get("shot_size") or "ms").lower()
    mood = (cut.get("mood") or "neutral").lower()
    situation = cut.get("situation")
    composition = cut.get("composition")
    angle = cut.get("angle")

    result = search_scenes(
        shot_size=shot_size,
        mood=mood if mood != "neutral" else None,
        situation=situation,
        composition=composition,
        angle=angle,
        scene_type=parent_type,
        preferred_shows=["psg_2010", "psg_new", "nichijou"],
        limit=3,
    )
    scenes = result.get("results") or []
    if scenes:
        ff = scenes[0].get("representative_frame")
        if ff:
            full = SCREENSHOT_ROOT / ff
            if full.exists():
                return full

    return None


def _iter_cuts(manifest: dict) -> list[CutItem]:
    """Flatten scenes -> cuts when needed, similar to generate_storyboard_full.py."""
    shots = manifest.get("shots") or []
    has_cuts = any(isinstance(s.get("cuts"), list) and s.get("cuts") for s in shots)

    cuts: list[CutItem] = []
    if has_cuts:
        for shot in shots:
            parent_type = shot.get("type", "SKIT")
            parent_chars = shot.get("characters", [])
            for cut in (shot.get("cuts") or []):
                if cut.get("cut_type") == "text_overlay":
                    continue
                data = dict(cut)
                data["_parent_characters"] = parent_chars
                sid = data.get("cut_id") or shot.get("shot_id")
                if not sid:
                    continue
                cuts.append(CutItem(shot_id=sid, data=data, parent_type=parent_type))
    else:
        for shot in shots:
            sid = shot.get("shot_id")
            if not sid:
                continue
            cuts.append(CutItem(shot_id=sid, data=shot, parent_type=shot.get("type", "SKIT")))
    return cuts


def _require_file(path: Path, what: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing {what}: {path}")


def _write_image_bytes(dst: Path, data: bytes) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(dst)


def _render_stage(
    *,
    client: ComfyUIClient,
    workflow: dict,
    overrides: dict,
    timeout_s: int,
) -> bytes:
    pid = client.queue_workflow(workflow, overrides=overrides)
    result = client.wait_for_completion(pid, timeout=timeout_s, poll_interval=5.0)
    images = result.get("images") or []
    if not images:
        raise RuntimeError("ComfyUI returned no images")
    return client.get_image(images[0])


@contextlib.contextmanager
def _exclusive_lock(lock_path: Path):
    """Prevent concurrent runs that would overload the GPU/ComfyUI queue."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w", encoding="utf-8") as f:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(f"Another run is already active (lock): {lock_path}")
        f.write(f"pid={os.getpid()}\n")
        f.flush()
        yield


def _stage1_pass(
    *,
    cuts: list[CutItem],
    client: ComfyUIClient,
    wf1: dict,
    stage1_dir: Path,
    blank: Path,
    timeout_s: int,
    resume: bool,
) -> tuple[int, int, int]:
    ok = skip = fail = 0
    for i, cut in enumerate(cuts, start=1):
        sid = cut.shot_id
        parent_type = (cut.parent_type or "SKIT").upper()
        prompt = cut.data.get("compiled_prompt")
        if not prompt:
            print(f"[S1 {i}/{len(cuts)}] {sid} SKIP (no compiled_prompt)")
            skip += 1
            continue
        out_path = stage1_dir / f"{sid}_layout.png"
        if resume and out_path.exists():
            print(f"[S1 {i}/{len(cuts)}] {sid} SKIP (exists)")
            skip += 1
            continue
        try:
            ref = _pick_reference_screenshot(cut.data, parent_type) or blank
            ref_upload = client.upload_image(str(ref))
            overrides = {
                "Load Reference Screenshot": {"image": ref_upload["name"]},
                "Positive Prompt": {"text": prompt},
                "Random Noise": {"noise_seed": _stable_seed(sid, 1)},
            }
            t0 = time.time()
            img = _render_stage(client=client, workflow=wf1, overrides=overrides, timeout_s=timeout_s)
            _write_image_bytes(out_path, img)
            print(f"[S1 {i}/{len(cuts)}] {sid} OK ({time.time()-t0:.0f}s)")
            ok += 1
        except Exception as e:
            msg = str(e).replace("\n", " ")
            print(f"[S1 {i}/{len(cuts)}] {sid} ERROR: {msg[:240]}")
            fail += 1
    return ok, skip, fail


def _stage2_pass(
    *,
    cuts: list[CutItem],
    client: ComfyUIClient,
    wf2: dict,
    stage1_dir: Path,
    stage2_dir: Path,
    blank: Path,
    timeout_s: int,
    resume: bool,
) -> tuple[int, int, int]:
    ok = skip = fail = 0
    for i, cut in enumerate(cuts, start=1):
        sid = cut.shot_id
        prompt = cut.data.get("compiled_prompt")
        if not prompt:
            print(f"[S2 {i}/{len(cuts)}] {sid} SKIP (no compiled_prompt)")
            skip += 1
            continue
        in_path = stage1_dir / f"{sid}_layout.png"
        out_path = stage2_dir / f"{sid}_char.png"
        if not in_path.exists():
            print(f"[S2 {i}/{len(cuts)}] {sid} SKIP (missing Stage1: {in_path.name})")
            skip += 1
            continue
        if resume and out_path.exists():
            print(f"[S2 {i}/{len(cuts)}] {sid} SKIP (exists)")
            skip += 1
            continue
        try:
            chars = _infer_characters_for_cut(cut.data)
            golden = _find_golden_shot(chars) or blank
            ref_upload = client.upload_image(str(in_path))
            golden_upload = client.upload_image(str(golden))
            overrides = {
                "Load Reference Screenshot": {"image": ref_upload["name"]},
                "Load Character Golden Shot": {"image": golden_upload["name"]},
                "Positive Prompt": {"text": prompt},
                "Random Noise": {"noise_seed": _stable_seed(sid, 2)},
            }
            t0 = time.time()
            img = _render_stage(client=client, workflow=wf2, overrides=overrides, timeout_s=timeout_s)
            _write_image_bytes(out_path, img)
            print(f"[S2 {i}/{len(cuts)}] {sid} OK ({time.time()-t0:.0f}s)")
            ok += 1
        except Exception as e:
            msg = str(e).replace("\n", " ")
            print(f"[S2 {i}/{len(cuts)}] {sid} ERROR: {msg[:240]}")
            fail += 1
    return ok, skip, fail


def _stage3_pass(
    *,
    cuts: list[CutItem],
    client: ComfyUIClient,
    wf3: dict,
    stage2_dir: Path,
    stage25_dir: Path | None,
    stage3_dir: Path,
    timeout_s: int,
    resume: bool,
    prefer_kontext: bool,
) -> tuple[int, int, int]:
    ok = skip = fail = 0
    for i, cut in enumerate(cuts, start=1):
        sid = cut.shot_id
        in_path = stage2_dir / f"{sid}_char.png"
        if prefer_kontext and stage25_dir is not None:
            k = stage25_dir / f"{sid}_kontext.png"
            if k.exists():
                in_path = k
        out_path = stage3_dir / f"panel_{sid}.png"
        if not in_path.exists():
            print(f"[S3 {i}/{len(cuts)}] {sid} SKIP (missing input: {in_path.name})")
            skip += 1
            continue
        if resume and out_path.exists():
            print(f"[S3 {i}/{len(cuts)}] {sid} SKIP (exists)")
            skip += 1
            continue
        try:
            stage2_upload = client.upload_image(str(in_path))
            overrides = {
                "Load Stage 2 Result": {"image": stage2_upload["name"]},
            }
            t0 = time.time()
            img = _render_stage(client=client, workflow=wf3, overrides=overrides, timeout_s=timeout_s)
            _write_image_bytes(out_path, img)
            print(f"[S3 {i}/{len(cuts)}] {sid} OK ({time.time()-t0:.0f}s)")
            ok += 1
        except Exception as e:
            msg = str(e).replace("\n", " ")
            print(f"[S3 {i}/{len(cuts)}] {sid} ERROR: {msg[:240]}")
            fail += 1
    return ok, skip, fail


def _stage25_kontext_pass(
    *,
    cuts: list[CutItem],
    client: ComfyUIClient,
    wf25: dict,
    stage2_dir: Path,
    stage25_dir: Path,
    timeout_s: int,
    resume: bool,
) -> tuple[int, int, int]:
    """Stage 2.5: Kontext refinement pass (runs after Stage2, before Stage3)."""
    ok = skip = fail = 0
    stage25_dir.mkdir(parents=True, exist_ok=True)

    # Required node titles in the Kontext API workflow.
    required_titles = {
        "Load Stage 2 Result",
        "Save Kontext Refined",
    }
    titles = {n.get("_meta", {}).get("title", "") for n in wf25.values()}
    missing = [t for t in required_titles if t not in titles]
    if missing:
        raise RuntimeError(
            "Kontext workflow is missing required node titles: "
            + ", ".join(missing)
            + ". Export an API-format workflow and ensure node titles match."
        )

    for i, cut in enumerate(cuts, start=1):
        sid = cut.shot_id
        in_path = stage2_dir / f"{sid}_char.png"
        out_path = stage25_dir / f"{sid}_kontext.png"

        if not in_path.exists():
            print(f"[S2.5 {i}/{len(cuts)}] {sid} SKIP (missing Stage2: {in_path.name})")
            skip += 1
            continue
        if resume and out_path.exists():
            print(f"[S2.5 {i}/{len(cuts)}] {sid} SKIP (exists)")
            skip += 1
            continue

        try:
            inp = client.upload_image(str(in_path))
            overrides = {
                "Load Stage 2 Result": {"image": inp["name"]},
                # Optional: if the workflow has a prompt node titled "Positive Prompt",
                # we feed the compiled prompt for light consistency guidance.
            }
            prompt = cut.data.get("compiled_prompt")
            if prompt:
                overrides["Positive Prompt"] = {"text": prompt}
            t0 = time.time()
            img = _render_stage(client=client, workflow=wf25, overrides=overrides, timeout_s=timeout_s)
            _write_image_bytes(out_path, img)
            print(f"[S2.5 {i}/{len(cuts)}] {sid} OK ({time.time()-t0:.0f}s)")
            ok += 1
        except Exception as e:
            msg = str(e).replace("\n", " ")
            print(f"[S2.5 {i}/{len(cuts)}] {sid} ERROR: {msg[:240]}")
            fail += 1

    return ok, skip, fail


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, help="episodes/epXX/manifest.json")
    parser.add_argument(
        "--stage",
        type=int,
        default=0,
        choices=[0, 1, 2, 25, 3],
        help="0=all (S1 -> S2 -> [S2.5 kontext] -> S3), 1/2/25/3=single stage pass",
    )
    parser.add_argument("--shot", default="", help="Filter by shot_id prefix (e.g. s001)")
    parser.add_argument("--limit", type=int, default=0, help="Process only first N cuts (after filtering)")
    parser.add_argument("--resume", action="store_true", help="Skip outputs that already exist")
    parser.add_argument("--kontext", action="store_true", help="Enable Stage 2.5 Kontext refinement between Stage2 and Stage3")
    parser.add_argument("--kontext-workflow", default=str(STAGE25_WORKFLOW_PATH), help="API-format Kontext workflow path")
    parser.add_argument("--comfyui-url", default="http://127.0.0.1:8188")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()

    manifest_path = (PROJECT_ROOT / args.manifest).resolve() if not Path(args.manifest).is_absolute() else Path(args.manifest)
    _require_file(manifest_path, "manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    ep_id = manifest.get("episode_id") or manifest_path.parent.name
    ep_dir = PROJECT_ROOT / "episodes" / ep_id
    # Prefer manifest location if it is already under episodes/
    if "episodes" in manifest_path.parts:
        ep_dir = manifest_path.parent

    stage1_dir = ep_dir / "storyboard" / "stage1_layout"
    stage2_dir = ep_dir / "storyboard" / "stage2_character"
    stage25_dir = ep_dir / "storyboard" / "stage2_kontext"
    stage3_dir = ep_dir / "storyboard" / "panels"
    stage1_dir.mkdir(parents=True, exist_ok=True)
    stage2_dir.mkdir(parents=True, exist_ok=True)
    stage25_dir.mkdir(parents=True, exist_ok=True)
    stage3_dir.mkdir(parents=True, exist_ok=True)

    blank = _ensure_blank_white(PROJECT_ROOT)

    cuts = _iter_cuts(manifest)
    if args.shot:
        cuts = [c for c in cuts if c.shot_id.startswith(args.shot)]
    if args.limit and args.limit > 0:
        cuts = cuts[: args.limit]

    if not cuts:
        print("No cuts to process (check --shot/--limit).")
        return

    wf1 = load_workflow(str(STAGE1_WORKFLOW_PATH))
    wf2 = load_workflow(str(STAGE2_WORKFLOW_PATH))
    wf3 = load_workflow(str(STAGE3_WORKFLOW_PATH))
    wf25 = None
    if args.stage == 25 or (args.kontext and args.stage in (0, 3)):
        # Kontext is optional, but if requested we require an API-format workflow file.
        wf25_path = Path(args.kontext_workflow)
        if not wf25_path.is_absolute():
            wf25_path = PROJECT_ROOT / wf25_path
        wf25 = load_workflow(str(wf25_path))

    client = ComfyUIClient(url=args.comfyui_url)
    client.health_check(min_free_gb=1.0)

    t_all = time.time()

    lock_path = ep_dir / "storyboard" / ".render.lock"

    s1 = (0, 0, 0)
    s2 = (0, 0, 0)
    s25 = (0, 0, 0)
    s3 = (0, 0, 0)

    with _exclusive_lock(lock_path):
        if args.stage in (0, 1):
            print("=" * 60)
            print("Stage 1 Pass (composition/layout)")
            print("=" * 60)
            client.health_check(min_free_gb=1.0)
            s1 = _stage1_pass(
                cuts=cuts,
                client=client,
                wf1=wf1,
                stage1_dir=stage1_dir,
                blank=blank,
                timeout_s=args.timeout,
                resume=args.resume,
            )

        if args.stage in (0, 2):
            print("=" * 60)
            print("Stage 2 Pass (character via IP-Adapter)")
            print("=" * 60)
            client.health_check(min_free_gb=1.0)
            s2 = _stage2_pass(
                cuts=cuts,
                client=client,
                wf2=wf2,
                stage1_dir=stage1_dir,
                stage2_dir=stage2_dir,
                blank=blank,
                timeout_s=args.timeout,
                resume=args.resume,
            )

        if args.stage == 25 or (args.stage == 0 and args.kontext):
            print("=" * 60)
            print("Stage 2.5 Pass (Kontext refinement)")
            print("=" * 60)
            if wf25 is None:
                raise RuntimeError("Kontext requested but no workflow was loaded (unexpected).")
            client.health_check(min_free_gb=1.0)
            s25 = _stage25_kontext_pass(
                cuts=cuts,
                client=client,
                wf25=wf25,
                stage2_dir=stage2_dir,
                stage25_dir=stage25_dir,
                timeout_s=args.timeout,
                resume=args.resume,
            )

        if args.stage in (0, 3):
            print("=" * 60)
            print("Stage 3 Pass (AnimeSharp 4x -> 1920x1080, no crop)")
            print("=" * 60)
            client.health_check(min_free_gb=1.0)
            s3 = _stage3_pass(
                cuts=cuts,
                client=client,
                wf3=wf3,
                stage2_dir=stage2_dir,
                stage25_dir=stage25_dir,
                stage3_dir=stage3_dir,
                timeout_s=args.timeout,
                resume=args.resume,
                prefer_kontext=args.kontext,
            )

    dt = time.time() - t_all
    ok_total = s1[0] + s2[0] + s25[0] + s3[0]
    skip_total = s1[1] + s2[1] + s25[1] + s3[1]
    fail_total = s1[2] + s2[2] + s25[2] + s3[2]
    print("=" * 60)
    print(f"COMPLETE in {dt/60:.1f} min")
    print(f"  S1 OK/SKIP/FAIL: {s1[0]}/{s1[1]}/{s1[2]}")
    print(f"  S2 OK/SKIP/FAIL: {s2[0]}/{s2[1]}/{s2[2]}")
    print(f"  S2.5 OK/SKIP/FAIL: {s25[0]}/{s25[1]}/{s25[2]}")
    print(f"  S3 OK/SKIP/FAIL: {s3[0]}/{s3[1]}/{s3[2]}")
    print(f"  TOTAL OK/SKIP/FAIL: {ok_total}/{skip_total}/{fail_total}")


if __name__ == "__main__":
    main()
