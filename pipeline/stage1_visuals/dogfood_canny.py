import os
import sys
import json
import argparse
from pathlib import Path

# 1. 동적 Project Root 설정 (환경 변수 PROJECT_ROOT가 있으면 사용, 없으면 기본값 사용)
DEFAULT_ROOT = "/home/hugh/youtube-studio-copy"
PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", DEFAULT_ROOT))

# Add pipeline/shared to sys.path
sys.path.insert(0, str(PROJECT_ROOT / "pipeline" / "shared"))

from comfyui_client import ComfyUIClient

def main(args):
    client = ComfyUIClient()
    
    # 1. Health Check
    print("Checking ComfyUI Health...")
    health = client.health_check(min_free_gb=1.0)
    print(f"Health check passed. Queue size: {health['comfyui_queue']}")

    # 2. Load Workflow
    workflow_path = PROJECT_ROOT / "workflows" / "legacy" / "nichijou_ipadapter_keyframe.json"
    with open(workflow_path, "r") as f:
        workflow = json.load(f)

    # 3. Upload Reference Image (명령줄에서 받은 경로 사용)
    ref_image_path = Path(args.image)
    if not ref_image_path.exists():
        print(f"Error: Reference image not found at {ref_image_path}")
        sys.exit(1)
        
    print(f"Uploading reference image: {ref_image_path}")
    upload_result = client.upload_image(str(ref_image_path))
    print(f"Uploaded: {upload_result['name']}")

    # 4. Define Overrides
    # Dynamic prompt construction based on camera shot
    shot_prompts = {
        "ECU": "extreme close-up, highly detailed face, intense emotion focus, ",
        "CU": "close-up shot, single character focus, clear facial expression, ",
        "OTS": "over-the-shoulder shot, looking at other character, depth of field, ",
        "MS": "medium shot, upper body, clear body language, ",
        "2-Shot": "two-shot, two characters facing each other, balanced composition, ",
        "WS": "wide shot, establishing shot, showing full environment and background, "
    }
    
    base_prompt = "flat colors, detailed anime screencap, cinematic anime style, dramatic lighting, vibrant colors."
    shot_prefix = shot_prompts.get(args.shot, "")
    intent_prefix = f"Director intent: {args.intent}. " if args.intent else ""
    
    final_prompt = f"{intent_prefix}{shot_prefix}{base_prompt}"
    print(f"Generated Prompt: {final_prompt}")

    overrides = {
        "Load Reference Screenshot": {
            "image": upload_result['name']
        },
        "Positive Prompt": {
            "text": final_prompt
        },
        "🎬 Director's Note": {
            "text": f"Director's Intent: {args.intent}\nCamera Shot: {args.shot}\n\n* This note documents the cinematic purpose of this workflow instance. Always adhere to 'One Point Per Shot'."
        }
    }

    # 5. Queue Workflow
    print("Queueing workflow...")
    try:
        prompt_id = client.queue_workflow(workflow, overrides=overrides)
        print(f"Prompt ID: {prompt_id}")

        # 6. Wait for Completion
        print("Waiting for generation (this may take 5-10 minutes)...")
        result = client.wait_for_completion(prompt_id, timeout=900, poll_interval=10.0)
        print("Generation complete!")

        # 7. Save Outputs
        output_dir = PROJECT_ROOT / "work" / "dogfood_outputs"
        output_dir.mkdir(parents=True, exist_ok=True)

        for node_id, node_out in result['outputs'].items():
            if 'images' in node_out:
                for img_info in node_out['images']:
                    img_bytes = client.get_image(img_info)
                    filename = f"node_{node_id}_{img_info['filename']}"
                    save_path = output_dir / filename
                    save_path.write_bytes(img_bytes)
                    print(f"Saved: {save_path}")

    except RuntimeError as e:
        print(f"ERROR during execution: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    # 인자 파싱 (Argument Parsing) 설정
    parser = argparse.ArgumentParser(description="Run ComfyUI Canny ControlNet pipeline with cinematic intent.")
    parser.add_argument(
        "-i", "--image", 
        required=True, 
        type=str, 
        help="Path to the reference image."
    )
    parser.add_argument(
        "--intent", 
        type=str, 
        default="",
        help="Director's intent for the cut (e.g., 'Angry confrontation')."
    )
    parser.add_argument(
        "--shot", 
        type=str, 
        choices=["ECU", "CU", "OTS", "MS", "2-Shot", "WS"],
        default="MS",
        help="Camera shot type (e.g., CU, WS, OTS)."
    )
    args = parser.parse_args()
    
    main(args)
