# 캐릭터 생성 스펙 — 확정 설정

> 최종 확정일: 2026-04-06
> 모델: Flux 1 Dev GGUF + Juustagram Chibi LoRA @ 1.0

---

## ComfyUI 노드 체인 (캐릭터 골든 샷)

```
UnetLoaderGGUF (flux1-dev-Q5_K_S.gguf)
  → LoraLoader (Juustagram_Chibi_LoRA.safetensors @ 1.0)
    → ModelSamplingFlux (max_shift=1.15, base_shift=0.5, 768x1344)
      → BasicGuider + FluxGuidance (3.5)

DualCLIPLoaderGGUF (clip_l + t5-v1_1-xxl-encoder-Q5_K_M, type="flux")
  → CLIPTextEncode (positive prompt)
    → FluxGuidance (3.5)

RandomNoise (seed)
BasicScheduler (scheduler="normal", steps=25, denoise=1.0)
KSamplerSelect (sampler_name="euler")
SamplerCustomAdvanced → VAEDecode (ae.safetensors)
  → UpscaleModelLoader (4x-AnimeSharp.pth)
    → ImageUpscaleWithModel → ImageScale (1080x1920) → SaveImage
```

### 핵심 설정값

| 항목 | 값 |
|---|---|
| Base Model | flux1-dev-Q5_K_S.gguf |
| LoRA | Juustagram_Chibi_LoRA.safetensors |
| LoRA 강도 | 1.0 (model + clip) |
| 트리거 워드 | `juustagram style, chibi` |
| 생성 해상도 | **1024×1024** (정방, 치비 캐릭터) |
| 업스케일 | 4x-AnimeSharp → **2048×2048** |
| Steps | 25 (캐릭터) / 20 (키프레임) |
| CFG (FluxGuidance) | 3.5 |
| Scheduler | normal |
| Sampler | euler |
| ModelSamplingFlux | max_shift=1.15, base_shift=0.5 |
| VAE | ae.safetensors |
| IP-Adapter | **미사용** (캐릭터 시트는 순수 프롬프트) |
| ControlNet | **미사용** |

### ❌ 사용하지 않는 노드
- KSampler (레거시)
- EmptyLatentImage (Flux 전용 아님)
- IP-Adapter (캐릭터 시트에서는 불필요)
- ControlNet (구도 참조 불필요)

---

## 프롬프트 구조

```
juustagram style, chibi, azur lane slow ahead style,
flat color cel shading, thick black outlines, pastel color palette,
simple round face, large head small body proportions,
1girl, solo,
[머리: color + style],
[눈: color],
[복장: 국가 특색 의상 (간결하게)],
[소품: 국가 대표 아이템],
[국기 액세서리: flag pin],
[표정/포즈],
standing, full body, white background, clean anime art
```

### 핵심 규칙
1. **치비 비율** — `large head small body proportions, simple round face` 필수
2. **스타일 앵커** — `juustagram style, chibi, azur lane slow ahead style` 프리픽스
3. **교복 금지** — 국가 특색 의상으로 (카우보이, 히잡, 치파오 등)
4. **white background** — 골든 샷은 항상 흰 배경
5. **full body, standing** — 전신 정면
6. **파스텔 톤 + 굵은 외곽선** — `flat color cel shading, thick black outlines`

---

## 확정된 캐릭터 프롬프트 (Pilot 5명)

### America
```
juustagram style, chibi, azur lane slow ahead style, flat color cel shading, thick black outlines,
pastel color palette, simple round face, large head small body proportions,
1girl, solo, blonde wavy hair, blue eyes, cowboy hat, red crop top, denim shorts,
cowboy boots, star badge, confident smirk, hands on hips,
standing, full body, white background, clean anime art
```

### Iran
```
juustagram style, chibi, azur lane slow ahead style, flat color cel shading, thick black outlines,
pastel color palette, simple round face, large head small body proportions,
1girl, solo, long black hair, green eyes, loose green headscarf, off-shoulder dark green top,
black skirt, red rose accessory, flag pin, defiant expression, arms crossed,
standing, full body, white background, clean anime art
```

### Iraq
```
juustagram style, chibi, azur lane slow ahead style, flat color cel shading, thick black outlines,
pastel color palette, simple round face, large head small body proportions,
1girl, solo, black wavy hair, brown eyes, beige off-shoulder sweater, brown mini skirt,
gold earrings, flag pin, worried expression, hands clasped,
standing, full body, white background, clean anime art
```

### UK
```
juustagram style, chibi, azur lane slow ahead style, flat color cel shading, thick black outlines,
pastel color palette, simple round face, large head small body proportions,
1girl, solo, ginger red twintails, green eyes, open navy blazer, white cropped blouse,
plaid mini skirt, flag pin, smug expression, holding teacup,
standing, full body, white background, clean anime art
```

### Germany
```
juustagram style, chibi, azur lane slow ahead style, flat color cel shading, thick black outlines,
pastel color palette, simple round face, large head small body proportions,
1girl, solo, blonde twin braids, blue eyes, black corset top, red flared skirt,
white off-shoulder blouse, flag pin, nervous expression, hands together,
standing, full body, white background, clean anime art
```

### China
```
juustagram style, chibi, azur lane slow ahead style, flat color cel shading, thick black outlines,
pastel color palette, simple round face, large head small body proportions,
1girl, solo, black double buns, red eyes, sleeveless red qipao mini dress, gold trim,
flag pin, calm smile, holding teacup,
standing, full body, white background, clean anime art
```

### Korea
```
juustagram style, chibi, azur lane slow ahead style, flat color cel shading, thick black outlines,
pastel color palette, simple round face, large head small body proportions,
1girl, solo, long black hair blue ribbon, brown eyes, pink crop top, blue pleated skirt,
gold accessory, flag pin, cheerful smile, hands together,
standing, full body, white background, clean anime art
```

### Pakistan
```
juustagram style, chibi, azur lane slow ahead style, flat color cel shading, thick black outlines,
pastel color palette, simple round face, large head small body proportions,
1girl, solo, dark brown hair bun, brown eyes, sky blue sleeveless tunic, white leggings,
light scarf, flag pin, gentle smile, holding paper,
standing, full body, white background, clean anime art
```

---

## 씹덕 속성 맵

| 캐릭터 | 속성 | 체형 | 복장 스타일 |
|---|---|---|---|
| America | 겐키+양키 | 178cm, 글래머 건강미 | 카우보이 |
| Iran | 쿨뷰티+츤데레 | 168cm, 슬렌더 우아 | 페르시안 코트 |
| Iraq | 소심+보호본능유발 | 162cm, 보통 귀여움 | 캐주얼 중동 |
| EU | 히메+능글 | 170cm, 글래머 성숙 | 정장 |
| UK | 오죠사마+독설 | 165cm, 슬렌더 기품 | 영국식 블레이저 |

---

## 복장 바리에이션 (TODO)

각 캐릭터에 2~3개 복장 변형 추가 예정:
- 평상복 (casual)
- 전투/긴장 모드 (battle/tense)
- 정장/공식 (formal)

---

## 워크플로우 파일

- 캐릭터 생성용: `workflows/legacy/golden_chibi.json` (IP-Adapter/ControlNet 미사용)
- 키프레임 생성용: `workflows/legacy/storyboard_quick.json` 전체 사용

---

## 에셋 경로

```
assets/characters/{country}/
├── {country}_golden.png     ← 확정 골든 샷 (사장 승인)
├── {country}_sheet.png      ← 3면도 (TODO)
├── {country}_casual.png     ← 캐주얼 복장 (TODO)
└── {country}_battle.png     ← 전투 모드 (TODO)
```
