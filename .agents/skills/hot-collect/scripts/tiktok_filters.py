"""Strict, multilingual-aware topic filters for TikTok captions.

Why this file exists - three measured traps, all of them silent:

  1. The bare word "ai" is a common word in Vietnamese / Portuguese / French /
     Spanish / Italian ("là ai", "ai que tristeza", "ai muốn bà ơi"). A naive
     `\\bai\\b` match pulled in entertainment and news videos. In the 2026-10
     partition the loose regex matched 16,314 rows whose top-view entries
     were Vietnamese soap-opera clips and Portuguese memes.

  2. Product names collide with ordinary words. Measured top-view false
     positives and the word that caused each:
       - "his copilot" (the aviation co-pilot)          481K views
       - "Jean-Claude Van Damme" (the actor)             338K views
       - "on the runway" (the airport runway)
       - "Sora" / "Kimi" / "Manus" / "Devin" (given names)
     So an ambiguous product name only counts when it is QUALIFIED
     ("Claude Code", "GitHub Copilot", "OpenAI Sora").

  3. "gemini" is also a ZODIAC sign ("géminis"). Spanish horoscope videos
     about Gemini outrank real Gemini-model content by views.

And one axis that is NOT the topic: `is_ai_generated` / "#ai" / "AI-generated"
mean the video was MADE with AI (CapCut effects, AI short dramas). That is
84,804 of 1.73M rows in the same partition - a completely different question
from "does this video talk about AI".
"""

from __future__ import annotations

import re

# --- unambiguous products --------------------------------------------------
PRODUCT = re.compile(
    r"\b(chat\s?gpt|chatgpt|gpt-?[345o]\b|gpt ?\d|openai|anthropic|"
    r"midjourney|stable ?diffusion|deepseek|llama ?\d|qwen|ollama|lm ?studio|"
    r"hugging ?face|n8n|langchain|llamaindex|bbolt|bolt\.new|replit|lovable|"
    r"comfy ?ui|invoke ?ai|make\.com|mcp)\b",
    re.I,
)

# --- ambiguous names: only count when qualified ----------------------------
# "his copilot" (aviation), "Jean-Claude Van Damme" (actor), "on the runway"
# (airport) all measured as false positives. So:
#   QUALIFIED_STRONG  - an explicit product form  -> strong signal
#   AMBIGUOUS_NAME    - the bare word            -> weak signal, needs company
QUALIFIED_STRONG = re.compile(
    r"(?:(?:anthropic|ai|agentic|openai|google|deepmind|github|microsoft|moonshot|"
    r"cognition)\s+(?:ai\s+)?(?:claude|gemini|copilot|perplexity|sora|kimi|manus|"
    r"devin|veo|kling|runway)\b)"
    r"|(?:\b(?:claude|gemini|copilot|perplexity|sora|kimi|manus|devin|veo|kling|"
    r"runway)\s?(?:code|opus|sonnet|haiku|api|app|cli|pro|flash|ultra|agent|chat|"
    r"workspace|mode|ml|gen|ai|2|3|3\.5|k2|sonar)\b)",
    re.I,
)
AMBIGUOUS_NAME = re.compile(
    r"(?<!jean-)(?<!jean )\b(claude|gemini|copilot|perplexity|sora|kimi|manus|"
    r"devin|veo|kling|runway)\b",
    re.I,
)

# --- AI + a tech/topic noun (the noun is required) -------------------------
AI_TECH = re.compile(
    r"\b(ai|artificial intelligence)\b[ -]?"
    r"(tools?|models?|agents?|agentic|videos?|images?|art|music|voice|chatbots?|apps?|"
    r"code|coding|developer|dev|design|logos?|headshots?|avatars?|generators?|"
    r"workflows?|automation|news|explained|tutorial|how|future|prompts?|"
    r"prompting|copilot|startup|saas|tech|tools? stack|era|slop|content)\b",
    re.I,
)
# reversed order: "coding with ai" / "prompt for ai" / "built with ai".
# The connector must sit DIRECTLY next to the AI term - a loose window
# matched "Styled By Miloh ... #ai" (a fashion clip) because "by" is a
# connector and "#ai" appeared 30 chars later.
TECH_AI = re.compile(
    r"\b(coding|building|built|creating|created|generating|generated|making|made|"
    r"powered|using|with|via|for|by|writing|code|programar|programando|hecho con|"
    r"creado con)\s+(con\s+|de\s+)?"
    r"(ai|artificial intelligence|chatgpt|chat ?gpt|claude|copilot|cursor|midjourney|"
    r"openai|llms?|gemini)\b",
    re.I,
)
PROMPTING = re.compile(
    r"\b(prompt(?:ing| engineering)?|system prompt|chat template|context window|"
    r"agentic|multi-?agent|ai agent|ai coding|vibe\s?cod(?:ing|er)?|"
    r"code agent|ai ?slop)\b",
    re.I,
)

