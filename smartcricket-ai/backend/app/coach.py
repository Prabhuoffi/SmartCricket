"""AI virtual coach (module M7): grounded replies from OpenAI or Gemini.

Only the stored numbers of one analysis are sent to the model, never the image or video.
A guard checks that every number in the reply appears in those stored numbers.
"""
import json
import re
import time

import httpx

from .config import settings

# One coach for the whole app. PERSONA is shared; the topic rules add what is special about the page.
PERSONA = """You are the SmartCricket AI Coach, the one friendly batting coach of the SmartCricket AI app.
The player meets you on every page, so you know their training plan and progress (player JSON) and, on a result
page, the analysis they are looking at (this_analysis JSON). Use ONLY these JSON facts about the player.
Start every line that states a fact from the JSON with "Measured:".
Start every line of general coaching advice with "General tip:".
Suggest drills as suggestions, not instructions. Keep replies under 120 words.
Joint angles are 2D estimates from one camera; never call technique right or wrong because of them.
If the player reports pain or soreness, suggest rest and seeing a doctor or physiotherapist if it continues.
Never invent numbers. Never give medical or injury advice."""

ANALYSIS_RULES = """Topic: the result in this_analysis. Answer about it first; use the player JSON when the player
asks what to practise or how this fits their plan.
If a joint was not measured, say so instead of estimating it.
If the analysis is marked uncertain or no person was detected, say there is not enough data for a firm answer.
For videos, "shot" is the model's prediction and "confidence" its calibrated probability (0 to 1).
If the analysis is a movement analysis (shot is null), no shot was identified: say so plainly and talk about the
body movement instead (joint ranges, the frame with the most movement), never guess the shot.
A heatmap shows where the model looked; it does not prove the model reasoned correctly.
In reference_comparison, mean_diff is the player's angle minus the reference angle in degrees."""

TRAINING_RULES = """Topic: the player's training (today's plan, check-in, streak, level, this week), with their most
recent result in latest_result. Never push a player to train when they report soreness."""

NO_KEY_REPLY = ("The AI Coach is not set up yet: add LLM_API_KEY to the .env file and restart the server. "
                "Your results, plan and progress still work without it.")
FALLBACK_REPLY = ("Measured: see the angle table on this page for your results. "
                  "I could not produce an answer that sticks to your measured numbers, so please try rephrasing.")


def facts_for(analysis) -> dict:
    """The compact JSON the model is allowed to use."""
    s = analysis.summary or {}
    return {
        "mode": analysis.mode,
        "shot": analysis.shot,
        "confidence": analysis.confidence,
        "uncertain": analysis.uncertain,
        "top3": analysis.top3,
        "person_detected": s.get("detected"),
        "landmarks_visible": s.get("visible"),
        "landmarks_total": s.get("total"),
        "shoulder_line_deg": s.get("shoulder_line_deg"),
        "angles_deg": {k: v["deg"] for k, v in (analysis.angles or {}).items()},
    } | (_video_facts(analysis) if analysis.mode == "video" else {})


def _video_facts(analysis) -> dict:
    """Video results without the long per-frame arrays, which the model does not need."""
    s = analysis.summary or {}
    key = s.get("key_frame")
    facts = {"model": s.get("model_label"), "key_frame": None if key is None else key + 1, "frames": s.get("frames"),
             "angles_at_key_frame_deg": (s.get("angles_seq") or [{}])[key] if key is not None else None}
    if analysis.mode == "video" and not analysis.shot:
        facts["analysis_type"] = "movement analysis (shot classifier not used)"
        facts["frame_with_most_movement"] = facts.pop("key_frame")
        facts["joint_ranges_deg"] = {j: {k: r[k] for k in ("min", "max", "range")} for j, r in (s.get("joint_ranges") or {}).items()}
        facts["frames_with_body_tracked"] = s.get("tracked_frames")
    if analysis.dtw:
        facts["reference_comparison"] = {"reference": analysis.dtw.get("reference_label"),
                                         "dtw_distance": analysis.dtw.get("distance"),
                                         "per_joint": analysis.dtw.get("per_joint")}
    return facts


def _numbers(obj):
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        yield float(obj)
        if isinstance(obj, float) and obj <= 1:
            yield obj * 100  # a confidence of 0.83 may be written as 83%
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _numbers(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _numbers(v)


def numbers_grounded(reply: str, facts: dict) -> bool:
    allowed = [round(n, 0) for n in _numbers(facts)]
    for tok in re.findall(r"\d+(?:\.\d+)?", reply):
        n = float(tok)
        if n <= 15:  # small counts ("2 drills", "3 sets") are allowed
            continue
        if not any(abs(round(n, 0) - a) <= 1 for a in allowed):
            return False
    return True


class CoachBusy(Exception):
    """Every model tried was overloaded or rate-limited."""


def _gemini(model: str, body: dict) -> str:
    # The key goes in a header, never in the URL, so it cannot end up in logs or error messages.
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    r = httpx.post(url, json=body, headers={"x-goog-api-key": settings.llm_api_key}, timeout=25)
    r.raise_for_status()
    parts = r.json()["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()


def _call(messages: list[dict]) -> str:
    if settings.llm_provider == "gemini":
        contents = [{"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
                    for m in messages if m["role"] != "system"]
        body = {"system_instruction": {"parts": [{"text": messages[0]["content"]}]}, "contents": contents,
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1024,
                                     "thinkingConfig": {"thinkingBudget": 0}}}
        models = [settings.llm_model] + [m.strip() for m in settings.llm_fallback_models.split(",")
                                         if m.strip() and m.strip() != settings.llm_model]
        # Busy (429/503) or slow models: retry once, then move on to the next model.
        for model in models:
            for attempt in range(2):
                try:
                    return _gemini(model, body)
                except httpx.TimeoutException:
                    break
                except httpx.HTTPStatusError as e:
                    if e.response.status_code in (429, 500, 503):
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    if e.response.status_code == 404:  # model retired or not available to this key
                        break
                    raise
        raise CoachBusy()
    r = httpx.post("https://api.openai.com/v1/chat/completions",
                   headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                   json={"model": settings.llm_model, "messages": messages, "temperature": 0.3, "max_tokens": 400},
                   timeout=30)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def converse(facts: dict, history: list[tuple[str, str]], question: str, topic_rules: str) -> str:
    """One conversation turn with the coach: shared persona, topic rules, the facts, the last six messages,
    and the number check (regenerate once, then fall back)."""
    if not settings.llm_api_key:
        return NO_KEY_REPLY
    messages = [{"role": "system", "content": PERSONA + "\n" + topic_rules + "\n\nFacts JSON:\n" + json.dumps(facts)}]
    for role, text in history[-6:]:
        messages.append({"role": "assistant" if role == "coach" else "user", "content": text})
    messages.append({"role": "user", "content": question})
    answer = _call(messages)
    if numbers_grounded(answer, facts):
        return answer
    messages.append({"role": "assistant", "content": answer})
    messages.append({"role": "user", "content": "Your reply used a number that is not in the facts JSON. "
                                                "Answer again using only numbers from the JSON."})
    answer = _call(messages)
    return answer if numbers_grounded(answer, facts) else FALLBACK_REPLY


def reply(analysis, history: list[tuple[str, str]], question: str, player: dict | None = None) -> str:
    """Coach on a result page: knows this analysis and, when given, the player's plan and progress."""
    facts = {"this_analysis": facts_for(analysis)} | ({"player": player} if player else {})
    return converse(facts, history, question, ANALYSIS_RULES)
