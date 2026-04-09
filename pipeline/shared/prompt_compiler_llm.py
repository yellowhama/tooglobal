#!/usr/bin/env python3
"""prompt_compiler_llm.py — LLM 기반 프롬프트 컴파일러.

Ollama qwen3.5로 씬 묘사 → booru 태그 + 자연어 프롬프트 양쪽 생성.
manifest에 compiled_prompt (tags) + compiled_prompt_nl (natural language) 저장.

Usage:
    python prompt_compiler_llm.py --manifest episodes/ep01/manifest.json
    python prompt_compiler_llm.py --manifest episodes/ep01/manifest.json --shot s003 --preview
    python prompt_compiler_llm.py --manifest episodes/ep01/manifest.json --mode tags    # 태그만
    python prompt_compiler_llm.py --manifest episodes/ep01/manifest.json --mode natural # 자연어만
"""
import json
import sys
import argparse
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT / "pipeline" / "shared"))
sys.path.insert(0, str(PROJECT / "pipeline" / "stage1_visuals"))
from character_config import STYLE_ANCHOR, CHARACTER_VISUAL_DESC, CHARACTERS as GOLDEN_PROMPTS, TRIGGER_WORD

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen3.5:9b"

FIXED_STYLE_TAGS = STYLE_ANCHOR

# === 시스템 프롬프트 ===

SYSTEM_PROMPT_TAGS = """## Purpose
You convert anime scene descriptions into SHORT image generation tags for Flux + Juustagram Chibi LoRA.
Each cut has a MOOD and DIALOGUE CONTEXT — use them to vary expression and composition.

## CRITICAL RULES
- Output ONLY comma-separated tags. NO sentences.
- Keep it SHORT: 10-15 tags maximum. Under 200 characters.
- Background = BRIGHT pastel gradient (NOT dark). Color matches mood.
- INTERVIEW/CONFESSIONAL = "bright pastel interview room, sitting on sofa"
- Always end with: juustagram style, chibi
- Tag order: character count → hair/eyes → outfit → expression/pose → framing → bright background → juustagram style, chibi
- EVERY CUT must have a DIFFERENT composition/expression. Never repeat the same pose twice.

## VERIFIED prompts (SSOT character_config.py — 2026-04-09):

America (angry):
"1girl, solo, chibi, blonde wavy hair, blue eyes, cowboy hat, red crop top, denim shorts, furious, fist raised, close-up, simple red gradient background, bright, juustagram style, chibi"

America (smug):
"1girl, solo, chibi, blonde wavy hair, blue eyes, cowboy hat, red crop top, smug, one eye closed, pointing, three quarter view, simple warm orange background, bright, juustagram style, chibi"

Iran (defiant):
"1girl, solo, chibi, long black hair, green eyes, green headscarf, off-shoulder dark green top, defiant, arms crossed, upper body, simple dark green gradient background, juustagram style, chibi"

Iran (calm interview):
"1girl, solo, chibi, long black hair, green eyes, green headscarf, dark green top, calm, hands on knees, sitting on sofa, bright pastel green interview room, juustagram style, chibi"

Iraq (crying interview):
"1girl, solo, chibi, black wavy hair, brown eyes, beige off-shoulder sweater, crying, tears, sitting on sofa, bright pastel blue interview room, juustagram style, chibi"

Germany (terrified):
"1girl, solo, chibi, blonde twin braids, blue eyes, black corset top, red skirt, terrified, trembling, hands on cheeks, portrait, cold blue gradient background, bright, juustagram style, chibi"

China (calm):
"1girl, solo, chibi, black double buns, red eyes, red qipao mini dress, calm smile, holding teacup, three quarter view, simple warm yellow background, bright, juustagram style, chibi"

Pakistan (nervous):
"1girl, solo, chibi, dark brown hair bun, brown eyes, sky blue tunic, nervous, holding paper, full body, simple light yellow gradient background, bright, juustagram style, chibi"

## Variety — EVERY CUT MUST BE DIFFERENT!
- FRAMING: close-up, portrait, upper body, cowboy shot, full body (rotate!)
- ANGLE: from below, from above, three quarter view, from behind looking over shoulder
- POSE: arms crossed, fist raised, sitting, leaning forward, hands on hips, pointing, holding object
- EXPRESSION: match the MOOD field — angry/defiant/crying/calm/terrified/smug/shocked/nervous
- BG COLOR by mood: anger=red, tension=orange, sadness=light purple, fear=cold blue, comedy=bright yellow, peace=sky blue, neutral=white
- INTERVIEW/CONFESSIONAL: always "bright pastel [color] interview room, sitting on sofa"

## FORBIDDEN
- Dark backgrounds for interviews/confessionals ❌
- Complex backgrounds (hallway ❌, corridor ❌, room ❌)
- More than 15 tags
- Repeating the same framing/pose as previous cut ❌
- Sentences — TAGS ONLY"""

