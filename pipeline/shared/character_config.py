"""character_config.py — 캐릭터 & 스타일 SSOT (Single Source of Truth).

모든 파이프라인 스크립트는 이 파일에서 import한다.
직접 프롬프트를 하드코딩하지 말 것.

Usage:
    from character_config import STYLE_ANCHOR, CHARACTERS, CHARACTER_VISUAL_DESC, SEED, LORA_NAME, LORA_STRENGTH
"""

# ─── 확정 설정 (2026-04-09) ───
SEED = 65700
LORA_NAME = "Juustagram style v1.0-000005.safetensors"
LORA_STRENGTH = 1.0
CFG = 3.5
STEPS = 30
TRIGGER_WORD = "juustagram style, chibi"

# ─── 스타일 앵커 (모든 프롬프트 공통 프리픽스) ───
STYLE_ANCHOR = (
    "juustagram style, chibi, azur lane slow ahead style, "
    "flat color cel shading, thick black outlines, pastel color palette, "
    "simple round face, large head small body proportions, "
    "white background, clean anime art"
)

# ─── 배경 프롬프트 ───
BG_PROMPTS = {
    "worldmap":      "cute illustrated world map, super mario world map style, bright green continents, blue ocean, dotted paths, pastel colors, chibi landmarks",
    "pastel":        "simple pastel {color} gradient background, bright, clean, chibi style",
    "interview":     "bright interview room, simple pastel background, sitting on sofa, looking at viewer, chibi style",
    "versus":        "split screen red and blue background, dramatic lightning, versus, chibi style",
    "ocean":         "simple blue ocean background with waves, bright, chibi style",
    "conference":    "simple meeting table, bright pastel background, chibi style",
    "news_desk":     "simple news desk background, bright, clean, chibi style",
}

# ─── 감정별 배경 색상 ───
BG_MOOD_COLORS = {
    "peace":    "sky blue",
    "tension":  "warm orange",
    "anger":    "red",
    "sadness":  "light purple",
    "comedy":   "bright yellow",
    "fear":     "dark blue",
    "neutral":  "white",
}

