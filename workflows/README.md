# Workflows Index

Canonical storyboard/panel pipeline files live in this directory root.

## Canonical Order

1. `stage1_composition.json`
   - Stage 1 layout/composition
   - Depth ControlNet only
   - Input: screenshot reference
   - Output: `storyboard/stage1_layout/*_layout.png`

2. `stage2_character.json`
   - Stage 2 character pass
   - Stage 1 result as ControlNet reference
   - Golden shot via IP-Adapter
   - Output: `storyboard/stage2_character/*_char.png`

3. `stage2_5_kontext.json`
   - Optional Stage 2.5 consistency/detail fix
   - Input: Stage 2 result
   - Output: `storyboard/stage2_kontext/*_kontext.png`
   - Status: not present by default in this repo snapshot
   - Requirement: export an API-format workflow from ComfyUI

4. `stage3_upscale.json`
   - Stage 3 final upscale
   - AnimeSharp 4x -> 1920x1080
   - No center crop
   - Output: `storyboard/panels/panel_*.png`

## Execution Rules

- Do not run stages in parallel.
- Run full Stage 1 pass first, then Stage 2, then optional Stage 2.5, then Stage 3.
- `pipeline/stage1_visuals/generate_panels_3stage.py` is the canonical runner.
- The runner enforces a lock file at `episodes/<ep>/storyboard/.render.lock`.

## File Classes

- Canonical: `stage1_composition.json`, `stage2_character.json`, `stage3_upscale.json`
- Optional canonical slot: `stage2_5_kontext.json`
- Legacy baseline: `legacy/storyboard_quick.json`, `legacy/golden_chibi.json`, `legacy/img2img_refine.json`
- Experimental/reference only: `reference/*.json`, `experimental/flux_lots_of_tweaks.json`, `legacy/nichijou_ipadapter_keyframe.json`, `legacy/regional_prompting.json`

## Important Caveat

`reference/Flux Kontext.json` is a ComfyUI UI graph, not an API prompt workflow.
It is useful as a source graph, but the runner cannot execute it directly.
