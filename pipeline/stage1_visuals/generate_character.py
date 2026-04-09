#!/usr/bin/env python3
"""Character asset generation pipeline via ComfyUI API.

Generates 2 asset types per character:
  - golden: Full-body chibi character (1024x1024 → 4x AnimeSharp → 2048x2048)
  - expression: Facial expression variants (1024x1024 → 2048x2048)

Model: Flux 1 Dev GGUF + Juustagram Chibi LoRA @ 1.0
Style: Azur Lane Slow Ahead anchor + flat color cel shading

Usage:
  python generate_character.py --character america --type golden
  python generate_character.py --character korea --type all
  python generate_character.py --batch
  python generate_character.py --manifest episodes/ep01/manifest.json
"""

import argparse
import sys
import time
from pathlib import Path

# ─── Project paths ───
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PIPELINE_SHARED = PROJECT_ROOT / "pipeline" / "shared"
sys.path.insert(0, str(PIPELINE_SHARED))

from gpu_utils import check_gpu
from comfyui_client import ComfyUIClient, load_workflow

# ─── SSOT import ───
from character_config import STYLE_ANCHOR, CHARACTERS, CHARACTER_VISUAL_DESC, SEED, LORA_STRENGTH

# ─── Model config ───
WORKFLOW_PATH = PROJECT_ROOT / "workflows" / "legacy" / "golden_chibi.json"
UPSCALE_SRC_PATH = PROJECT_ROOT / "workflows" / "legacy" / "storyboard_quick.json"

# ─── Generation Presets ───
PRESETS = {
    "golden":     {"width": 1024, "height": 1024, "steps": 30, "cfg": 3.5},
    "expression": {"width": 1024, "height": 1024, "steps": 30, "cfg": 3.5},
}

# CHARACTERS, CHARACTER_VISUAL_DESC — character_config.py SSOT에서 import됨


def build_workflow(preset_name: str = "golden") -> dict:
    """golden_chibi.json + AnimeSharp 4x 업스케일러 워크플로우 구성."""
    import json
    preset = PRESETS[preset_name]
    wf = json.loads(WORKFLOW_PATH.read_text())

    wf["26"]["inputs"]["guidance"] = preset["cfg"]
    wf["28"]["inputs"]["steps"] = preset["steps"]
    wf["7"]["inputs"]["width"] = preset["width"]
    wf["7"]["inputs"]["height"] = preset["height"]

    # AnimeSharp 4x 업스케일러 추가
    wf_upscale = json.loads(UPSCALE_SRC_PATH.read_text())
    wf["40"] = wf_upscale["40"]  # UpscaleModelLoader (4x-AnimeSharp.pth)
    wf["41"] = wf_upscale["41"]  # ImageUpscaleWithModel
    wf["42"] = wf_upscale["42"]  # ImageScale
    wf["42"]["inputs"]["width"] = 2048
    wf["42"]["inputs"]["height"] = 2048
    wf["14"]["inputs"]["images"] = ["42", 0]

    return wf


def generate_with_comfyui(client: ComfyUIClient, char_desc: str, preset_name: str,
                          output_path: Path, label: str = "", seed: int = SEED,
                          lora_strength: float = LORA_STRENGTH) -> tuple[bool, float]:
    """ComfyUI API로 단일 이미지 생성 (Chibi v2).

    Returns: (success, elapsed_seconds)
    """
    preset = PRESETS[preset_name]
    # 스타일 앵커 + 캐릭터 디스크립션 결합
    full_prompt = f"{STYLE_ANCHOR}, {char_desc}"

    print(f"  Generating: {label or output_path.stem}")
    print(f"    Resolution: {preset['width']}x{preset['height']}, Steps: {preset['steps']}")
    print(f"    Prompt: {full_prompt[:90]}...")

    t0 = time.time()

    try:
        workflow = build_workflow(preset_name)

        overrides = {
            "Positive Prompt": {"text": full_prompt},
            "Random Noise": {"noise_seed": seed},
        }

        prompt_id = client.queue_workflow(workflow, overrides)
        print(f"    Queued: {prompt_id}")

        result = client.wait_for_completion(prompt_id, timeout=600)
        elapsed = time.time() - t0

        if result["images"]:
            img_data = client.get_image(result["images"][0])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(img_data)
            file_size = output_path.stat().st_size / 1024
            print(f"    OK: {output_path} ({file_size:.0f} KB, {elapsed:.1f}s)")
            return True, elapsed
        else:
            print(f"    FAIL: No images in result after {elapsed:.1f}s")
            return False, elapsed

    except Exception as e:
        elapsed = time.time() - t0
        print(f"    FAIL after {elapsed:.1f}s: {e}")
        return False, elapsed


