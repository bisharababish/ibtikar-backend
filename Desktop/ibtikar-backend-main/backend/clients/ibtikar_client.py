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
    
    # Extract model path from various URL formats
    model_path = None
    if "/models/" in url:
        model_path = url.split("/models/")[-1].rstrip("/")
    elif "router.huggingface.co" in url and "/v1/models/" in url:
        model_path = url.split("/v1/models/")[-1].rstrip("/")
    elif "api-inference.huggingface.co" in url:
        model_path = url.split("models/")[-1] if "models/" in url else url.split("/")[-1]
    
    if not model_path:
        print(f"⚠️ Could not extract model path from URL: {url}")
        model_path = "bisharababish/arabert-toxic-classifier"
    
    print(f"🔍 Extracted model path: {model_path}")
    
    # Inference API is DEPRECATED (returns 410 Gone)
    # MUST use Router API: https://router.huggingface.co/v1/models/{model_path}
    # If URL is already router format, use it; otherwise convert to router
    if "api-inference.huggingface.co" in url:
        print(f"🔄 Converting deprecated Inference API URL to Router API format")
        url = f"https://router.huggingface.co/v1/models/{model_path}"
    elif "router.huggingface.co" not in url:
        # If URL doesn't specify router API, use router
        url = f"https://router.huggingface.co/v1/models/{model_path}"
    
    # Ensure router URL has correct format
    if "router.huggingface.co" in url and "/v1/models/" not in url:
        # Add /v1/ if missing
        if "/models/" in url:
            model_part = url.split("/models/")[-1]
            url = f"https://router.huggingface.co/v1/models/{model_part}"
    
    print(f"🔍 Using Hugging Face Router API: {url}")
    
    # Prepare headers with optional authentication
    headers = {"Content-Type": "application/json"}
    if settings.HF_TOKEN:
        # Validate token format (should start with hf_)
        if not settings.HF_TOKEN.startswith("hf_"):
            print(f"⚠️ WARNING: HF_TOKEN doesn't start with 'hf_' - might be invalid")
            print(f"   Token value: {settings.HF_TOKEN[:10]}...")
        headers["Authorization"] = f"Bearer {settings.HF_TOKEN}"
        print(f"🔑 Using HF_TOKEN for authentication (token length: {len(settings.HF_TOKEN)}, starts with: {settings.HF_TOKEN[:3]}...)")
    else:
        print("⚠️ No HF_TOKEN configured - trying without authentication")
        print("   Note: Router API may require authentication even for public models")
        print("   Add HF_TOKEN environment variable in Render settings if requests fail")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, text in enumerate(texts):
            try:
                print(f"🔍 Processing text {i+1}/{len(texts)}: {text[:50]}...")
                # Hugging Face Router API expects single input
                # Format: POST with {"inputs": text}
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
                # DO NOT use stub - raise error so we can see what's wrong
                print(f"❌ HF API error for text {i+1}: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                # Raise error instead of using stub
                raise Exception(f"HF API call failed for text {i+1}: {e}") from e
    
    print(f"✅ Processed {len(results)}/{len(texts)} texts via HF API")
    
    # Log summary of classifications
    harmful_count = sum(1 for r in results if r.get("label") == "harmful")
    safe_count = sum(1 for r in results if r.get("label") == "safe")
    print(f"📊 Classification summary: {harmful_count} harmful, {safe_count} safe")
    
    return results


async def analyze_texts(texts: List[str]) -> List[Dict]:
    print(f"📊 analyze_texts called with {len(texts)} texts")
    print(f"🔍 IBTIKAR_URL from settings: {repr(settings.IBTIKAR_URL)}")
    print(f"🔍 HF_TOKEN configured: {bool(settings.HF_TOKEN)}")
    if settings.HF_TOKEN:
        print(f"🔍 HF_TOKEN starts with: {settings.HF_TOKEN[:10]}...")
    
    # If no URL configured, use stub
    if not settings.IBTIKAR_URL:
        print("❌ IBTIKAR_URL not configured - this is why we're using stub classifier!")
        print("   Please set IBTIKAR_URL environment variable in Render settings")
        stub_results = _stub(texts)
        print(f"📊 Stub results (should show harmful for toxic Arabic text, but won't): {stub_results}")
        return stub_results

    url = settings.IBTIKAR_URL.rstrip("/")
    print(f"✅ IBTIKAR_URL is configured: {url}")
    
    # FORCE Inference API format (router API gives 404)
    # Extract model path
    model_path = None
    if "/models/" in url:
        model_path = url.split("/models/")[-1].rstrip("/")
    elif "router.huggingface.co" in url and "/v1/models/" in url:
        model_path = url.split("/v1/models/")[-1].rstrip("/")
    elif "api-inference.huggingface.co" in url:
        model_path = url.split("models/")[-1] if "models/" in url else url.split("/")[-1]
    
    if not model_path:
        model_path = "bisharababish/arabert-toxic-classifier"
    
    # Inference API is DEPRECATED (410 Gone) - MUST use Router API
    # Router API format: https://router.huggingface.co/v1/models/{model_path}
    if "api-inference.huggingface.co" in url:
        print(f"🔄 Converting deprecated Inference API URL to Router API format")
        url = f"https://router.huggingface.co/v1/models/{model_path}"
    elif "router.huggingface.co" not in url:
        # If URL doesn't specify router API, use router
        url = f"https://router.huggingface.co/v1/models/{model_path}"
    
    # Ensure router URL has correct format
    if "router.huggingface.co" in url and "/v1/models/" not in url:
        # Add /v1/ if missing
        if "/models/" in url:
            model_part = url.split("/models/")[-1]
            url = f"https://router.huggingface.co/v1/models/{model_part}"
    
    print(f"✅ Using Hugging Face Router API: {url}")
    print(f"🔍 Original URL was: {settings.IBTIKAR_URL}")

    # Check if it's Hugging Face API
    if _is_huggingface_api(url):
        print(f"✅ Detected as Hugging Face API")
        try:
            # Use Router API URL (Inference API is deprecated)
            results = await _call_huggingface_api(texts, url)
            print(f"📊 HF API returned {len(results)} results")
            
            # Log summary of results
            harmful_count = sum(1 for r in results if r.get("label") == "harmful")
            safe_count = sum(1 for r in results if r.get("label") == "safe")
            print(f"📊 Result summary: {harmful_count} harmful, {safe_count} safe")
            
            # Check if all results are safe/0.7 (stub classifier signature)
            if len(results) > 0 and all(r.get("label") == "safe" and r.get("score") == 0.7 for r in results):
                print(f"❌ WARNING: All results are safe/0.7 - this looks like stub classifier output!")
                print(f"   The API call may have failed silently. Check logs above for errors.")
            return results
        except Exception as e:
            # Re-raise rate limit errors so they can be handled properly
            if "rate limit" in str(e).lower() or "429" in str(e) or "Rate limited" in str(e):
                print(f"❌ Hugging Face API rate limited: {e}")
                raise
            # DO NOT fall back to stub - raise the error so we can see what's wrong
            print(f"❌ Hugging Face API error: {e}")
            import traceback
            traceback.print_exc()
            print(f"❌ NOT using stub classifier - raising error to diagnose the issue")
            raise Exception(f"Hugging Face API failed: {e}. Please check logs and API configuration.") from e

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
