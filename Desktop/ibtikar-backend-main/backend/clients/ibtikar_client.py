from typing import List, Dict

import httpx
from backend.core.config import settings


BAD_LOCAL = ["hate", "kys", "die", "kill", "dumb", "trash", "terror"]


def _stub(texts: List[str]) -> List[Dict]:
    # Fallback if IBTIKAR_URL is not set or service is down
    out: List[Dict] = []
    for t in texts:
        lower = (t or "").lower()
        harmful = any(w in lower for w in BAD_LOCAL)
        out.append(
            {
                "label": "harmful" if harmful else "safe",
                "score": 0.85 if harmful else 0.70,
            }
        )
    return out


def _is_huggingface_api(url: str) -> bool:
    """Check if URL is a Hugging Face Inference API endpoint."""
    return "api-inference.huggingface.co" in url or "hf.space" in url


async def _call_huggingface_api(texts: List[str], url: str) -> List[Dict]:
    """Call Hugging Face Inference API for each text."""
    results = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for text in texts:
            try:
                # Hugging Face Inference API expects single input
                r = await client.post(
                    url,
                    json={"inputs": text},
                    headers={"Content-Type": "application/json"}
                )
                r.raise_for_status()
                data = r.json()
                
                # Handle different response formats from HF API
                if isinstance(data, list) and len(data) > 0:
                    # Standard HF API response: [{"label": "LABEL_0", "score": 0.95}, ...]
                    best = max(data, key=lambda x: x.get("score", 0))
                    label = best.get("label", "LABEL_0")
                    score = best.get("score", 0.0)
                    # Map HF labels to our format
                    label_mapped = "harmful" if "LABEL_1" in label or "toxic" in label.lower() else "safe"
                    results.append({"label": label_mapped, "score": float(score)})
                elif isinstance(data, dict):
                    # Some models return dict format
                    label = data.get("label", "safe")
                    score = data.get("score", 0.0)
                    label_mapped = "harmful" if "toxic" in label.lower() or "harmful" in label.lower() else "safe"
                    results.append({"label": label_mapped, "score": float(score)})
                else:
                    # Fallback
                    results.append({"label": "safe", "score": 0.5})
            except Exception as e:
                print(f"⚠️ HF API error for text: {e}")
                results.append({"label": "safe", "score": 0.5})
    return results


async def analyze_texts(texts: List[str]) -> List[Dict]:
    # If no URL configured, use stub
    if not settings.IBTIKAR_URL:
        return _stub(texts)

    url = settings.IBTIKAR_URL.rstrip("/")

    # Check if it's Hugging Face API
    if _is_huggingface_api(url):
        try:
            return await _call_huggingface_api(texts, url)
        except Exception as e:
            print(f"⚠️ Hugging Face API error: {e}, using stub")
            return _stub(texts)

    # Legacy API format (original IbtikarAI service)
    url = url + "/predict"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(url, json={"texts": texts})
            r.raise_for_status()
            data = r.json()
    except httpx.RequestError:
        # Service unreachable -> safe fallback
        return _stub(texts)

    preds = data.get("preds")
    if not isinstance(preds, list):
        return _stub(texts)

    # Make sure each item has label + score
    cleaned = []
    for p in preds:
        cleaned.append(
            {
                "label": str(p.get("label", "unknown")),
                "score": float(p.get("score", 0.0)),
            }
        )
    return cleaned