SYSTEM_PROMPT_NATURAL = """## Purpose
You write SHORT natural language prompts for Flux AI + Juustagram Chibi LoRA.
Use the MOOD and DIALOGUE CONTEXT to pick the right expression and composition.

## CRITICAL RULES
- Write 20-40 words max. SHORT.
- Describe ONLY: character appearance + expression + pose + BRIGHT background.
- Background = BRIGHT pastel gradient matching mood. NOT dark.
- INTERVIEW/CONFESSIONAL = "bright pastel interview room, sitting on sofa"
- Start with "juustagram style, chibi,"
- EVERY cut needs a UNIQUE composition. Never repeat.

## VERIFIED examples (SSOT character_config.py — 2026-04-09):

Input: "America furious, fist raised, shouting"
Output: juustagram style, chibi, a blonde girl with wavy hair and blue eyes wearing a cowboy hat and red crop top, shouting furiously with raised fist, close-up portrait against a bright red gradient background

Input: "Iran defiant, arms crossed, chin up"
Output: juustagram style, chibi, a girl with long black hair and green eyes wearing a green headscarf and dark green off-shoulder top, standing defiantly with arms crossed, upper body against a dark green gradient background

Input: "Iraq crying in interview"
Output: juustagram style, chibi, a girl with black wavy hair and brown eyes wearing a beige off-shoulder sweater, sitting on a sofa crying with tears streaming down, bright pastel blue interview room

Input: "China calmly sipping tea"
Output: juustagram style, chibi, a girl with black double buns and red eyes wearing a sleeveless red qipao mini dress, calmly sipping tea with a knowing smile, three quarter view against a bright warm yellow background

Input: "Germany terrified about energy crisis"
Output: juustagram style, chibi, a blonde girl with twin braids and blue eyes wearing a black corset top and red skirt, terrified with hands on cheeks trembling, portrait against a bright cold blue gradient background

Input: "America uncertain, looking away"
Output: juustagram style, chibi, a blonde girl with wavy hair and blue eyes wearing a cowboy hat and red crop top, sitting uncertainly looking to the side, medium shot in a bright pastel blue interview room"""