def generate_character(client: ComfyUIClient, character_name: str,
                       asset_type: str, output_dir: Path, seed: int = SEED,
                       lora_strength: float = LORA_STRENGTH) -> list:
    """Generate assets for a single character via ComfyUI.

    Returns: list of (success, time, path) tuples
    """
    if character_name not in CHARACTERS:
        print(f"ERROR: Unknown character '{character_name}'")
        print(f"  Available: {', '.join(CHARACTERS.keys())}")
        sys.exit(1)

    char_data = CHARACTERS[character_name]
    char_dir = Path(output_dir) / character_name
    char_dir.mkdir(parents=True, exist_ok=True)

    results = []
    types_to_generate = []

    if asset_type in ("golden", "all"):
        types_to_generate.append("golden")
    if asset_type in ("expression", "all"):
        types_to_generate.append("expression")

    print()
    print("=" * 60)
    print(f"  Character: {character_name.upper()}")
    print(f"  Types: {', '.join(types_to_generate)}")
    print(f"  Output: {char_dir}")
    print("=" * 60)

    for gen_type in types_to_generate:
        if gen_type == "golden":
            out_path = char_dir / f"{character_name}_golden.png"
            label = f"{character_name}/golden"
            success, t = generate_with_comfyui(
                client, char_data["golden"], "golden", out_path, label, seed, lora_strength)
            results.append((success, t, out_path))

        elif gen_type == "expression":
            for expr_name, expr_prompt in char_data.get("expressions", {}).items():
                out_path = char_dir / f"{character_name}_expr_{expr_name}.png"
                label = f"{character_name}/expr/{expr_name}"
                success, t = generate_with_comfyui(
                    client, expr_prompt, "expression", out_path, label, seed, lora_strength)
                results.append((success, t, out_path))

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Character asset generation via ComfyUI (Flux 1 Dev + Juustagram Chibi)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --character america --type golden
  %(prog)s --character denmark --type all
  %(prog)s --batch
  %(prog)s --manifest episodes/ep01/manifest.json
        """,
    )

    parser.add_argument("--character", "-c", type=str, choices=list(CHARACTERS.keys()),
                        help="Character (country) to generate")
    parser.add_argument("--type", "-t", type=str,
                        choices=["golden", "expression", "all"], default="all",
                        help="Asset type to generate (default: all)")
    parser.add_argument("--output-dir", "-o", type=str, default=None,
                        help="Output directory (default: assets/characters/)")
    parser.add_argument("--batch", "-b", action="store_true",
                        help="Generate ALL assets for ALL characters")
    parser.add_argument("--seed", "-s", type=int, default=SEED,
                        help=f"Random seed (default: {SEED})")
    parser.add_argument("--manifest", type=str, default=None,
                        help="Manifest JSON — auto-extract characters to generate")
    parser.add_argument("--comfyui-url", type=str, default="http://127.0.0.1:8188",
                        help="ComfyUI server URL")
    parser.add_argument("--lora-strength", type=float, default=LORA_STRENGTH,
                        help=f"Flat Anime LoRA strength (default: {LORA_STRENGTH})")

    args = parser.parse_args()

    # ─── GPU + ComfyUI pre-flight ───
    print("=" * 60)
    print("  TOO GLOBAL TO HANDLE — Character Asset Pipeline")
    print("  Model: Flux 1 Dev + Juustagram Chibi LoRA @ 1.0")
    print("  Style: Azur Lane Slow Ahead anchor")
    print("=" * 60)
    print()

    # GPU 상태 체크
    print("[Pre-flight] GPU status check...")
    check_gpu(verbose=True)
    print()

    # ComfyUI 서버 체크
    client = ComfyUIClient(url=args.comfyui_url)
    print("[Pre-flight] ComfyUI server check...")
    client.health_check(min_free_gb=4.0)
    print()

    # LoRA strength override
    lora_strength = args.lora_strength

    # ─── Resolve output directory ───
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = PROJECT_ROOT / "assets" / "characters"
    output_dir.mkdir(parents=True, exist_ok=True)

    # ─── Determine characters to generate ───
    if args.manifest:
        from manifest_loader import load_manifest, get_characters_from_manifest
        manifest = load_manifest(args.manifest)
        characters_to_run = [c for c in get_characters_from_manifest(manifest) if c in CHARACTERS]
        asset_type = "all"
        print(f"[MANIFEST] Characters from manifest: {characters_to_run}")
    elif args.batch:
        characters_to_run = list(CHARACTERS.keys())
        asset_type = "all"
        print(f"BATCH MODE: {len(characters_to_run)} characters, all asset types")
    elif args.character:
        characters_to_run = [args.character]
        asset_type = args.type
    else:
        parser.error("Either --character, --batch, or --manifest is required")
        return

    # ─── Generate ───
    all_results = []
    total_start = time.time()

    for i, char_name in enumerate(characters_to_run):
        # GPU 상태 체크 (매 캐릭터 전)
        print(f"\n[GPU Check] Before {char_name} ({i+1}/{len(characters_to_run)})...")
        check_gpu(verbose=True)

        char_results = generate_character(client, char_name, asset_type, output_dir, args.seed, lora_strength)
        all_results.extend([(char_name, *r) for r in char_results])

    total_time = time.time() - total_start

    # ─── Summary ───
    print()
    print("=" * 60)
    print("  GENERATION SUMMARY")
    print("=" * 60)
    print()

    passed = sum(1 for r in all_results if r[1])
    failed = len(all_results) - passed

    for char_name, success, gen_time, path in all_results:
        status = "OK" if success else "FAIL"
        print(f"  [{status}] {char_name:12s} — {path.name:40s} ({gen_time:.1f}s)")

    print()
    print(f"  Total images: {len(all_results)}")
    print(f"  Passed: {passed} | Failed: {failed}")
    print(f"  Total time: {total_time:.1f}s ({total_time / 60:.1f} min)")
    print(f"  Output: {output_dir}")
    print()

    # Final GPU status
    print("[Post-flight] Final GPU status:")
    check_gpu(verbose=True)

    if failed > 0:
        print(f"\n  WARNING: {failed} generation(s) failed")
        sys.exit(1)
    else:
        print("\n  All generations completed successfully")


if __name__ == "__main__":
    main()
