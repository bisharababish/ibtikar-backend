from typing import List, Dict
import asyncio
import time

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
    return "api-inference.huggingface.co" in url or "router.huggingface.co" in url or "hf.space" in url


async def _call_huggingface_api(texts: List[str], url: str) -> List[Dict]:
    """Call Hugging Face Inference API for each text."""
    results = []
    
    # Convert old API URL to new format if needed
    if "api-inference.huggingface.co" in url:
        # Extract model path: models/username/model-name
        model_path = url.split("models/")[-1] if "models/" in url else url.split("/")[-1]
        # Use new router endpoint
        url = f"https://router.huggingface.co/hf-inference/v1/models/{model_path}"
    
    print(f"🔍 Calling Hugging Face API: {url}")
    
    # Prepare headers with optional authentication
    headers = {"Content-Type": "application/json"}
    if settings.HF_TOKEN:
        headers["Authorization"] = f"Bearer {settings.HF_TOKEN}"
        print("🔑 Using HF_TOKEN for authentication")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, text in enumerate(texts):
            try:
                print(f"🔍 Processing text {i+1}/{len(texts)}: {text[:50]}...")
                # Hugging Face Inference API expects single input
                r = await client.post(
                    url,
                    json={"inputs": text},
                    headers=headers
                )
                
                # Handle rate limiting properly
                if r.status_code == 429:
                    # Get rate limit info from headers
                    reset_timestamp = r.headers.get("x-rate-limit-reset")
                    retry_after = r.headers.get("retry-after")
                    limit = r.headers.get("x-rate-limit-limit", "unknown")
                    remaining = r.headers.get("x-rate-limit-remaining", "0")
                    
                    # Calculate wait time
                    wait_seconds = 60  # Default 1 minute
                    if retry_after:
                        try:
                            wait_seconds = int(retry_after)
                        except ValueError:
                            pass
                    elif reset_timestamp:
                        try:
                            reset_time = int(reset_timestamp)
                            current_time = int(time.time())
                            wait_seconds = max(1, reset_time - current_time)
                        except (ValueError, TypeError):
                            pass
                    
                    # Cap wait time at 5 minutes (300 seconds)
                    wait_seconds = min(wait_seconds, 300)
                    
                    wait_minutes = wait_seconds // 60
                    wait_secs = wait_seconds % 60
                    
                    error_msg = (
                        f"⚠️ Rate limited (429) for text {i+1}/{len(texts)}. "
                        f"Limit: {limit}, Remaining: {remaining}. "
                        f"Waiting {wait_minutes}m {wait_secs}s before retry..."
                    )
                    print(error_msg)
                    
                    # Wait for the calculated time
                    await asyncio.sleep(wait_seconds)
                    
                    # Try once more after waiting
                    r = await client.post(
                        url,
                        json={"inputs": text},
                        headers=headers
                    )
                    
                    # If still rate limited, raise an error with details
                    if r.status_code == 429:
                        raise Exception(
                            f"Still rate limited after waiting. "
                            f"Reset time: {reset_timestamp or 'unknown'}, "
                            f"Please try again later."
                        )
                
                r.raise_for_status()
                data = r.json()
                
                # Always log response format for debugging
                print(f"📋 HF API response for text {i+1}: {str(data)[:200]}")
                print(f"📋 Response type: {type(data)}")
                
                # Handle different response formats from HF API
                # HF classification models can return:
                # - List of lists: [[{"label": "LABEL_0", "score": 0.95}, {"label": "LABEL_1", "score": 0.05}]]
                # - List of dicts: [{"label": "LABEL_0", "score": 0.95}, {"label": "LABEL_1", "score": 0.05}]
                # - Single dict: {"label": "LABEL_1", "score": 0.65}
                
                label_mapped = "unknown"
                score = 0.5
                
                try:
                    # Handle nested list format: [[{...}, {...}]]
                    if isinstance(data, list) and len(data) > 0:
                        # Check if first element is also a list (nested format)
                        if isinstance(data[0], list) and len(data[0]) > 0:
                            data = data[0]  # Unwrap nested list
                            if i == 0:
                                print(f"📋 Unwrapped nested list, now: {data}")
                    
                    # Now process the actual list of label dicts
                    if isinstance(data, list) and len(data) > 0:
                        # Find LABEL_0 (safe) and LABEL_1 (toxic/harmful)
                        label_0_item = None
                        label_1_item = None
                        
                        for item in data:
                            if not isinstance(item, dict):
                                continue
                            label_str = str(item.get("label", "")).upper()
                            if "LABEL_0" in label_str or label_str == "0":
                                label_0_item = item
                            elif "LABEL_1" in label_str or label_str == "1":
                                label_1_item = item
                        
                        # If not found by label name, assume by position (first = LABEL_0, second = LABEL_1)
                        if not label_0_item and len(data) > 0 and isinstance(data[0], dict):
                            label_0_item = data[0]
                        if not label_1_item and len(data) > 1 and isinstance(data[1], dict):
                            label_1_item = data[1]
                        
                        # Get scores - handle both LABEL_0/1 format and numeric labels
                        score_0 = float(label_0_item.get("score", 0.0)) if label_0_item else 0.0
                        score_1 = float(label_1_item.get("score", 0.0)) if label_1_item else 0.0
                        
                        # Log what we found
                        if i == 0:
                            print(f"🔍 Found labels: LABEL_0={label_0_item}, LABEL_1={label_1_item}")
                            print(f"🔍 Raw scores: score_0={score_0}, score_1={score_1}")
                        
                        # Decision rule: LABEL_1 (toxic/harmful) score > LABEL_0 (safe) score = harmful
                        # Use > instead of >= to be more strict
                        # Also, if score_1 is significantly higher (e.g., > 0.6), mark as harmful
                        if score_1 > score_0 or score_1 > 0.6:
                            label_mapped = "harmful"
                            score = score_1
                        elif score_0 > 0.6:
                            label_mapped = "safe"
                            score = score_0
                        else:
                            # Uncertain - use the higher score
                            if score_1 > score_0:
                                label_mapped = "harmful"
                                score = score_1
                            else:
                                label_mapped = "safe"
                                score = score_0
                        
                        # Debug log for first text only
                        if i == 0:
                            print(f"🔍 LABEL_0 item: {label_0_item}")
                            print(f"🔍 LABEL_1 item: {label_1_item}")
                            print(f"🔍 Scores: LABEL_0={score_0:.4f}, LABEL_1={score_1:.4f}")
                            print(f"✅ Final decision: {label_mapped} (score={score:.4f})")
                        
                        # IMPORTANT: Append the result!
                        results.append({"label": label_mapped, "score": float(score)})
                    
                    elif isinstance(data, dict):
                        # Single dict response
                        label = str(data.get("label", "")).upper()
                        score = float(data.get("score", 0.5))
                        label_mapped = "harmful" if ("LABEL_1" in label or "TOXIC" in label or "1" in label) else "safe"
                        if i == 0:
                            print(f"✅ Single dict format: {label_mapped} (score={score:.4f})")
                        results.append({"label": label_mapped, "score": float(score)})
                    else:
                        # Unexpected format - log and raise error to trigger stub
                        print(f"❌ Unexpected response format for text {i+1}: {type(data)}")
                        print(f"   Data: {str(data)[:500]}")
                        raise Exception(f"Unexpected HF API response format: {type(data)}. Expected list or dict.")
                    
                except Exception as e:
                    print(f"⚠️ Error parsing HF response for text {i+1}: {e}, data: {data}")
                    import traceback
                    traceback.print_exc()
                    results.append({"label": "unknown", "score": 0.5})
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    # Rate limited - raise exception to be handled by caller
                    reset_timestamp = e.response.headers.get("x-rate-limit-reset")
                    retry_after = e.response.headers.get("retry-after")
                    raise Exception(
                        f"Rate limited by Hugging Face API. "
                        f"Reset: {reset_timestamp or 'unknown'}, "
                        f"Retry after: {retry_after or 'unknown'} seconds"
                    )
                error_text = e.response.text[:500] if e.response.text else "No error text"
                print(f"❌ HF API HTTP error for text {i+1}: {e.response.status_code}")
                print(f"   Error response: {error_text}")
                print(f"   This indicates a problem with the API call - NOT using fallback")
                # Re-raise to trigger fallback to stub, not return safe/0.5
                raise Exception(f"HF API HTTP {e.response.status_code}: {error_text}")
            except Exception as e:
                # Re-raise rate limit errors
                if "rate limit" in str(e).lower() or "429" in str(e) or "Rate limited" in str(e):
                    raise
                print(f"❌ HF API error for text {i+1}: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                # For non-rate-limit errors, skip this text but continue with others
                # Use stub classification for this text
                harmful = any(w in text.lower() for w in BAD_LOCAL)
                results.append({
                    "label": "harmful" if harmful else "safe",
                    "score": 0.85 if harmful else 0.70,
                })
                print(f"   Using stub classification for text {i+1}")
    
    print(f"✅ Processed {len(results)}/{len(texts)} texts via HF API")
    
    # Log summary of classifications
    harmful_count = sum(1 for r in results if r.get("label") == "harmful")
    safe_count = sum(1 for r in results if r.get("label") == "safe")
    print(f"📊 Classification summary: {harmful_count} harmful, {safe_count} safe")
    
    return results


async def analyze_texts(texts: List[str]) -> List[Dict]:
    print(f"📊 analyze_texts called with {len(texts)} texts")
    
    # If no URL configured, use stub
    if not settings.IBTIKAR_URL:
        print("⚠️ IBTIKAR_URL not configured, using stub classifier")
        stub_results = _stub(texts)
        print(f"📊 Stub results: {stub_results}")
        return stub_results

    url = settings.IBTIKAR_URL.rstrip("/")
    print(f"🔍 Using model API: {url}")
    print(f"🔍 IBTIKAR_URL value: {settings.IBTIKAR_URL}")

    # Check if it's Hugging Face API
    if _is_huggingface_api(url):
        print(f"✅ Detected as Hugging Face API")
        try:
            results = await _call_huggingface_api(texts, url)
            print(f"📊 HF API returned {len(results)} results")
            
            # Log summary of results
            harmful_count = sum(1 for r in results if r.get("label") == "harmful")
            safe_count = sum(1 for r in results if r.get("label") == "safe")
            print(f"📊 Result summary: {harmful_count} harmful, {safe_count} safe")
            
            # Verify results are not all safe/0.5 (indicates a problem)
            if len(results) > 0 and all(r.get("label") == "safe" and r.get("score") == 0.5 for r in results):
                print(f"❌ WARNING: All results are safe/0.5 - this indicates an API issue!")
                print(f"   This usually means the API failed silently or returned an unexpected format")
                # Don't retry, just return what we got so user can see the issue
            return results
        except Exception as e:
            # Re-raise rate limit errors so they can be handled properly
            if "rate limit" in str(e).lower() or "429" in str(e) or "Rate limited" in str(e):
                print(f"❌ Hugging Face API rate limited: {e}")
                raise
            print(f"⚠️ Hugging Face API error: {e}")
            import traceback
            traceback.print_exc()
            print(f"   Falling back to stub classifier")
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
