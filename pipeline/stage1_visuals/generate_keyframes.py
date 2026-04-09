#!/usr/bin/env python3
"""Unified keyframe generator — manifest-driven shot production.

Replaces manual compose_keyframe.py calls by routing each shot to the
appropriate renderer and applying quality gates.

Pipeline per shot:
  1. Detect mode (scene/confessional/interview)
  2. Render via ComfyUI (IP-Adapter + Canny + AnimeSharp upscale)
  3. Score via score_keyframe.py heuristic
  4. FAIL → retry with seed change (up to 3x)
  5. Write final keyframe + update manifest stage_scores

Usage:
    python generate_keyframes.py --manifest episodes/ep06/manifest.json --all
    python generate_keyframes.py --manifest episodes/ep06/manifest.json --shot 1
    python generate_keyframes.py --manifest episodes/ep06/manifest.json --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "pipeline" / "shared"))

from manifest_loader import get_shots_for_compose  # noqa: E402

# Quality thresholds
AESTHETIC_THRESHOLD = 4.5  # lowered for infographics
MAX_RETRIES = 3

# Paths
SCORE_SCRIPT = PROJECT_ROOT / "pipeline" / "stage1_visuals" / "score_keyframe.py"
CANNY_WORKFLOW_PATH = PROJECT_ROOT / "workflows" / "legacy" / "golden_chibi.json"
IPADAPTER_WORKFLOW_PATH = PROJECT_ROOT / "workflows" / "legacy" / "golden_chibi.json"
GOLDEN_SHOT_DIR = PROJECT_ROOT / "assets" / "characters"

# ─── SSOT import ───
from character_config import STYLE_ANCHOR, CHARACTER_VISUAL_DESC
STYLE_PREFIX = STYLE_ANCHOR + ", "

# Beat role → cinematographic tone modifiers
BEAT_TONE_MAP = {
    "establish": "wide establishing shot, clear geography, readable screen direction",
    "explain": "medium shot, informational framing, clean composition",
    "escalate": "intense close-up, high tension, claustrophobic framing, dramatic angle",
    "compare": "split composition, balanced two-subject framing, contrast emphasis",
    "payoff": "impactful reveal shot, dramatic lighting shift, emotional peak",
    "button": "punctuation shot, brief beat, clean exit framing",
}

# Camera preset → prompt modifiers
CAMERA_PROMPT_MAP = {
    "static_hold": "static camera, stable composition",
    "slow_push_in": "subtle forward movement, increasing intimacy",
    "dramatic_push_in": "dramatic zoom-in, building tension",
    "pull_out_reveal": "camera pulling back, revealing context",
    "pan_left": "horizontal pan left, following action",
    "pan_right": "horizontal pan right, following action",
    "tilt_up": "camera tilting upward, revealing scale",
    "tilt_down": "camera tilting downward, grounding subject",
}

def detect_mode(shot: dict) -> str:
    """Detect shot rendering mode from manifest data.

    This show is 100% animation — ALL shots (DOCU, SKIT, INTERVIEW, CONFESSIONAL)
    are anime-style scenes with characters. No infographic mode.
    """
    vp = (shot.get("enriched_visual_prompt") or shot.get("visual_prompt") or "").lower()
    if "confessional" in vp:
        return "confessional"
    shot_type = (shot.get("type") or "").upper()
    if shot_type == "INTERVIEW":
        return "interview"
    return "scene"


def find_episode_keyframe_renderer(manifest_path: Path) -> Path | None:
    """Find an episode-specific renderer that can own all shot types.

    NOTE: Episode-specific PIL renderers have been archived to _archive/.
    This function is kept for future ComfyUI-based episode renderers only.
    PIL-based renderers in _archive/ are intentionally excluded.
    """
    ep_dir = manifest_path.parent
    for candidate in [
        PROJECT_ROOT / "pipeline" / "stage1_visuals" / f"render_keyframes_{ep_dir.name}.py",
        ep_dir / "render_keyframes.py",
    ]:
        if candidate.exists() and "_archive" not in str(candidate):
            return candidate
    return None


def render_episode_keyframe(shot_num: int, manifest_path: Path, output_dir: Path) -> tuple[bool, str] | None:
    """Run an episode-specific renderer when one is available."""
    renderer = find_episode_keyframe_renderer(manifest_path)
    if not renderer:
        return None

    target = output_dir / f"keyframe_{shot_num:02d}.png"
    result = subprocess.run(
        [
            sys.executable,
            str(renderer),
            "--manifest",
            str(manifest_path),
            "--shot",
            str(shot_num),
            "--output-dir",
            str(output_dir),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        print(f"    [WARN] Episode renderer failed: {stderr[:200]}")
        return None
    if not target.exists():
        print("    [WARN] Episode renderer completed without writing the expected keyframe")
        return None
    return True, "episode_keyframe_renderer"


# Shot size → natural language camera description
SHOT_SIZE_NL = {
    "ECU": "extreme close-up focusing on facial details",
    "CU": "close-up portrait shot",
    "MCU": "medium close-up from chest up",
    "MS": "medium shot from waist up",
    "MLS": "medium long shot showing most of the body",
    "FS": "full body shot",
    "LS": "long shot showing the full figure and environment",
    "ELS": "extreme long shot establishing the full scene",
    "IS": "insert shot focusing on a specific object or detail",
}

# Angle → natural language
ANGLE_NL = {
    "eye_level": "at eye level",
    "low_angle": "from a low angle looking up, giving a sense of power",
    "high_angle": "from a high angle looking down",
    "dutch_angle": "with a tilted dutch angle creating unease",
    "birds_eye": "from a bird's-eye view directly above",
    "worms_eye": "from a worm's-eye view on the ground",
    "overhead": "from directly overhead",
    "ground_level": "from ground level",
}

# Mood → atmospheric description
MOOD_NL = {
    "comedy": "with a lighthearted comedic atmosphere",
    "serious": "with a serious and focused atmosphere",
    "tense": "with a tense and suspenseful atmosphere",
    "intimidating": "with an intimidating and threatening atmosphere",
    "melancholy": "with a melancholic and somber atmosphere",
    "chaotic": "with a chaotic and energetic atmosphere",
    "peaceful": "with a calm and peaceful atmosphere",
    "epic": "with an epic and grand atmosphere",
    "triumphant": "with a triumphant and victorious atmosphere",
    "mysterious": "with a mysterious and enigmatic atmosphere",
    "romantic": "with a warm romantic atmosphere",
    "horror": "with a dark and unsettling atmosphere",
}

# Composition → framing description
COMPOSITION_NL = {
    "single": "with a single character centered in frame",
    "two_shot": "framing two characters in three-quarter view facing each other, both faces visible at quarter angle not pure profile",
    "group": "showing a group of characters together",
    "centered": "with centered symmetrical framing",
    "negative_space": "using negative space to create visual breathing room",
    "over_the_shoulder": "over-the-shoulder perspective",
    "leading_lines": "using leading lines to guide the eye",
    "frame_in_frame": "with frame-within-frame composition",
    "symmetrical": "with balanced symmetrical composition",
    "split_screen": "with split-screen divided composition",
}

# Situation → scene context
SITUATION_NL = {
    "confrontation": "during a tense confrontation",
    "conversation": "during a casual conversation",
    "reaction": "capturing a reaction moment",
    "establishing": "establishing the scene and setting",
    "observation": "quietly observing the situation",
    "monologue": "during an internal monologue",
    "exposition": "explaining something important",
    "idle": "in a relaxed idle moment",
    "celebration": "during a celebration",
    "fight": "in the middle of a conflict",
}


def assemble_shot_prompt(shot: dict) -> str:
    """Build a booru-tag style prompt for Flux + Juustagram Chibi LoRA.

    This LoRA was trained on tag-based captions. Keep it concise:
    Style tags → Character tags → Scene tags → Camera tags
    Target: under 200 chars for best quality.
    """
    tags = []

    # 1. Character (most important — goes right after style prefix)
    characters = shot.get("characters") or []
    for char_name in characters[:2]:
        desc = CHARACTER_VISUAL_DESC.get(char_name)
        if desc:
            tags.append(desc)

    # 2. Scene — just the visual essence, strip abstract concepts
    enriched = shot.get("enriched_visual_prompt") or shot.get("visual_prompt") or ""
    if enriched:
        # Take only first sentence, strip non-visual abstractions
        first_sentence = enriched.strip().split(".")[0][:80]
        tags.append(first_sentence)

    # 3. Camera/composition (from 6-axis system, as tags not sentences)
    beat_role = (shot.get("beat_role") or "").lower()
    beat_shot = {"establish": "wide shot", "explain": "medium shot", "escalate": "close-up",
                 "compare": "medium shot", "payoff": "full shot", "button": "close-up"}.get(beat_role, "medium shot")
    tags.append(beat_shot)

    # Angle
    ref = shot.get("storyboard_reference") or {}
    carry = ref.get("carry_over") or {}
    angle = carry.get("angle", "eye_level")
    angle_tag = {"eye_level": "eye level", "low_angle": "low angle", "high_angle": "high angle",
                 "dutch_angle": "dutch angle"}.get(angle, "eye level")
    tags.append(angle_tag)

    # 4. Background
    scene_title = (shot.get("scene_title") or "").upper()
    shot_type = (shot.get("type") or "SKIT").upper()
    bg_tag = "simple white background"  # Default

    if shot_type == "CONFESSIONAL":
        bg_tag = "dark background, single spotlight from above"
    elif shot_type == "INTERVIEW":
        bg_tag = "dark background, professional side lighting"
    elif "CONFRONTATION" in scene_title or "STANDOFF" in scene_title:
        bg_tag = "split screen red vs blue background, dramatic"
    elif "MAP" in scene_title or "DOCU" in scene_title:
        bg_tag = "cute illustrated world map background, pastel colors"
    else:
        bg_tag = "simple white background"

    tags.append(bg_tag)

    # Assemble
    prompt = STYLE_PREFIX + ", ".join(tags)

    # Hard cap
    if len(prompt) > 350:
        prompt = prompt[:347] + "..."

    return prompt


# Beat role → preferred reference show for cinematography
BEAT_REFERENCE_SHOW_PREFERENCE = {
    "establish": ["nichijou"],
    "explain": ["nichijou"],
    "escalate": ["bocchi", "jojo3", "nichijou"],
    "compare": ["jojo3", "nichijou"],
    "payoff": ["psg_2010", "psg_new", "nichijou"],
    "button": ["nichijou"],
}

# Screenshot root — resolved via project_paths (no hardcoded /mnt/e/)
from project_paths import get_screenshot_root
from scene_cluster import search_scenes
SCREENSHOT_ROOT = get_screenshot_root()


def select_reference_image(shot: dict) -> Path | None:
    """Select best reference image: manifest first, then beat-aware fallback."""
    # 1. Try manifest storyboard_reference (already selected by adapter)
    for source_key in ("storyboard_reference_modes", "storyboard_reference"):
        source = shot.get(source_key) or {}
        if source_key == "storyboard_reference_modes":
            for mode_key in ("composition", "background", "character"):
                mode = source.get(mode_key) or {}
                ref_img = mode.get("reference_image") or {}
                path = ref_img.get("actual_path")
                if path and Path(path).exists():
                    return Path(path)
        else:
            ref_img = source.get("reference_image") or {}
            path = ref_img.get("actual_path")
            if path and Path(path).exists():
                return Path(path)

    # 2. Scene cluster search (씬 단위 대표 프레임 — 작품 스타일 가중치 적용)
    try:
        shot_size = (shot.get("shot_size") or "MS").lower()
        scene_type = (shot.get("type") or "SKIT").upper()
        mood_map = {"SKIT": "comedy", "DOCU": "serious", "CONFESSIONAL": "melancholy"}
        beat_role = (shot.get("beat_role") or "establish").lower()
        preferred = BEAT_REFERENCE_SHOW_PREFERENCE.get(beat_role, [])
        result = search_scenes(
            shot_size=shot_size,
            mood=mood_map.get(scene_type, "comedy"),
            scene_type=scene_type,
            preferred_shows=preferred or None,
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

    # 3. Beat-aware directory fallback
    beat_role = (shot.get("beat_role") or "establish").lower()
    preferred_shows = BEAT_REFERENCE_SHOW_PREFERENCE.get(beat_role, ["nichijou"])

    for show in preferred_shows:
        show_dir = SCREENSHOT_ROOT / show
        if not show_dir.exists():
            continue
        ep_dirs = sorted([d for d in show_dir.iterdir() if d.is_dir()])
        if not ep_dirs:
            continue
        shot_num = int(shot.get("shot_id", "s001").replace("s", ""))
        ep_dir = ep_dirs[shot_num % len(ep_dirs)]
        frames = sorted(ep_dir.glob("frame_*.jpg"))
        if not frames:
            frames = sorted(ep_dir.glob("*.jpg")) + sorted(ep_dir.glob("*.png"))
        if frames:
            start = len(frames) // 4
            end = len(frames) * 3 // 4
            mid_frames = frames[start:end] if end > start else frames
            idx = shot_num % len(mid_frames)
            return mid_frames[idx]

    return None


def _find_golden_shot(characters: list[str]) -> Path | None:
    """Find the golden shot PNG for the first character with one."""
    for char in characters:
        for pattern in [
            GOLDEN_SHOT_DIR / char / f"{char}_golden.png",
            GOLDEN_SHOT_DIR / char / f"{char}_psg_golden.png",
        ]:
            if pattern.exists():
                return pattern
    return None


RENDER_LOG: list[dict] = []  # Accumulated render log entries


def _log_render(entry: dict, output_dir: Path):
    """Append render log entry and write to render_log.json."""
    RENDER_LOG.append(entry)
    log_path = output_dir / "render_log.json"
    log_path.write_text(json.dumps(RENDER_LOG, ensure_ascii=False, indent=2))


def render_comfyui(shot_num: int, shot: dict, output_dir: Path, attempt: int = 1) -> tuple[bool, str]:
    """Render a keyframe via ComfyUI IP-Adapter + Canny + AnimeSharp upscale."""
    render_start = time.time()
    log_entry = {
        "shot_id": f"s{shot_num:03d}",
        "attempt": attempt,
        "timestamp": datetime.now().isoformat(),
        "success": False,
        "output_kind": None,
        "seed": None,
        "ref_image": None,
        "golden_image": None,
        "char_lora": None,
        "render_time_sec": None,
        "output_hash": None,
        "output_size": None,
        "output_resolution": None,
        "error": None,
    }

    try:
        from comfyui_client import ComfyUIClient
    except ImportError:
        log_entry["error"] = "comfyui_import_fail"
        _log_render(log_entry, output_dir)
        return False, "comfyui_import_fail"

    target = output_dir / f"keyframe_{shot_num:02d}.png"

    # Choose workflow: IP-Adapter if available, fallback to Canny-only
    workflow_path = IPADAPTER_WORKFLOW_PATH if IPADAPTER_WORKFLOW_PATH.exists() else CANNY_WORKFLOW_PATH
    use_ipadapter = workflow_path == IPADAPTER_WORKFLOW_PATH

    try:
        client = ComfyUIClient()
        health = client.health_check(min_free_gb=1.0)
        if not health.get("comfyui_ok"):
            print(f"    [WARN] ComfyUI not healthy: {health}")
            return False, "comfyui_unhealthy"

        if not workflow_path.exists():
            print(f"    [WARN] Workflow not found: {workflow_path}")
            return False, "workflow_missing"

        with open(workflow_path) as f:
            workflow = json.load(f)

        # 1. Upload reference image (for Canny ControlNet composition guide)
        ref_path = select_reference_image(shot)
        if ref_path is None:
            print("    [WARN] No reference image found for shot")
            return False, "no_reference"

        ref_upload = client.upload_image(str(ref_path))

        # 2. Assemble prompt
        prompt_text = assemble_shot_prompt(shot)
        print(f"    Prompt: {prompt_text[:80]}...")
        print(f"    Ref: {ref_path.name} (Canny)")

        # 3. Build overrides
        seed = (shot_num * 1000 + attempt * 137 + int(time.time()) % 10000)
        overrides = {
            "Load Reference Screenshot": {"image": ref_upload["name"]},
            "Positive Prompt": {"text": prompt_text},
            "Random Noise": {"noise_seed": seed},
        }

        # 4. Upload character golden shot for IP-Adapter
        if use_ipadapter:
            characters = shot.get("characters") or []
            golden_path = _find_golden_shot(characters)
            if golden_path:
                golden_upload = client.upload_image(str(golden_path))
                overrides["Load Character Golden Shot"] = {"image": golden_upload["name"]}
                print(f"    Golden: {golden_path.name} (IP-Adapter)")
            else:
                # No golden shot → use reference image as IP-Adapter input too
                overrides["Load Character Golden Shot"] = {"image": ref_upload["name"]}
                print(f"    Golden: none, using ref as IP-Adapter fallback")

        # 5. Character LoRA (if trained)
        if characters:
            char_name = characters[0]
            lora_path = PROJECT_ROOT / "assets" / "loras" / f"{char_name}_lora.safetensors"
            if lora_path.exists():
                overrides["Character LoRA (optional)"] = {
                    "lora_name": lora_path.name,
                    "strength_model": 1.0,
                    "strength_clip": 1.0,
                }
                print(f"    LoRA: {lora_path.name} @ 1.0")

        # 5. Queue and wait
        prompt_id = client.queue_workflow(workflow, overrides=overrides)
        print(f"    Queued: {prompt_id[:12]}... ({'IP-Adapter' if use_ipadapter else 'Canny-only'})")
        result = client.wait_for_completion(prompt_id, timeout=600, poll_interval=5.0)

        if not result or not result.get("outputs"):
            print("    [WARN] ComfyUI returned no outputs")
            return False, "comfyui_no_output"

        # 7. Save output (already upscaled by workflow if IP-Adapter path)
        output_dir.mkdir(parents=True, exist_ok=True)
        log_entry["seed"] = seed
        log_entry["ref_image"] = ref_path.name if ref_path else None

        for node_id, node_out in result["outputs"].items():
            if "images" in node_out:
                for img_info in node_out["images"]:
                    img_data = client.get_image(img_info)
                    target.write_bytes(img_data)
                    img = Image.open(target)
                    # Fallback PIL upscale only if workflow didn't upscale
                    if img.size[0] < 1920 and not use_ipadapter:
                        img = img.resize((1920, 1080), Image.Resampling.LANCZOS)
                        img.save(target, "PNG")
                    method = "ipadapter_upscale" if use_ipadapter else "canny_only"

                    # Output validation
                    file_size = target.stat().st_size
                    if file_size < 10_000:
                        print(f"    [FAIL] Output too small ({file_size} bytes) — likely blank")
                        log_entry["error"] = f"output_too_small_{file_size}"
                        _log_render(log_entry, output_dir)
                        return False, "output_too_small"

                    output_hash = hashlib.md5(target.read_bytes()).hexdigest()
                    log_entry.update({
                        "success": True,
                        "output_kind": f"comfyui_{method}",
                        "render_time_sec": round(time.time() - render_start, 1),
                        "output_hash": output_hash,
                        "output_size": file_size,
                        "output_resolution": f"{img.size[0]}x{img.size[1]}",
                    })
                    _log_render(log_entry, output_dir)

                    print(f"    Saved: {target} ({file_size} bytes, {img.size[0]}x{img.size[1]})")
                    return True, f"comfyui_{method}"

        log_entry["error"] = "no_images_in_output"
        _log_render(log_entry, output_dir)
        return False, "comfyui_no_images"

    except Exception as e:
        log_entry["error"] = str(e)[:200]
        log_entry["render_time_sec"] = round(time.time() - render_start, 1)
        _log_render(log_entry, output_dir)
        print(f"    [ERROR] ComfyUI render failed: {e}")
        return False, "comfyui_error"


def score_shot(shot_num: int, manifest_path: Path, image_dir: Path) -> tuple[bool, float]:
    """Run quality gate on a single shot. Returns (passed, aesthetic_score)."""
    result = subprocess.run(
        [sys.executable, str(SCORE_SCRIPT),
         "--manifest", str(manifest_path),
         "--shot", str(shot_num),
         "--image-dir", str(image_dir),
         "--no-clip",
         "--threshold-aesthetic", str(AESTHETIC_THRESHOLD)],
        capture_output=True, text=True, timeout=30,
    )
    # Parse aesthetic score from output
    aes_score = 0.0
    passed = result.returncode == 0
    for line in result.stdout.split("\n"):
        if f"Shot {shot_num:02d}" in line:
            # Extract Aes=X.X
            import re
            m = re.search(r"Aes=(\d+\.?\d*)", line)
            if m:
                aes_score = float(m.group(1))
            break
    return passed, aes_score


def refine_with_img2img(keyframe_path: Path, prompt: str) -> bool:
    """Optional: refine PIL composite via ComfyUI img2img (Phase 4-A).

    This requires ComfyUI running + legacy/img2img_refine.json workflow.
    Returns True if refinement was applied, False if skipped.
    """
    workflow_path = PROJECT_ROOT / "workflows" / "legacy" / "img2img_refine.json"
    if not workflow_path.exists():
        return False  # Phase 4 not yet implemented

    try:
        from comfyui_client import ComfyUIClient
        client = ComfyUIClient()
        status = client.health_check(min_free_gb=2.0)
        if not status.get("healthy"):
            return False

        with open(workflow_path) as f:
            workflow = json.load(f)

        overrides = {
            "Load Image": {"image": str(keyframe_path)},
            "CLIP Text Encode (Prompt)": {"text": prompt[:300]},
            "KSampler": {"denoise": 0.3, "seed": int(time.time()) % 2**32},
        }

        prompt_id = client.queue_workflow(workflow, overrides)
        result = client.wait_for_completion(prompt_id, timeout=120)
        if result:
            # Save refined image
            for node_id, images in result.get("outputs", {}).items():
                for img_info in images:
                    img_data = client.get_image(img_info)
                    keyframe_path.write_bytes(img_data)
                    return True
    except Exception as e:
        print(f"    [WARN] img2img refine failed: {e}")

    return False


def process_shot(
    shot_num: int,
    shot_data: dict,
    manifest_path: Path,
    output_dir: Path,
    dry_run: bool = False,
    refine: bool = False,
) -> dict:
    """Process a single shot through the full pipeline. Returns result dict."""
    mode = detect_mode(shot_data)
    keyframe = output_dir / f"keyframe_{shot_num:02d}.png"

    result = {
        "shot_num": shot_num,
        "mode": mode,
        "rendered": False,
        "passed": False,
        "aesthetic": 0.0,
        "refined": False,
        "retries": 0,
        "output_kind": None,
    }

    if dry_run:
        status = "EXISTS" if keyframe.exists() else "PENDING"
        print(f"  s{shot_num:03d} [{mode:12s}] {status}")
        return result

    print(f"\n  s{shot_num:03d} [{mode}]")

    # Render — ALL shots go through ComfyUI (this is a 100% animation show)
    for attempt in range(1, MAX_RETRIES + 1):
        success, output_kind = render_comfyui(shot_num, shot_data, output_dir, attempt=attempt)
        if not success:
            print(f"    [FAIL] ComfyUI render failed: {output_kind}")

        result["output_kind"] = output_kind

        if not success:
            print(f"    [FAIL] Render failed (attempt {attempt}/{MAX_RETRIES})")
            result["retries"] = attempt
            continue

        result["rendered"] = True

        # Score
        passed, aes = score_shot(shot_num, manifest_path, output_dir)
        result["aesthetic"] = aes
        result["passed"] = passed

        if passed:
            print(f"    [PASS] Aes={aes:.1f}")
            break
        else:
            print(f"    [RETRY] Aes={aes:.1f} < {AESTHETIC_THRESHOLD} (attempt {attempt}/{MAX_RETRIES})")
            result["retries"] = attempt

    # Optional img2img refine (Phase 4-A)
    if refine and result["passed"] and mode != "infographic":
        prompt = shot_data.get("enriched_visual_prompt", "")
        if refine_with_img2img(keyframe, prompt):
            result["refined"] = True
            print(f"    [REFINED] img2img denoise 0.3 applied")

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Unified keyframe generator.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--shot", type=int, help="Single shot number")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without rendering")
    parser.add_argument("--refine", action="store_true", help="Apply img2img refinement (Phase 4-A)")
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    if not args.shot and not args.all:
        parser.error("Specify --shot N or --all")

    manifest_path = args.manifest.resolve()
    if not manifest_path.exists():
        print(f"ERROR: {manifest_path}")
        sys.exit(1)

    output_dir = args.output_dir or (manifest_path.parent / "images")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load manifest
    with open(manifest_path) as f:
        manifest = json.load(f)

    shots = {}
    for shot in manifest.get("shots", []):
        num = int(shot["shot_id"].replace("s", ""))
        shots[num] = shot

    shot_nums = [args.shot] if args.shot else sorted(shots.keys())

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Keyframe Generator")
    print(f"Manifest: {manifest_path}")
    print(f"Output:   {output_dir}")
    print(f"Shots:    {len(shot_nums)}")
    print(f"Refine:   {'ON' if args.refine else 'OFF'}")
    print("=" * 50)

    results = []
    for num in shot_nums:
        if num not in shots:
            print(f"  s{num:03d} [SKIP] not in manifest")
            continue
        r = process_shot(num, shots[num], manifest_path, output_dir, args.dry_run, args.refine)
        results.append(r)

    if args.dry_run:
        return

    # Persist canonical keyframe paths back into the manifest for downstream stages.
    project_root = PROJECT_ROOT
    changed = False
    for item in results:
        if not item.get("rendered"):
            continue
        shot_num = item["shot_num"]
        shot_id = f"s{shot_num:03d}"
        shot = shots.get(shot_num)
        if not shot:
            continue
        keyframe_path = output_dir / f"keyframe_{shot_num:02d}.png"
        if not keyframe_path.exists():
            continue
        rel_path = str(keyframe_path.relative_to(project_root))
        if shot.get("image_path") != rel_path:
            shot["image_path"] = rel_path
            changed = True
        render_audit = shot.get("render_audit") or {}
        updated_render_audit = {
            "generator": "pipeline/stage1_visuals/generate_keyframes.py",
            "render_method": "comfyui",
            "mode": item.get("mode"),
            "output_kind": item.get("output_kind", ""),
            "quality_passed": item.get("passed", False),
            "aesthetic": item.get("aesthetic", 0.0),
            "refined": item.get("refined", False),
            "rendered_at": datetime.now().isoformat(),
        }
        if render_audit != updated_render_audit:
            shot["render_audit"] = updated_render_audit
            changed = True
        if item.get("refined"):
            if shot.get("image_path_refined") != rel_path:
                shot["image_path_refined"] = rel_path
                changed = True
        elif shot.get("image_path_refined") and shot.get("image_path_refined") != rel_path and not Path(project_root / shot["image_path_refined"]).exists():
            shot.pop("image_path_refined", None)
            changed = True

    if changed:
        manifest["shots"] = [shots[int(shot["shot_id"].replace("s", ""))] for shot in manifest.get("shots", [])]
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # MD5 adjacent-shot duplicate check
    md5_map: dict[str, list[int]] = {}
    for num in sorted(shots.keys()):
        kf = output_dir / f"keyframe_{num:02d}.png"
        if kf.exists():
            h = hashlib.md5(kf.read_bytes()).hexdigest()
            md5_map.setdefault(h, []).append(num)

    dup_shots: list[int] = []
    for h, nums in md5_map.items():
        if len(nums) < 2:
            continue
        # Check if any are adjacent
        for i in range(len(nums) - 1):
            if nums[i + 1] - nums[i] <= 2:  # adjacent or near-adjacent
                dup_shots.extend(nums)
                print(f"  [DUPE] md5={h[:12]} shared by shots: {', '.join(f's{n:03d}' for n in nums)}")
                # Mark as FAIL in manifest
                for n in nums:
                    shot = shots.get(n)
                    if shot:
                        audit = shot.get("render_audit") or {}
                        audit["quality_passed"] = False
                        audit["fail_reason"] = "md5_duplicate_adjacent"
                        shot["render_audit"] = audit
                        changed = True
                break

    # Summary
    rendered = sum(1 for r in results if r["rendered"])
    passed = sum(1 for r in results if r["passed"])
    refined = sum(1 for r in results if r["refined"])
    failed = [r for r in results if r["rendered"] and not r["passed"]]

    print("\n" + "=" * 50)
    print(f"  Rendered: {rendered}/{len(results)}")
    print(f"  Passed:   {passed}/{len(results)}")
    if refined:
        print(f"  Refined:  {refined}")
    if failed:
        fail_ids = ", ".join(f"s{r['shot_num']:03d}" for r in failed)
        print(f"  Failed:   {len(failed)} ({fail_ids})")
    print("=" * 50)

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