# "AI-generated" with NOTHING after it is the EFFECT axis (a label on an
# AI-generated clip), not the topic. Measured: a 1.01M-view Ronaldo clip
# matched only because its caption carried the "AI-generated" label.
AI_GENERATED_BARE = re.compile(r"\bai[ -]?generated(?![ -]?\w)", re.I)
AI_GENERATED_TOPIC = re.compile(
    r"\bai[ -]?(?:generated|made|created)[ -]?(image|images|video|videos|art|artwork|"
    r"content|music|voice|avatar|headshot|logo|photo|photos)\b",
    re.I,
)

# --- hashtags: TOPIC vs EFFECT --------------------------------------------
# NOTE: plain "#ai" is NOT a topic tag. Measured 2026-10-23: the highest-view
# row carrying #ai was a 2.8M-view "AI story" clip (tags: fruitdrama aistory
# ai fruitstory brainrot). On TikTok "#ai" marks content MADE with AI, the
# same axis as is_ai_generated - not people talking about AI.
TOPIC_TAGS = {
    "aicoding", "aitools", "artificialintelligence", "chatgpt", "claude",
    "openai", "llm", "llms", "genai", "generativeai", "promptengineering",
    "prompting", "vibecoding", "cursorai", "techtok", "ainews", "aidev",
    "aicontent", "learntocode", "buildinpublic", "devlife", "aiagents",
    "aiautomation", "aigamedev", "aidesign", "aicodingtiktok", "coding",
    "programmertok", "buildwithai", "madewithai", "chatgptprompts", "ai2025",
    "ai2026", "artificialintelligencetiktok", "aiagent", "aiproduct",
    "aibusiness", "aitoolsdaily", "technews", "devtools", "codeagent",
    # Spanish / Portuguese for AI ("#ia") - a 486K-view real hit
    # ("Claude convirtiendo Imagen a AutoCAD #ia") was only findable this way.
    "ia", "inteligenciaartificial", "inteligencia", "chatgptprompts2",
}
# "made with AI" / "AI effects" - a DIFFERENT axis (the video was generated).
EFFECT_TAGS = {
    "ai", "aivideo", "aigenerated", "aigeneratedvideos", "aistory", "dreamina",
    "dreaminaskillstudio", "dreaminaweb2", "dreaminapioneer", "capcut",
    "capcutpioneer", "aivideoeffect", "aivideoediting", "aifilter", "aieffect",
    "aicartoon", "aistorytiktok", "aiart", "aiviral",
}

# --- false-positive guards -------------------------------------------------
ZODIAC_CONTEXT = re.compile(
    r"(g[eé]minis|gemini sign|horoscope|zodiac|zodiaco|signs?|mercure|scorpio|"
    r"leo|virgo|sagitario|gemelos|twins|astrology|astrolog|astroloji|"
    r"占星|星座|双魚|雙子|山羊|天秤|水瓶|射手|巨蟹|狮子)",
    re.I,
)
# languages where a bare "ai" is an ordinary word
BARE_AI_OK_LANGS = {"vi", "pt", "fr", "es", "it", "id", "my", "th", "ar", "tr", "pl", "ro"}


