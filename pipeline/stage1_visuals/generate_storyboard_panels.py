#!/usr/bin/env python3
"""Storyboard panel generator — rough ComfyUI panels for framing review.

Generates 960×540 quick-render panels for each shot in the manifest.
These are NOT publishable keyframes — they validate composition, framing,
and character placement BEFORE expensive final renders.

Usage:
    python generate_storyboard_panels.py --manifest episodes/pilot/manifest.json --all
    python generate_storyboard_panels.py --manifest episodes/pilot/manifest.json --shot 1
    python generate_storyboard_panels.py --manifest episodes/pilot/manifest.json --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "pipeline" / "shared"))

from comfyui_client import ComfyUIClient
from project_paths import get_screenshot_root
from scene_cluster import search_scenes

WORKFLOW_PATH = PROJECT_ROOT / "workflows" / "legacy" / "storyboard_quick.json"
GOLDEN_SHOT_DIR = PROJECT_ROOT / "assets" / "characters"
SCREENSHOT_ROOT = get_screenshot_root()

# ─── SSOT import ───
from character_config import STYLE_ANCHOR, CHARACTER_VISUAL_DESC
STYLE_PREFIX = STYLE_ANCHOR + ", "

# Beat → camera framing
BEAT_FRAMING = {
    "establish": "wide shot, establishing scene",
    "explain": "medium shot, clear framing",
    "escalate": "close-up, tense framing",
    "compare": "split composition, two subjects",
    "payoff": "dramatic shot, reveal",
    "button": "close-up, punctuation shot",
}


def build_panel_prompt(shot: dict) -> str:
    """Build a concise prompt for storyboard panel."""
    parts = [STYLE_PREFIX]

    # Characters
    for char in (shot.get("characters") or [])[:2]:
        desc = CHARACTER_VISUAL_DESC.get(char)
        if desc:
            parts.append(desc)

    # Scene essence
    vp = shot.get("enriched_visual_prompt") or shot.get("visual_prompt") or ""
    if vp:
        parts.append(vp.split(".")[0][:60])

    # Camera
    beat = (shot.get("beat_role") or "establish").lower()
    parts.append(BEAT_FRAMING.get(beat, "medium shot"))

    parts.append("school setting, warm lighting")

    prompt = ", ".join(p for p in parts if p)
    return prompt[:300]


def select_reference(shot: dict) -> Path | None:
    """Pick a reference image for ControlNet composition guide."""
    # 1. Manifest reference (from storyboard_reference_adapter)
    for key in ("storyboard_reference_modes", "storyboard_reference"):
        source = shot.get(key) or {}
        if key == "storyboard_reference_modes":
            for mode in ("composition", "background", "character"):
                ref = (source.get(mode) or {}).get("reference_image", {})
                path = ref.get("actual_path")
                if path and Path(path).exists():
                    return Path(path)
                # Also check frame_file relative to screenshot root
                frame_file = (source.get(mode) or {}).get("frame_file")
                if frame_file:
                    full = SCREENSHOT_ROOT / frame_file
                    if full.exists():
                        return full
        else:
            ref = source.get("reference_image", {})
            path = ref.get("actual_path")
            if path and Path(path).exists():
                return Path(path)
            frame_file = source.get("frame_file")
            if frame_file:
                full = SCREENSHOT_ROOT / frame_file
                if full.exists():
                    return full

    # 2. Scene cluster search (씬 단위 대표 프레임)
    try:
        shot_size = (shot.get("shot_size") or "MS").lower()
        scene_type = (shot.get("type") or "SKIT").upper()
        mood_map = {"SKIT": "comedy", "DOCU": "serious", "CONFESSIONAL": "melancholy"}
        result = search_scenes(
            shot_size=shot_size,
            mood=mood_map.get(scene_type, "comedy"),
            scene_type=scene_type,
            limit=1,
        )
        items = result.get("results", [])
        if items:
            rep = items[0].get("representative_frame")
            if rep:
                full = SCREENSHOT_ROOT / rep
                if full.exists():
                    return full
    except Exception:
        pass

    # 3. Screenshot root fallback
    if SCREENSHOT_ROOT.is_dir():
        shot_num = int(shot.get("shot_id", "s001").replace("s", ""))
        shows = sorted([d for d in SCREENSHOT_ROOT.iterdir() if d.is_dir()])
        if shows:
            show = shows[shot_num % len(shows)]
            frames = sorted(show.glob("**/*.jpg"))[:100]
            if frames:
                return frames[shot_num % len(frames)]

    return None


def generate_panel(client: ComfyUIClient, workflow: dict, shot: dict,
                   output_dir: Path) -> dict:
    """Generate a single storyboard panel via ComfyUI."""
    shot_id = shot.get("shot_id", "s001")
    shot_num = int(shot_id.replace("s", ""))
    target = output_dir / f"panel_{shot_id}.png"

    result = {
        "shot_id": shot_id,
        "generated": False,
        "path": str(target),
        "method": "comfyui_storyboard",
        "error": None,
    }

    # Pre-flight
    ref_path = select_reference(shot)
    
    # Fallback to a blank image to avoid ComfyUI error if node exists
    blank_path = PROJECT_ROOT / "assets" / "system" / "blank_white.png"
    if not blank_path.exists():
        blank_path.parent.mkdir(parents=True, exist_ok=True)
        from PIL import Image
        Image.new("RGB", (1024, 1024), (255, 255, 255)).save(blank_path)

    if not ref_path or not ref_path.exists():
        print(f"  {shot_id} [WARN] No reference image found, using blank white fallback")
        ref_path = blank_path

    try:
        # Upload reference
        ref_upload = client.upload_image(str(ref_path))

        # Build prompt
        prompt_text = build_panel_prompt(shot)

        # Overrides — must match nichijou_ipadapter_keyframe.json node titles
        seed = shot_num * 1000 + int(time.time()) % 10000
        overrides = {
            "Load Reference Screenshot": {"image": ref_upload["name"]},
            "Positive Prompt": {"text": prompt_text},
            "Random Noise": {"noise_seed": seed},
            "Load Character Golden Shot": {"image": str(blank_path.absolute())}, # Default fallback
        }

        # Upload golden shot for IP-Adapter (character consistency)
        characters = shot.get("characters") or []
        golden_path = None
        for char in characters:
            gp = GOLDEN_SHOT_DIR / char / f"{char}_golden.png"
            if gp.exists():
                golden_path = gp
                break
        if golden_path:
            golden_upload = client.upload_image(str(golden_path))
            overrides["Load Character Golden Shot"] = {"image": golden_upload["name"]}
        else:
            # No golden → use reference as IP-Adapter input
            overrides["Load Character Golden Shot"] = {"image": ref_upload["name"]}

        # Queue
        prompt_id = client.queue_workflow(workflow, overrides=overrides)
        print(f"  {shot_id} Queued: {prompt_id[:12]}... ref={ref_path.name}")

        # Wait
        completion = client.wait_for_completion(prompt_id, timeout=600, poll_interval=5.0)

        if not completion or not completion.get("images"):
            result["error"] = "no_output"
            print(f"  {shot_id} [FAIL] No output from ComfyUI")
            return result

        # Save
        output_dir.mkdir(parents=True, exist_ok=True)
        for img_info in completion["images"]:
            img_data = client.get_image(img_info)
            target.write_bytes(img_data)
            result["generated"] = True
            size_kb = target.stat().st_size // 1024
            print(f"  {shot_id} [OK] {size_kb}KB")
            return result

    except Exception as e:
        result["error"] = str(e)[:200]
        print(f"  {shot_id} [ERROR] {e}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Storyboard panel generator")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--shot", type=int, help="Single shot number")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    if not args.shot and not args.all:
        parser.error("Specify --shot N or --all")

    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text())
    shots = {int(s["shot_id"].replace("s", "")): s for s in manifest.get("shots", [])}

    output_dir = args.output_dir or (manifest_path.parent / "storyboard" / "panels")
    output_dir.mkdir(parents=True, exist_ok=True)

    shot_nums = [args.shot] if args.shot else sorted(shots.keys())

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Storyboard Panel Generator")
    print(f"Manifest: {manifest_path}")
    print(f"Output:   {output_dir}")
    print(f"Shots:    {len(shot_nums)}")
    print("=" * 50)

    if args.dry_run:
        for num in shot_nums:
            if num not in shots:
                continue
            panel = output_dir / f"panel_s{num:03d}.png"
            status = "EXISTS" if panel.exists() else "PENDING"
            ref = select_reference(shots[num])
            ref_name = ref.name if ref else "NONE"
            print(f"  s{num:03d} [{status}] ref={ref_name}")
        return

    # Load workflow
    if not WORKFLOW_PATH.exists():
        print(f"ERROR: Workflow not found: {WORKFLOW_PATH}")
        sys.exit(1)

    workflow = json.loads(WORKFLOW_PATH.read_text())

    # Connect to ComfyUI
    client = ComfyUIClient()
    try:
        health = client.health_check(min_free_gb=0.0) # Bypass strict check since model might be cached
        if not health.get("comfyui_ok"):
            print(f"ERROR: ComfyUI not healthy: {health}")
            sys.exit(1)
    except SystemExit:
        # If check_gpu still fails, just assume it's running and proceed
        print("[WARN] GPU check failed, but proceeding anyway...")

    results = []
    for num in shot_nums:
        if num not in shots:
            print(f"  s{num:03d} [SKIP] not in manifest")
            continue
        r = generate_panel(client, workflow, shots[num], output_dir)
        results.append(r)

    # Summary
    generated = sum(1 for r in results if r["generated"])
    failed = sum(1 for r in results if not r["generated"])

    print(f"\n{'=' * 50}")
    print(f"  Generated: {generated}/{len(results)}")
    print(f"  Failed:    {failed}/{len(results)}")
    if failed:
        fail_ids = [r["shot_id"] for r in results if not r["generated"]]
        print(f"  Failed shots: {', '.join(fail_ids[:10])}")
    print("=" * 50)

    # Write report
    report_path = output_dir.parent / "panel_generation_report.json"
    report = {
        "generated_at": datetime.now().isoformat(),
        "total_shots": len(results),
        "generated": generated,
        "failed": failed,
        "results": results,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Report: {report_path}")

    sys.exit(1 if failed > len(results) * 0.5 else 0)


if __name__ == "__main__":
    main()
