#!/usr/bin/env python3
"""전체 스토리보드 패널 생성 — manifest 기반 배치 처리.

Usage:
    python generate_storyboard_full.py --manifest episodes/pilot/manifest.json
    python generate_storyboard_full.py --manifest episodes/pilot/manifest.json --batch 1  # batch 1만
    python generate_storyboard_full.py --manifest episodes/pilot/manifest.json --resume    # 이미 생성된 건 스킵
"""
import json
import sys
import time
import argparse
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT / "pipeline" / "shared"))

from comfyui_client import ComfyUIClient
from project_paths import get_screenshot_root

WORKFLOW = PROJECT / "workflows" / "legacy" / "storyboard_quick.json"
CHAR_DIR = PROJECT / "assets" / "characters"
SCREENSHOT_ROOT = get_screenshot_root()

# 캐릭터 프롬프트 (generate_keyframes.py에서 가져옴)
sys.path.insert(0, str(PROJECT / "pipeline" / "stage1_visuals"))
from generate_keyframes import CHARACTER_VISUAL_DESC

STYLE_PREFIX = "juustagram style, chibi, azur lane slow ahead style, flat color cel shading, thick black outlines, pastel color palette, clean anime art, "


def _infer_bg(shot):
    """샷 타입 기반 배경 추론 (No Metaphor Rule — 아파트/학교 비유 금지)."""
    shot_type = (shot.get("type") or "SKIT").upper()
    vp = (shot.get("enriched_visual_prompt") or shot.get("visual_prompt") or "").lower()

    if shot_type == "CONFESSIONAL":
        return "dark background, single spotlight from above"
    if shot_type == "INTERVIEW":
        return "dark background, professional side lighting"
    if any(w in vp for w in ["confrontation", "standoff", "versus", "face to face"]):
        return "split screen red vs blue background, dramatic"
    if any(w in vp for w in ["map", "globe", "world"]):
        return "cute illustrated world map background, pastel colors"
    if any(w in vp for w in ["ocean", "sea", "strait", "ship"]):
        return "simple blue ocean background with waves"
    return "simple white background"


def build_prompt(shot, use_natural: bool = False):
    """compiled_prompt 우선 사용, 없으면 폴백. use_natural=True면 자연어 프롬프트."""
    if use_natural:
        nl = shot.get("compiled_prompt_nl")
        if nl:
            return nl
    compiled = shot.get("compiled_prompt")
    if compiled:
        return compiled

    # 폴백: 기존 방식
    tags = []
    shot_size = shot.get("shot_size") or "MS"
    size_map = {"ECU": "extreme close-up shot", "CU": "close-up shot", "MCU": "medium close-up shot, bust shot",
                "MS": "medium shot, waist up", "MLS": "medium long shot", "LS": "long shot, wide shot, full body",
                "ELS": "extreme long shot, wide angle", "FS": "full shot, head to toe", "IS": "insert shot, object focus"}
    tags.append(size_map.get(shot_size.upper(), "medium shot"))
    for char_name in (shot.get("characters") or [])[:2]:
        if char_name == "narrator":
            continue
        desc = CHARACTER_VISUAL_DESC.get(char_name)
        if desc:
            tags.append(desc)
    enriched = shot.get("enriched_visual_prompt") or shot.get("visual_prompt") or ""
    if enriched:
        tags.append(enriched.strip()[:150])
    tags.append(_infer_bg(shot))
    prompt = STYLE_PREFIX + ", ".join(tags)
    return prompt[:500]