# ─── 캐릭터 정의 (Chibi v2 — 2026-04-09 확정) ───
CHARACTERS = {
    "america": {
        "golden": "1girl, solo, blonde wavy hair, blue eyes, cowboy hat, red crop top, denim shorts, cowboy boots, star badge, confident smirk, hands on hips, standing, full body",
        "expressions": {
            "angry":   "1girl, solo, blonde wavy hair, blue eyes, cowboy hat, red crop top, angry, v-shaped eyebrows, shouting, fist raised, portrait",
            "sad":     "1girl, solo, blonde wavy hair, blue eyes, cowboy hat, red crop top, sad, tears, looking down, portrait",
            "smug":    "1girl, solo, blonde wavy hair, blue eyes, cowboy hat, red crop top, smug, one eye closed, pointing, portrait",
            "shocked": "1girl, solo, blonde wavy hair, blue eyes, cowboy hat, red crop top, shocked, eyes wide, mouth open, portrait",
        },
    },
    "iran": {
        "golden": "1girl, solo, long black hair, green eyes, loose green headscarf, off-shoulder dark green top, black skirt, red rose accessory, flag pin, defiant expression, arms crossed, standing, full body",
        "expressions": {
            "fierce":   "1girl, solo, long black hair, green headscarf, dark green top, fierce expression, narrowed eyes, portrait",
            "calm":     "1girl, solo, long black hair, green headscarf, dark green top, calm smile, hands folded, portrait",
            "contempt": "1girl, solo, long black hair, green headscarf, dark green top, contemptuous expression, chin raised, portrait",
        },
    },
    "iraq": {
        "golden": "1girl, solo, black wavy hair, brown eyes, beige off-shoulder sweater, brown mini skirt, gold earrings, flag pin, worried expression, hands clasped, standing, full body",
        "expressions": {
            "crying":     "1girl, solo, black wavy hair, brown eyes, beige sweater, crying, tears, trembling, portrait",
            "hopeful":    "1girl, solo, black wavy hair, brown eyes, beige sweater, slight hopeful smile, looking up, portrait",
            "determined": "1girl, solo, black wavy hair, brown eyes, beige sweater, determined expression, fist clenched, portrait",
        },
    },
    "uk": {
        "golden": "1girl, solo, ginger red twintails, green eyes, open navy blazer, white cropped blouse, plaid mini skirt, flag pin, smug expression, holding teacup, standing, full body",
        "expressions": {
            "shocked":  "1girl, solo, ginger red twintails, green eyes, navy blazer, shocked, wide eyes, monocle falling, portrait",
            "haughty":  "1girl, solo, ginger red twintails, green eyes, navy blazer, haughty, chin raised, looking down, portrait",
            "sipping":  "1girl, solo, ginger red twintails, green eyes, navy blazer, sipping tea, eyes closed, content, portrait",
        },
    },
    "germany": {
        "golden": "1girl, solo, blonde twin braids, blue eyes, black corset top, red flared skirt, white off-shoulder blouse, flag pin, nervous expression, hands together, standing, full body",
        "expressions": {
            "stern":   "1girl, solo, blonde twin braids, blue eyes, corset top, stern expression, furrowed brows, arms crossed, portrait",
            "scared":  "1girl, solo, blonde twin braids, blue eyes, corset top, terrified, trembling, pale face, portrait",
            "angry":   "1girl, solo, blonde twin braids, blue eyes, corset top, angry, fists clenched, portrait",
        },
    },
    "pakistan": {
        "golden": "1girl, solo, dark brown hair bun, brown eyes, sky blue sleeveless tunic, white leggings, light scarf, flag pin, gentle smile, holding paper, standing, full body",
        "expressions": {
            "nervous":   "1girl, solo, dark brown hair bun, brown eyes, sky blue tunic, nervous, sweat drop, forced smile, portrait",
            "exhausted": "1girl, solo, dark brown hair bun, brown eyes, sky blue tunic, exhausted, drooping eyes, slouched, portrait",
            "pleading":  "1girl, solo, dark brown hair bun, brown eyes, sky blue tunic, pleading expression, wide eyes, portrait",
        },
    },
    "china": {
        "golden": "1girl, solo, black double buns, red eyes, sleeveless red qipao mini dress, gold trim, flag pin, calm smile, holding teacup, standing, full body",
        "expressions": {
            "smug":        "1girl, solo, black double buns, red eyes, red qipao, smug, arms crossed, chin raised, portrait",
            "threatening": "1girl, solo, black double buns, red eyes, red qipao, threatening, shadow over eyes, menacing, portrait",
            "calm":        "1girl, solo, black double buns, red eyes, red qipao, calm calculating smile, sipping tea, portrait",
        },
    },
    "korea": {
        "golden": "1girl, solo, long black hair blue ribbon, brown eyes, pink crop top, blue pleated skirt, gold accessory, flag pin, cheerful smile, hands together, standing, full body",
        "expressions": {
            "tired":   "1girl, solo, long black hair, brown eyes, pink top, tired eyes, dark circles, slouched, portrait",
            "crying":  "1girl, solo, long black hair, brown eyes, pink top, crying, big tears, sobbing, portrait",
            "excited": "1girl, solo, long black hair blue ribbon, brown eyes, pink top, excited, sparkling eyes, fists up, portrait",
        },
    },
}

# ─── 호환용 (다른 스크립트에서 CHARACTER_VISUAL_DESC로 참조) ───
CHARACTER_VISUAL_DESC = {k: v["golden"] for k, v in CHARACTERS.items()}

# ─── 카메라/구도 가이드 (Sylsatra 원작자 검증 — LORA_REFERENCE.md) ───
CAMERA_GUIDE = {
    "framing": ["portrait", "upper body", "full body", "close-up", "cowboy shot"],
    "angle": ["45-degree angle", "from side", "profile", "three quarter view", "from above", "from below"],
    "height": ["below eye level", "above eye level", "eye level"],
    "lighting": ["bright lighting", "dim lighting", "spotlight", "side lighting"],
}

VERIFIED_POSES = [
    "fold hands in front, arms extended",
    "looking over shoulder",
    "one arm crossed, hand on chin",
    "sitting on floor, leaning forward",
    "sitting with knees crossed",
    "hands on waist",
    "one knee up",
    "sitting sideways",
    "leaning on wall, popping hip",
    "sitting with one leg bent and other extended",
]

# ─── 연출 규칙 ───
SCENE_RULES = {
    # 2인 대화씬: 옆모습 금지, 쿼터뷰(three quarter view)로 표정 보이게
    "dialogue_2char": "three quarter view, looking at each other, both faces visible",
    # CONFESSIONAL/INTERVIEW: 밝은 인터뷰룸
    "interview": "bright interview room, simple pastel background, sitting on sofa, looking at viewer",
    # VERSUS: 빨/파 분할
    "versus": "split screen red and blue background, dramatic, versus",
}
