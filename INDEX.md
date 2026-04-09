# Repository Index (youtube-studio-copy)

Windows path (WSL): `\\wsl.localhost\Ubuntu-22.04\home\hugh\youtube-studio-copy\`

## Start Here

- `QUICKSTART.md` — fastest way to run key parts of the pipeline
- `ONBOARDING.md` — environment + models + expected outputs
- `WORKFLOW_GUIDE.md` — ComfyUI workflow conventions, node titles, overrides, and rendering habits
- `workflows/README.md` — canonical storyboard workflow order, file classes, and execution rules
- `HANDOFF_3STAGE_PIPELINE.md` — stage-sequential storyboard/panel pipeline spec + Kontext slot + next steps

## Key Code Paths

- `pipeline/shared/comfyui_client.py` — ComfyUI HTTP client; queue/wait/download; title-based overrides
- `pipeline/shared/prompt_compiler_llm.py` — the only prompt generator; manifest uses `compiled_prompt`
- `pipeline/shared/scene_cluster.py` — scene_clusters reference search (for screenshot reference selection)
- `pipeline/stage1_visuals/decompose_cuts.py` — script to split scenes into cuts/shots (metadata only)
- `pipeline/stage1_visuals/generate_storyboard_full.py` — current single-pass renderer (reference for 3-stage renderer)
- `pipeline/stage1_visuals/generate_keyframes.py` — IP-Adapter + ControlNet patterns
- `pipeline/stage1_visuals/generate_panels_3stage.py` — canonical runner (Stage1 pass -> Stage2 pass -> optional Stage2.5 Kontext -> Stage3 pass; uses `.render.lock` to block concurrent runs)

## Workflows (ComfyUI)

- `workflows/stage1_composition.json` — Stage 1 layout (Depth ControlNet only)
- `workflows/stage2_character.json` — Stage 2 character (IP-Adapter + light Depth CN)
- `workflows/stage3_upscale.json` — Stage 3 upscale (AnimeSharp 4x -> 1920x1080)
- `workflows/legacy/storyboard_quick.json` — legacy all-in-one (CN + IP-Adapter + upscale) baseline
- `workflows/legacy/golden_chibi.json` — legacy character generation workflow (IP-Adapter route)
- `workflows/legacy/img2img_refine.json` — legacy optional img2img refinement workflow

Reference/Research workflows:
- `workflows/reference/CRT_FLUX SUPER (v4.3).json` — controlnet sampler injection + face enhancement (subgraph-heavy)
- `workflows/experimental/flux_lots_of_tweaks.json` — detailers-heavy experimental workflow

## Data

- `episodes/ep01/manifest.json` — 207 cuts; each cut has `compiled_prompt`
- `context/scene_clusters.json` — 5,518 clustered reference scenes
- `context/SHOW_BIBLE.md` — tone/style rules and constraints