def _flatten(value) -> str:
    """hashtags / on_screen_text are list-of-struct columns, not JSON strings."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    out: list[str] = []
    try:
        for item in value:
            if isinstance(item, dict):
                out.append(
                    str(
                        item.get("hashtagName")
                        or item.get("text")
                        or item.get("content")
                        or ""
                    )
                )
            else:
                out.append(str(item))
    except TypeError:
        return str(value)
    return " ".join(x for x in out if x)


def split_tags(value) -> list[str]:
    raw = _flatten(value)
    tags = []
    for t in re.split(r"[\s,]+", raw):
        t = t.strip().lstrip("#").strip()
        if t:
            tags.append(t)
    return tags


# --- vectorised prefilter -------------------------------------------------
# Running the strict classifier row-by-row over 1.7M rows is far too slow
# (a pandas .apply(axis=1) pass takes minutes). So: cheap vectorised regex
# first, then the strict per-row classifier only on the small candidate set.
# The prefilter is deliberately LOOSE (it may keep false positives) - the
# strict classifier is what decides. It must not be able to drop a true
# positive, so it matches on the strongest bare signals only.
PREFILTER = re.compile(
    r"(?:artificial intelligence|chat\s?gpt|chatgpt|gpt-?\d|openai|anthropic|"
    r"claude|gemini|copilot|midjourney|stable ?diffusion|deepseek|perplexity|"
    r"llama|qwen|runway|sora|lovable|cursor|n8n|langchain|"
    r"vibe\s?cod|prompt(?:ing| engineering)?|ai[ -]?(?:tool|model|agent|code|coding|"
    r"app|workflow|video|image|art|music|news|explained|tutorial|prompt|generator|"
    r"generated|design|headshot|avatar|logo|chatbot|assistant|automation|startup|"
    r"tech|era|slop|content|dev|developer|how|future)|"
    r"#(?:ai|aigc|chatgpt|claude|openai|llm|gemini|copilot|midjourney|prompting|"
    r"promptengineering|vibecoding|cursorai|techtok|artificialintelligence|"
    r"aitools|aicoding|ainews|aiagents|aiautomation|learntocode|buildinpublic|"
    r"devlife|chatgptprompts|buildwithai|programming|programmertok)\b)",
    re.I,
)


def prefilter_text(caption, hashtags, on_screen_text) -> str:
    return f"{_flatten(caption)} {_flatten(hashtags)} {_flatten(on_screen_text)}"


def classify(caption, hashtags, on_screen_text, language: str = "") -> dict:
    """Return {'topic': bool, 'effect': bool, 'score': int, 'why': [str]}."""
    cap = _flatten(caption)
    ost = _flatten(on_screen_text)
    text = f"{cap} {ost}"
    tags = [t.lower() for t in split_tags(hashtags)]
    why: list[str] = []
    score = 0

    tag_topic = [t for t in tags if t in TOPIC_TAGS]
    tag_effect = [t for t in tags if t in EFFECT_TAGS]
    if tag_topic:
        score += 2
        why.append(f"tag:{','.join(tag_topic[:3])}")

    zodiac = bool(ZODIAC_CONTEXT.search(text))
    has_other_ai = bool(AI_TECH.search(text) or PROMPTING.search(text) or tag_topic)
    if PRODUCT.search(text):
        if not (zodiac and not has_other_ai):
            score += 2
            why.append("product")
    elif QUALIFIED_STRONG.search(text):
        if not (zodiac and not has_other_ai):
            score += 2
            why.append("qualified-product")
    elif AMBIGUOUS_NAME.search(text):
        # bare "claude" / "copilot" / "runway" -> weak, needs company
        score += 1
        why.append("ambiguous-name(weak)")

    if AI_TECH.search(text):
        score += 2
        why.append("ai+noun")
    if AI_GENERATED_TOPIC.search(text):
        score += 2
        why.append("ai-generated-topic")
    elif AI_GENERATED_BARE.search(text):
        # effect axis ("this clip was AI-generated"), not the topic
        why.append("ai-generated(effect,ignored)")
    if TECH_AI.search(text):
        score += 1
        why.append("noun+ai")
    if PROMPTING.search(text):
        score += 2
        why.append("prompting/agent")

    # bare "ai" alone is not evidence
    bare = re.search(r"\bai\b", text, re.I)
    if bare and score == 0 and language in BARE_AI_OK_LANGS:
        why.append("bare-ai(ignored)")

    if zodiac and score <= 2:
        score -= 2
        why.append("zodiac(-2)")

    return {
        "topic": score >= 2,
        "effect": bool(tag_effect),
        "score": score,
        "why": why,
    }
