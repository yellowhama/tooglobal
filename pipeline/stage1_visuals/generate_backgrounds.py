#!/usr/bin/env python3
"""Generate anime-style background images via ComfyUI API.

Creates 5 scene backgrounds at 1920x1080 (generated at 1344x768, upscaled):
  - bg-school-hallway.png    (복도)
  - bg-confessional-room.png (고백룸)
  - bg-infographic.png       (인포그래픽)
  - bg-comedy-scene.png      (코미디)
  - bg-tension-scene.png     (긴장)

Model: Flux 1 Dev + Juustagram Chibi LoRA @ 1.0 (via ComfyUI)
No diffusers — all generation goes through ComfyUI HTTP API.

Usage:
    python generate_backgrounds.py
    python generate_backgrounds.py --verify
    python generate_backgrounds.py --bg bg-school-hallway
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

WORKFLOW_PATH = PROJECT_ROOT / "workflows" / "legacy" / "storyboard_quick.json"
OUTPUT_DIR = PROJECT_ROOT / "assets" / "backgrounds"
SEED = 42
LORA_STRENGTH = 1.0  # Juustagram Chibi LoRA — full strength for style consistency

# Target final resolution
FINAL_W = 1920
FINAL_H = 1080

# Background definitions
BACKGROUNDS = {
    "bg-world-map": {
        "prompt": (
            "juustagram style, chibi, cute illustrated world map, pastel colors, "
            "simple cartoon continents, soft watercolor texture, "
            "flat color cel shading, thick black outlines, "
            "no people, clean anime art, simple background"
        ),
    },
    "bg-ocean": {
        "prompt": (
            "juustagram style, chibi, simple blue ocean with gentle waves, "
            "pastel blue gradient sky, soft clouds, cute simple style, "
            "flat color cel shading, thick black outlines, "
            "no people, clean anime art, simple background"
        ),
    },
    "bg-conference-table": {
        "prompt": (
            "juustagram style, chibi, simple meeting room interior, large round table, "
            "pastel colored chairs, soft warm lighting, cute minimalist style, "
            "flat color cel shading, thick black outlines, "
            "no people, clean anime art, simple background"
        ),
    },
    "bg-spotlight": {
        "prompt": (
            "juustagram style, chibi, dark background with single spotlight from above, "
            "dramatic but cute lighting, simple dark gradient, confessional room feel, "
            "flat color cel shading, thick black outlines, "
            "no people, clean anime art, simple background"
        ),
    },
    "bg-versus": {
        "prompt": (
            "juustagram style, chibi, split screen background red vs blue, "
            "dynamic diagonal split, pastel red and pastel blue halves, "
            "versus battle background, simple geometric shapes, "
            "flat color cel shading, thick black outlines, "
            "no people, clean anime art, simple background"
        ),
    },
    "bg-news-desk": {
        "prompt": (
            "juustagram style, chibi, simple cute news desk background, "
            "pastel colored desk, small monitors, studio lights, "
            "flat color cel shading, thick black outlines, "
            "no people, clean anime art, simple background"
        ),
    },
    "bg-school-hallway": {
        "prompt": (
            "anime background art, school hallway interior, long corridor perspective, "
            "cherry blossom visible through windows, warm afternoon lighting, "
            "lockers on walls, polished wooden floor, soft shadows, "
            "no people, empty hallway, studio ghibli style, detailed background, "
            "vibrant colors, clean lineart"
        ),
    },
    "bg-confessional-room": {
        "prompt": (
            "anime background art, cozy small room interior, interview room setup, "
            "single chair in center, soft warm spotlight from above, "
            "dark cozy background with wood panels, bokeh light effect, "
            "warm amber lighting, intimate atmosphere, no people, "
            "anime style, detailed, clean"
        ),
    },
    "bg-infographic": {
        "prompt": (
            "anime background art, modern presentation screen, dark navy blue gradient, "
            "subtle grid lines, holographic data display aesthetic, "
            "futuristic control room, glowing blue accent lights, "
            "tech interface background, no text, no people, "
            "clean digital art style"
        ),
    },
    "bg-comedy-scene": {
        "prompt": (
            "anime background art, bright colorful school classroom, "
            "desks and chairs, large windows with blue sky, "
            "cherry blossom trees outside, bright cheerful lighting, "
            "pastel colors, cute atmosphere, no people, "
            "slice of life anime background, vibrant, detailed"
        ),
    },
    "bg-tension-scene": {
        "prompt": (
            "anime background art, dramatic dark corridor, ominous red lighting, "
            "cracked walls, thunder visible through broken window, "
            "dramatic shadows, intense atmosphere, dark and moody, "
            "no people, anime style, detailed background art, "
            "dark color palette, high contrast"
        ),
    },
    "bg-snack-bar-alleyway": {
        "prompt": (
            "anime background art, narrow brick alleyway between school buildings, "
            "dim afternoon lighting, cluttered with some empty lunch crates, "
            "vines on brick walls, cobblestone floor, perspective view leading to a gate, "
            "quiet and secluded, anime style, detailed, nichijou style"
        ),
    },
    "bg-alleyway-gate": {
        "prompt": (
            "anime background art, closeup of a rusty iron gate in a brick alley, "
            "large heavy padlock on the gate, weathered metal texture, "
            "dim lighting with a single street lamp above, "
            "trash cans nearby, moody atmosphere, no people, anime style, detailed"
        ),
    },
}


def generate_backgrounds(client: ComfyUIClient, bg_names: list = None,
                         verify: bool = False, seed: int = SEED):
    """Generate backgrounds via ComfyUI API."""
    if bg_names is None:
        bg_names = list(BACKGROUNDS.keys())

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for name in bg_names:
        if name not in BACKGROUNDS:
            print(f"  SKIP: Unknown background '{name}'")
            continue

        config = BACKGROUNDS[name]

        # GPU check before each background
        print(f"\n[GPU Check] Before {name}...")
        check_gpu(verbose=True)

        print(f"\n{'─' * 60}")
        print(f"  Generating: {name}")
        print(f"  Prompt: {config['prompt'][:80]}...")

        t0 = time.time()

        try:
            workflow = load_workflow(str(WORKFLOW_PATH))

            # Handle Image References (Always provide a fallback to avoid validation errors)
            blank_path = PROJECT_ROOT / "assets" / "system" / "blank_white.png"
            if not blank_path.exists():
                blank_path.parent.mkdir(parents=True, exist_ok=True)
                from PIL import Image
                Image.new("RGB", (1024, 1024), (255, 255, 255)).save(blank_path)

            # nichijou_ipadapter_keyframe.json 노드 타이틀 기준
            overrides = {
                "Positive Prompt": {"text": config["prompt"]},
                "Latent Image (1344x768)": {"width": 1344, "height": 768},
                "Random Noise": {"noise_seed": seed},
                "Scheduler": {"steps": 20},
                "Flux Guidance": {"guidance": 3.5},
                "Flat Anime LoRA": {
                    "strength_model": LORA_STRENGTH,
                    "strength_clip": LORA_STRENGTH,
                },
                "Save Keyframe": {"filename_prefix": name},
                "Load Character Golden Shot": {"image": str(blank_path.absolute())},
                "Load Reference Screenshot": {"image": str(blank_path.absolute())},
            }

            prompt_id = client.queue_workflow(workflow, overrides)
            print(f"  Queued: {prompt_id}")

            result = client.wait_for_completion(prompt_id, timeout=600)
            elapsed = time.time() - t0

            if result["images"]:
                img_data = client.get_image(result["images"][0])

                # Save raw ComfyUI output, then upscale to 1920x1080
                from PIL import Image
                import io
                raw_img = Image.open(io.BytesIO(img_data))
                final_img = raw_img.resize((FINAL_W, FINAL_H), Image.Resampling.LANCZOS)

                out_path = OUTPUT_DIR / f"{name}.png"
                final_img.save(out_path, "PNG")
                fsize = out_path.stat().st_size / 1024

                print(f"  OK: {out_path.name} ({fsize:.0f} KB, {elapsed:.1f}s)")
                print(f"  Size: {final_img.size[0]}x{final_img.size[1]}")
                results.append((name, out_path, fsize, final_img.size))
            else:
                print(f"  FAIL: No images returned ({elapsed:.1f}s)")

        except Exception as e:
            elapsed = time.time() - t0
            print(f"  FAIL after {elapsed:.1f}s: {e}")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Background Generation: {len(results)}/{len(bg_names)} succeeded")
    print("=" * 60)
    for name, path, fsize, size in results:
        print(f"  {name}.png  {fsize:>8.0f} KB  {size[0]}x{size[1]}")

    # Verification
    if verify and results:
        print(f"\n{'=' * 60}")
        print("VISUAL VERIFICATION")
        print("=" * 60)
        from PIL import Image
        for name, path, _, _ in results:
            img = Image.open(path)
            px = list(img.getdata())
            blacks = sum(1 for p in px if sum(p[:3]) < 30)
            total = len(px)
            black_pct = blacks * 100 // total
            r_vals = [p[0] for p in px[:1000]]
            g_vals = [p[1] for p in px[:1000]]
            b_vals = [p[2] for p in px[:1000]]
            variance = (max(r_vals) - min(r_vals)) + (max(g_vals) - min(g_vals)) + (max(b_vals) - min(b_vals))

            status = "PASS" if black_pct < 50 and variance > 100 else "FAIL"
            print(f"  [{status}] {name}.png — black: {black_pct}%, color variance: {variance}")

    # Post-flight GPU check
    print(f"\n[Post-flight] GPU status:")
    check_gpu(verbose=True)


def main():
    parser = argparse.ArgumentParser(
        description="Generate backgrounds via ComfyUI (Flux 1 Dev + Juustagram Chibi)")
    parser.add_argument("--verify", action="store_true", help="Run visual verification")
    parser.add_argument("--bg", type=str, action="append",
                        help="Specific background(s) to generate. Can repeat.")
    parser.add_argument("--comfyui-url", type=str, default="http://127.0.0.1:8188",
                        help="ComfyUI server URL")
    parser.add_argument("--seed", type=int, default=SEED, help="Random seed")
    args = parser.parse_args()

    print("=" * 60)
    print("  TOO GLOBAL TO HANDLE — Background Generation Pipeline")
    print("  Model: Flux 1 Dev + Juustagram Chibi via ComfyUI")
    print("=" * 60)
    print()

    # Pre-flight
    print("[Pre-flight] GPU status check...")
    check_gpu(verbose=True)
    print()

    client = ComfyUIClient(url=args.comfyui_url)
    print("[Pre-flight] ComfyUI server check...")
    client.health_check(min_free_gb=4.0)
    print()

    generate_backgrounds(client, bg_names=args.bg, verify=args.verify, seed=args.seed)


if __name__ == "__main__":
    main()