def get_reference_path(shot):
    """스토리보드 레퍼런스 (씬 클러스터 대표 프레임)."""
    ref = shot.get("storyboard_reference") or {}
    frame_file = ref.get("frame_file")
    if frame_file:
        full = SCREENSHOT_ROOT / frame_file
        if full.exists():
            return full
    # storyboard_reference_modes fallback
    modes = shot.get("storyboard_reference_modes") or {}
    for mode in ("composition", "background", "character"):
        m = modes.get(mode) or {}
        ff = m.get("frame_file")
        if ff:
            full = SCREENSHOT_ROOT / ff
            if full.exists():
                return full
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--batch", type=int, default=0, help="Specific batch (1-based), 0=all")
    parser.add_argument("--resume", action="store_true", help="Skip already generated")
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--natural", action="store_true", help="Use natural language prompt instead of tags")
    args = parser.parse_args()

    manifest_path = PROJECT / args.manifest
    data = json.loads(manifest_path.read_text())
    all_shots = data["shots"]

    # cuts 배열이 있으면 cut 단위로 순회, 없으면 기존 shot 단위
    has_cuts = any(s.get("cuts") for s in all_shots)
    if has_cuts:
        target_shots = []
        for shot in all_shots:
            for cut in shot.get("cuts", []):
                # cut에 부모 shot 정보 주입
                cut["_parent_type"] = shot.get("type", "SKIT")
                cut["_parent_characters"] = shot.get("characters", [])
                cut["shot_id"] = cut.get("cut_id", shot["shot_id"])
                cut["shot_category"] = cut.get("cut_type", "scene")
                cut["characters"] = [cut["speaker"]] if cut.get("speaker") and cut["speaker"] != "narrator" else shot.get("characters", [])
                if not cut.get("enriched_visual_prompt"):
                    cut["enriched_visual_prompt"] = cut.get("visual_prompt", "")
                target_shots.append(cut)
        print(f"📊 Cut mode: {len(target_shots)} cuts from {len(all_shots)} scenes")
        # text_overlay 컷은 ComfyUI 생성 불필요 (Pencil Dev 후처리)
        target_shots = [c for c in target_shots if c.get("cut_type") != "text_overlay"]
    else:
        target_shots = [s for s in all_shots if s.get("characters") and s.get("shot_category") in ("scene", "reaction")]
        print(f"📊 Scene mode: {len(target_shots)} shots")

    ep_id = data.get("episode_id", "pilot")
    # 기본 출력: episodes 아래
    out_dir = PROJECT / "episodes" / ep_id / "storyboard" / "panels"
    out_dir.mkdir(parents=True, exist_ok=True)

    # ComfyUI output 아래에도 에피소드별 폴더 생성 (윈도우 탐색기 접근용)
    comfy_out = Path("/home/hugh/ComfyUI/app/output") / f"storyboard_{ep_id}"
    comfy_out.mkdir(parents=True, exist_ok=True)

    # 배치 분할
    batches = []
    for i in range(0, len(target_shots), args.batch_size):
        batches.append(target_shots[i:i + args.batch_size])

    if args.batch > 0:
        if args.batch > len(batches):
            print(f"Batch {args.batch} doesn't exist (max {len(batches)})")
            return
        batches = [batches[args.batch - 1]]
        print(f"Running batch {args.batch} only ({len(batches[0])} shots)")

    workflow = json.loads(WORKFLOW.read_text())
    client = ComfyUIClient()
    client.health_check(min_free_gb=1.0)

    total_generated = 0
    total_skipped = 0
    total_failed = 0
    t_start = time.time()

    for bi, batch in enumerate(batches):
        batch_num = args.batch if args.batch > 0 else bi + 1
        print(f"\n{'='*60}")
        print(f"Batch {batch_num}/{len(batches) if args.batch == 0 else args.batch}")
        print(f"Shots: {batch[0]['shot_id']}~{batch[-1]['shot_id']} ({len(batch)}장)")
        print(f"{'='*60}")

        for shot in batch:
            sid = shot["shot_id"]
            panel_path = out_dir / f"panel_{sid}.png"

            if args.resume and panel_path.exists():
                print(f"  [{sid}] SKIP (exists)")
                total_skipped += 1
                continue

            ref_path = get_reference_path(shot)
            # 레퍼런스 없어도 OK — ControlNet 꺼져있으면 blank 사용
            if not ref_path:
                ref_path = PROJECT / "assets" / "system" / "blank_white.png"
                if not ref_path.exists():
                    ref_path.parent.mkdir(parents=True, exist_ok=True)
                    from PIL import Image
                    Image.new("RGB", (1024, 1024), (255, 255, 255)).save(ref_path)

            golden = None
            for c in shot.get("characters", []):
                g = CHAR_DIR / c / f"{c}_golden.png"
                if g.exists():
                    golden = g
                    break

            try:
                ref_upload = client.upload_image(str(ref_path))
                overrides = {
                    "Load Reference Screenshot": {"image": ref_upload["name"]},
                    "Positive Prompt": {"text": build_prompt(shot, use_natural=getattr(args, 'natural', False))},
                    "Random Noise": {"noise_seed": 42069 + hash(sid) % 99999},
                }
                if golden:
                    overrides["Load Character Golden Shot"] = {"image": client.upload_image(str(golden))["name"]}
                else:
                    # 골든샷 없으면 blank 이미지 — 절대 외부 스크린샷을 IP-Adapter에 넣지 않음
                    blank_path = PROJECT / "assets" / "system" / "blank_white.png"
                    if not blank_path.exists():
                        blank_path.parent.mkdir(parents=True, exist_ok=True)
                        from PIL import Image
                        Image.new("RGB", (1024, 1024), (255, 255, 255)).save(blank_path)
                    overrides["Load Character Golden Shot"] = {"image": client.upload_image(str(blank_path))["name"]}

                t0 = time.time()
                pid = client.queue_workflow(workflow, overrides=overrides)
                result = client.wait_for_completion(pid, timeout=600, poll_interval=5)
                elapsed = time.time() - t0

                if result and result.get("images"):
                    img_data = client.get_image(result["images"][0])
                    panel_path.write_bytes(img_data)
                    # ComfyUI output에도 복사 (윈도우 탐색기 접근용)
                    comfy_copy = comfy_out / f"panel_{sid}.png"
                    comfy_copy.write_bytes(img_data)
                    total_generated += 1
                    print(f"  [{sid}] OK ({elapsed:.0f}s, {len(img_data)//1024}KB)")
                else:
                    total_failed += 1
                    print(f"  [{sid}] FAIL (no output)")
            except Exception as e:
                total_failed += 1
                print(f"  [{sid}] ERROR: {str(e)[:100]}")

    elapsed_total = time.time() - t_start
    print(f"\n{'='*60}")
    print(f"COMPLETE")
    print(f"  Generated: {total_generated}")
    print(f"  Skipped: {total_skipped}")
    print(f"  Failed: {total_failed}")
    print(f"  Time: {elapsed_total/60:.1f}min")
    print(f"  Output: {out_dir}/")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
