# ComfyUI 워크플로우 가이드

> 상태: legacy guide
> 현재 canonical storyboard pipeline은 `workflows/stage1_composition.json` -> `workflows/stage2_character.json` -> optional `workflows/stage2_5_kontext.json` -> `workflows/stage3_upscale.json`
> 이 문서는 구세대 단일패스 워크플로우 참고 자료로 유지한다.

---

## 확정 설정 (Source of Truth: CHARACTER_GENERATION_SPEC.md)

| 항목 | 값 |
|---|---|
| Base Model | `flux1-dev-Q5_K_S.gguf` (Flux 1 Dev) |
| LoRA | `Flat_Anime_Style_-_FLUX-000009.safetensors` @ 0.8 |
| 트리거 워드 | `flat anime` |
| CLIP | `clip_l.safetensors` + `t5-v1_1-xxl-encoder-Q5_K_M.gguf` (type: flux) |
| VAE | `ae.safetensors` |
| CFG (FluxGuidance) | 3.5 |
| Sampler | SamplerCustomAdvanced (euler, normal) |
| Steps | 25 (캐릭터) / 20 (키프레임) |
| 생성 해상도 | 1344×768 (가로) / 768×1344 (세로 캐릭터) |
| 업스케일 | 4x-AnimeSharp → 1920×1080 |
| IP-Adapter | SigLIP-SO400m weight 0.4, end 0.4 |
| ControlNet | flux-controlnet-union-pro, Canny 0.55 |
| ModelSamplingFlux | max_shift=1.15, base_shift=0.5 |

---

## 워크플로우 파일 목록

| 파일 | 용도 | 상태 |
|---|---|---|
| `legacy/nichijou_ipadapter_keyframe.json` | **legacy 기준 워크플로우** — 키프레임/스토리보드/캐릭터/배경 공용 | 보관 |
| `legacy/storyboard_quick.json` | nichijou 복사본 (동일 설정) | 보관 |
| `legacy/img2img_refine.json` | img2img 보정용 | 보조 |
| `legacy/regional_prompting.json` | 멀티캐릭터 리전 프롬프팅 | 보조 |

### 삭제된 워크플로우 (사용 금지)
- ~~`klein9b_character.json`~~ — Klein 9B 모델 사용, 현재 파이프라인과 불일치
- ~~`klein9b_background.json`~~ — 위와 동일
- ~~`klein9b_canny_composition.json`~~ — 위와 동일

---

## 노드 구조 (26노드)

```
[1] Load Flux 1 Dev GGUF (UnetLoaderGGUF)
  → [4] Flat Anime LoRA (LoraLoader @ 0.8)
    → [32] Apply IP-Adapter (ApplyIPAdapterFlux, weight 0.4)
      → [27] Model Sampling Flux (max_shift=1.15, base_shift=0.5)
        → [33] Guider (BasicGuider)

[2] Dual CLIP Loader (DualCLIPLoaderGGUF, clip_l + t5-xxl)
  → [5] Positive Prompt (CLIPTextEncode)
    → [26] Flux Guidance (guidance=3.5)
      → [24] Apply ControlNet (strength=0.55)
        → [33] Guider

[20] Load Reference Screenshot (LoadImage)
  → [21] Canny Preprocessor (low=0.15, high=0.25)
    → [24] Apply ControlNet

[30] Load Character Golden Shot (LoadImage)
  → [32] Apply IP-Adapter

[31] Load IP-Adapter (IPAdapterFluxLoader, SigLIP)
  → [32] Apply IP-Adapter

[25] Random Noise → [12] Sampler (Advanced)
[28] Scheduler (steps=20) → [12]
[29] Sampler Select (euler) → [12]
[7] Latent Image (1344x768) → [12]

[12] Sampler → [13] VAE Decode (ae.safetensors)
  → [41] 4x Upscale (AnimeSharp)
    → [42] Scale to 1920x1080
      → [14] Save Keyframe
```

---

## 스크립트별 오버라이드 매핑

### generate_keyframes.py (키프레임)
```python
overrides = {
    "Load Reference Screenshot": {"image": ref_upload["name"]},
    "Positive Prompt": {"text": prompt_text},
    "Random Noise": {"noise_seed": seed},
    "Load Character Golden Shot": {"image": golden_upload["name"]},  # IP-Adapter
}
```

### generate_character.py (캐릭터)
```python
overrides = {
    "Positive Prompt": {"text": prompt},
    "Latent Image (1344x768)": {"width": w, "height": h},
    "Random Noise": {"noise_seed": seed},
    "Scheduler": {"steps": 25},
    "Flux Guidance": {"guidance": 3.5},
    "Flat Anime LoRA": {"strength_model": 0.8, "strength_clip": 0.8},
    "Save Keyframe": {"filename_prefix": name},
}
```
- IP-Adapter/ControlNet 노드는 워크플로우에 존재하지만 입력 이미지가 없으면 무시됨

### generate_backgrounds.py (배경)
```python
overrides = {
    "Positive Prompt": {"text": prompt},
    "Latent Image (1344x768)": {"width": 1344, "height": 768},
    "Random Noise": {"noise_seed": seed},
    "Scheduler": {"steps": 20},
    "Flux Guidance": {"guidance": 3.5},
    "Flat Anime LoRA": {"strength_model": 0.4, "strength_clip": 0.4},  # 배경은 0.4
    "Save Keyframe": {"filename_prefix": name},
}
```

### generate_storyboard_panels.py (스토리보드)
```python
overrides = {
    "Load Reference Screenshot": {"image": ref_upload["name"]},
    "Positive Prompt": {"text": prompt_text},
    "Random Noise": {"noise_seed": seed},
    "Load Character Golden Shot": {"image": golden_upload["name"]},
}
```
- nichijou 워크플로우 그대로 사용 (설정 변경 없음)

---

## 규칙

1. **워크플로우 설정을 코드에서 임의로 변경하지 않는다.** 확정 설정은 이 문서와 `CHARACTER_GENERATION_SPEC.md` 기준.
2. **이 문서의 legacy 스크립트는 `legacy/nichijou_ipadapter_keyframe.json` 계열을 사용한다.**
3. **오버라이드 키는 워크플로우의 `_meta.title` 값과 정확히 일치해야 한다.**
4. **Klein 모델/LoRA 사용 금지.** Flux 1 Dev + Flat_Anime_Style만 사용.
5. **steps, CFG, LoRA strength를 변경하려면 이 문서를 먼저 업데이트한다.**
