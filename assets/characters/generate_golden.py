#!/usr/bin/env python3
"""골든샷 생성 스크립트 — Juustagram Chibi + Azur Lane Slow Ahead 스타일.

Usage:
    python generate_golden.py                    # 전체 8개국
    python generate_golden.py --char america     # 특정 캐릭터만
    python generate_golden.py --seed 65700       # 시드 변경
"""
import json, sys, argparse, time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "pipeline" / "shared"))
from comfyui_client import ComfyUIClient

# === 확정 설정 ===
SEED = 65700
WORKFLOW = PROJECT / "workflows" / "legacy" / "golden_chibi.json"
UPSCALE_SRC = PROJECT / "workflows" / "legacy" / "storyboard_quick.json"
DST = Path(__file__).resolve().parent

STYLE = (
    "juustagram style, chibi, azur lane slow ahead style, "
    "flat color cel shading, thick black outlines, pastel color palette, "
    "simple round face, large head small body proportions, "
    "white background, clean anime art"
)

CHARS = {
    "america":  "1girl, solo, blonde wavy hair, blue eyes, cowboy hat, red crop top, denim shorts, cowboy boots, star badge, confident smirk, hands on hips, standing, full body",
    "iran":     "1girl, solo, long black hair, green eyes, loose green headscarf, off-shoulder dark green top, black skirt, red rose accessory, flag pin, defiant expression, arms crossed, standing, full body",
    "iraq":     "1girl, solo, black wavy hair, brown eyes, beige off-shoulder sweater, brown mini skirt, gold earrings, flag pin, worried expression, hands clasped, standing, full body",
    "uk":       "1girl, solo, ginger red twintails, green eyes, open navy blazer, white cropped blouse, plaid mini skirt, flag pin, smug expression, holding teacup, standing, full body",
    "germany":  "1girl, solo, blonde twin braids, blue eyes, black corset top, red flared skirt, white off-shoulder blouse, flag pin, nervous expression, hands together, standing, full body",
    "pakistan":  "1girl, solo, dark brown hair bun, brown eyes, sky blue sleeveless tunic, white leggings, light scarf, flag pin, gentle smile, holding paper, standing, full body",
    "china":    "1girl, solo, black double buns, red eyes, sleeveless red qipao mini dress, gold trim, flag pin, calm smile, holding teacup, standing, full body",
    "korea":    "1girl, solo, long black hair blue ribbon, brown eyes, pink crop top, blue pleated skirt, gold accessory, flag pin, cheerful smile, hands together, standing, full body",
}


def build_workflow():
    """IP-Adapter/CN 제거 워크플로우 + AnimeSharp 업스케일러."""
    wf = json.loads(WORKFLOW.read_text())
    wf["26"]["inputs"]["guidance"] = 3.5
    wf["28"]["inputs"]["steps"] = 30

    # 업스케일러 추가 (storyboard_quick에서 가져옴)
    wf_orig = json.loads(UPSCALE_SRC.read_text())
    wf["40"] = wf_orig["40"]  # UpscaleModelLoader (4x-AnimeSharp.pth)
    wf["41"] = wf_orig["41"]  # ImageUpscaleWithModel
    wf["42"] = wf_orig["42"]  # ImageScale
    wf["42"]["inputs"]["width"] = 2048
    wf["42"]["inputs"]["height"] = 2048
    wf["14"]["inputs"]["images"] = ["42", 0]

    return wf


def main():
    parser = argparse.ArgumentParser(description="골든샷 생성")
    parser.add_argument("--char", default=None, help="특정 캐릭터만 (e.g. america)")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    targets = {args.char: CHARS[args.char]} if args.char else CHARS
    workflow = build_workflow()
    client = ComfyUIClient()

    for i, (name, desc) in enumerate(targets.items()):
        prompt = f"{STYLE}, {desc}"
        overrides = {
            "Positive Prompt": {"text": prompt},
            "Random Noise": {"noise_seed": args.seed},
        }
        pid = client.queue_workflow(workflow, overrides=overrides)
        result = client.wait_for_completion(pid, timeout=600, poll_interval=5)

        out_dir = DST / name
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{name}_golden.png"

        if result and result.get("images"):
            out_path.write_bytes(client.get_image(result["images"][0]))
            print(f"[{i+1}/{len(targets)}] {name} OK → {out_path}")
        else:
            print(f"[{i+1}/{len(targets)}] {name} FAIL")

    print("\nDone!")


if __name__ == "__main__":
    main()