def call_ollama(prompt: str, system: str) -> str:
    """Ollama API 호출."""
    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {"temperature": 0.5, "num_predict": 300},
        "think": False
    }).encode()

    req = urllib.request.Request(OLLAMA_URL, data=payload,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            return result.get("response", "").strip()
    except Exception as e:
        print(f"  [WARN] Ollama failed: {e}")
        return None


def compile_prompt(shot: dict, mode: str = "both") -> dict:
    """LLM으로 프롬프트 컴파일. mode: 'tags', 'natural', 'both'"""
    enriched = shot.get("enriched_visual_prompt") or shot.get("visual_prompt") or ""
    characters = [c for c in shot.get("characters", []) if c != "narrator"]
    shot_size = shot.get("shot_size") or "MS"

    # 캐릭터 디스크립션 — CHARACTER_VISUAL_DESC 우선 (골든샷 이미지와 일치)
    char_desc = ""
    for c in characters[:2]:
        desc = CHARACTER_VISUAL_DESC.get(c)
        if desc:
            char_desc += f"Character '{c}' (USE EXACTLY THIS): {desc}\n"
        else:
            golden = GOLDEN_PROMPTS.get(c, {}).get("golden", "")
            if golden:
                char_desc += f"Character '{c}': {golden}\n"

    # 카메라 6축
    taxonomy = shot.get("shot_taxonomy") or {}
    angle = taxonomy.get("angle", "eye_level")
    composition = taxonomy.get("composition", "")
    mood_map = {"SKIT": "comedic, energetic", "DOCU": "serious",
                "CONFESSIONAL": "intimate, emotional, bright interview room",
                "INTERVIEW": "formal, bright interview room"}
    scene_type = shot.get("type", shot.get("_parent_type", "SKIT"))
    mood = mood_map.get(scene_type, "neutral")

    # 컷 메타 활용 (decompose_cuts.py에서 추가된 필드)
    dialogue = shot.get("dialogue_text", "") or ""
    cut_mood = shot.get("mood", "neutral")

    scene_info = f"""[Scene]
{enriched[:250]}

[Characters]
{char_desc or 'No specific character'}

[Camera]
Shot: {shot_size}, Angle: {angle}, Composition: {composition}
Mood: {cut_mood}
Scene type: {scene_type} — {mood}
Dialogue context: {dialogue[:100] if dialogue else 'none'}"""

    results = {}

    # === TAGS ===
    if mode in ("tags", "both"):
        tag_input = f"""{scene_info}

Convert to booru tags. Copy character appearance EXACTLY from design prompt above.
End with: juustagram style, chibi, azur lane slow ahead style, flat color cel shading, thick black outlines, pastel color palette
Tags only:"""

        tag_result = call_ollama(tag_input, SYSTEM_PROMPT_TAGS)
        if tag_result:
            tag_result = tag_result.replace("\n", ", ").strip().strip('"\'')
            if "juustagram" not in tag_result.lower():
                tag_result = FIXED_STYLE_TAGS + ", " + tag_result
            if len(tag_result) > 350:
                cut = tag_result[:350].rfind(",")
                tag_result = tag_result[:cut] if cut > 100 else tag_result[:350]
        else:
            tag_result = f"{FIXED_STYLE_TAGS}, {shot_size.lower()} shot, {', '.join(characters)}"
        results["tags"] = tag_result

    # === NATURAL LANGUAGE ===
    if mode in ("natural", "both"):
        nl_input = f"""{scene_info}

Write a 40-60 word Flux image prompt. Start with: "{TRIGGER_WORD}"
Copy character appearance from design prompt. Keep background simple.
Prompt only:"""

        nl_result = call_ollama(nl_input, SYSTEM_PROMPT_NATURAL)
        if nl_result:
            nl_result = nl_result.strip().strip('"\'')
            if TRIGGER_WORD.lower() not in nl_result.lower():
                nl_result = TRIGGER_WORD + " " + nl_result
            if len(nl_result) > 400:
                nl_result = nl_result[:397] + "..."
        else:
            nl_result = f"{TRIGGER_WORD} an anime character in a simple scene"
        results["natural"] = nl_result

    return results


def compile_manifest(manifest_path: str, mode: str = "both", preview: bool = False, shot_filter: str = None):
    """manifest 전체 프롬프트 컴파일. cuts[] 배열이 있으면 컷 단위로."""
    path = Path(manifest_path)
    data = json.loads(path.read_text(encoding="utf-8"))

    # cuts 배열 존재 여부 확인
    has_cuts = any(s.get("cuts") for s in data["shots"])

    if has_cuts:
        # ── 컷 단위 컴파일 ──
        total = sum(len(s.get("cuts", [])) for s in data["shots"])
        compiled = 0
        for shot in data["shots"]:
            if shot_filter and shot["shot_id"] != shot_filter:
                continue
            for cut in shot.get("cuts", []):
                # 컷에 부모 씬 정보 주입 (compile_prompt가 필요로 하는 필드)
                cut_for_compile = dict(cut)
                cut_for_compile.setdefault("type", shot.get("type", "SKIT"))
                cut_for_compile.setdefault("shot_taxonomy", shot.get("shot_taxonomy", {}))

                results = compile_prompt(cut_for_compile, mode=mode)

                if "tags" in results:
                    cut["compiled_prompt"] = results["tags"]
                if "natural" in results:
                    cut["compiled_prompt_nl"] = results["natural"]

                compiled += 1
                if preview:
                    print(f'  [{cut["cut_id"]}]')
                    if "tags" in results:
                        print(f'    TAGS: {results["tags"][:150]}')
                    if "natural" in results:
                        print(f'    NL:   {results["natural"][:150]}')
                elif compiled % 20 == 0 or compiled == total:
                    print(f'  [{compiled}/{total}] cuts compiled...')
    else:
        # ── 씬 단위 컴파일 (기존 로직) ──
        for shot in data["shots"]:
            if shot_filter and shot["shot_id"] != shot_filter:
                continue

            print(f'  [{shot["shot_id"]}] Compiling ({mode})...')
            results = compile_prompt(shot, mode=mode)

            if "tags" in results:
                shot["compiled_prompt"] = results["tags"]
            if "natural" in results:
                shot["compiled_prompt_nl"] = results["natural"]

            if preview:
                if "tags" in results:
                    print(f'    TAGS: {results["tags"][:200]}')
                if "natural" in results:
                    print(f'    NL:   {results["natural"][:200]}')
                print()

    if not preview:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        if has_cuts:
            count = sum(1 for s in data["shots"] for c in s.get("cuts", []) if c.get("compiled_prompt"))
            print(f"\n✅ Compiled {count}/{total} cut prompts → {path}")
        else:
            count = sum(1 for s in data["shots"] if s.get("compiled_prompt") or s.get("compiled_prompt_nl"))
        print(f"\n✅ Compiled {count}/{len(data['shots'])} prompts → {path}")


def main():
    parser = argparse.ArgumentParser(description="LLM 프롬프트 컴파일러 (tags + natural language)")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--shot", default=None)
    parser.add_argument("--mode", default="both", choices=["tags", "natural", "both"])
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    compile_manifest(args.manifest, mode=args.mode, preview=args.preview, shot_filter=args.shot)


if __name__ == "__main__":
    main()
