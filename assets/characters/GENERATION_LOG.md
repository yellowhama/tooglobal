# 캐릭터 골든샷 생성 로그

> 2026-04-09 확정 — Juustagram Chibi LoRA + Azur Lane Slow Ahead 스타일 앵커

---

## 모델 설정

| 항목 | 값 |
|------|-----|
| Base Model | Flux 1 Dev GGUF (Q5_K_S) |
| LoRA | `Juustagram style v1.0-000005.safetensors` @ **1.0** |
| CFG/Guidance | **3.5** |
| Steps | 30 |
| Sampler | euler / normal |
| Seed | **65700** |
| Resolution | 1024x1024 |
| IP-Adapter | **OFF** (골든샷 생성 시) |
| ControlNet | **OFF** |
| Upscaler | **4x-AnimeSharp.pth** → lanczos 2048x2048 |
| Workflow | `workflows/legacy/golden_chibi.json` + upscale nodes from `workflows/legacy/storyboard_quick.json` |

## 스타일 앵커 프리픽스 (모든 캐릭터 공통)

```
juustagram style, chibi, azur lane slow ahead style, flat color cel shading, thick black outlines, pastel color palette, simple round face, large head small body proportions, white background, clean anime art
```

> **핵심**: `azur lane slow ahead style`이 스타일 수렴의 결정적 요소. 이 LoRA의 원본 작품이라 시너지 최고.

## 캐릭터별 프롬프트

### America
```
[STYLE], 1girl, solo, blonde wavy hair, blue eyes, cowboy hat, red crop top, denim shorts, cowboy boots, star badge, confident smirk, hands on hips, standing, full body
```

### Iran
```
[STYLE], 1girl, solo, long black hair, green eyes, loose green headscarf, off-shoulder dark green top, black skirt, red rose accessory, flag pin, defiant expression, arms crossed, standing, full body
```

### Iraq
```
[STYLE], 1girl, solo, black wavy hair, brown eyes, beige off-shoulder sweater, brown mini skirt, gold earrings, flag pin, worried expression, hands clasped, standing, full body
```

### UK
```
[STYLE], 1girl, solo, ginger red twintails, green eyes, open navy blazer, white cropped blouse, plaid mini skirt, flag pin, smug expression, holding teacup, standing, full body
```

### Germany
```
[STYLE], 1girl, solo, blonde twin braids, blue eyes, black corset top, red flared skirt, white off-shoulder blouse, flag pin, nervous expression, hands together, standing, full body
```

### Pakistan
```
[STYLE], 1girl, solo, dark brown hair bun, brown eyes, sky blue sleeveless tunic, white leggings, light scarf, flag pin, gentle smile, holding paper, standing, full body
```

### China
```
[STYLE], 1girl, solo, black double buns, red eyes, sleeveless red qipao mini dress, gold trim, flag pin, calm smile, holding teacup, standing, full body
```

### Korea
```
[STYLE], 1girl, solo, long black hair blue ribbon, brown eyes, pink crop top, blue pleated skirt, gold accessory, flag pin, cheerful smile, hands together, standing, full body
```

## 아카이브

이전 Flat Anime Style 골든샷: `_archive_flat_anime_v1/`

## 스타일 고정 핵심

1. **스타일 앵커 프리픽스** — 모든 프롬프트 앞에 동일한 스타일 블록
2. **azur lane slow ahead style** — LoRA 원본 작품 레퍼런스로 스타일 수렴
3. **동일 시드** (65700) — 구도 통일
4. **동일 프롬프트 구조** — [스타일] + [캐릭터 외형] + [포즈] + [full body, white background]
