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
    return "api-inference.huggingface.co" in url or "router.huggingface.co" in url or "hf.space" in url or "huggingface.co" in url


async def _call_huggingface_api(texts: List[str], url: str) -> List[Dict]:
    """Call Hugging Face Inference API or Space API for each text."""
    results = []
    
    # Check if this is a Space API URL (hf.space)
    is_space_api = "hf.space" in url
    
    # For Space API, ensure we have the /api/predict endpoint
    if is_space_api and "/api/predict" not in url:
        url = url.rstrip("/") + "/api/predict"
        print(f"🔄 Updated Space API URL to: {url}")
    
    # Extract model path from various URL formats (for fallback to Router API)
    model_path = None
    if "/models/" in url:
        model_path = url.split("/models/")[-1].rstrip("/")
    elif "router.huggingface.co" in url and "/v1/models/" in url:
        model_path = url.split("/v1/models/")[-1].rstrip("/")
    elif "api-inference.huggingface.co" in url:
        model_path = url.split("models/")[-1] if "models/" in url else url.split("/")[-1]
    elif is_space_api:
        # Extract model name from Space URL (e.g., bisharababish-arabert-toxic-classifier)
        # Convert Space name to model path: bisharababish-arabert-toxic-classifier -> bisharababish/arabert-toxic-classifier
        space_name = url.split("hf.space")[0].split("//")[-1].split(".")[0]
        # Convert hyphenated space name to model path format
        if "-" in space_name:
            parts = space_name.split("-", 1)  # Split on first hyphen
            model_path = f"{parts[0]}/{parts[1]}" if len(parts) == 2 else space_name.replace("-", "/")
        else:
            model_path = space_name
        print(f"🔄 Converted Space name '{space_name}' to model path: {model_path}")
    
    if not model_path:
        print(f"⚠️ Could not extract model path from URL: {url}")
        model_path = "bisharababish/arabert-toxic-classifier"
    
    print(f"🔍 Extracted model path: {model_path}")
    print(f"🔍 Using URL: {url}")
    print(f"🔍 Is Space API: {is_space_api}")
    
    # Prepare headers with optional authentication
    headers = {"Content-Type": "application/json"}
    # Public Gradio Spaces usually don't need authentication
    # Only add token for Inference API/Router API, not for Space API
    if settings.HF_TOKEN and not is_space_api:
        # Validate token format (should start with hf_)
        if not settings.HF_TOKEN.startswith("hf_"):
            print(f"⚠️ WARNING: HF_TOKEN doesn't start with 'hf_' - might be invalid")
            print(f"   Token value: {settings.HF_TOKEN[:10]}...")
        headers["Authorization"] = f"Bearer {settings.HF_TOKEN}"
        print(f"🔑 Using HF_TOKEN for authentication (token length: {len(settings.HF_TOKEN)}, starts with: {settings.HF_TOKEN[:3]}...)")
    elif is_space_api:
        print("ℹ️  Space API detected - using without authentication (public Spaces don't need auth)")
    else:
        print("⚠️ No HF_TOKEN configured - trying without authentication")
        print("   Note: Router API may require authentication even for public models")
        print("   Add HF_TOKEN environment variable in Render settings if requests fail")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, text in enumerate(texts):
            try:
                print(f"🔍 Processing text {i+1}/{len(texts)}: {text[:50]}...")
                
                # Different request formats for different APIs
                if is_space_api:
                    # Space API (Gradio) expects: {"data": [text]} for function with single text input
                    request_data = {"data": [text]}
                else:
                    # Hugging Face Inference API expects: {"inputs": text}
                    request_data = {"inputs": text}
                
                r = await client.post(
                    url,
                    json=request_data,
                    headers=headers
                )
                
                # Handle model loading (503) - wait and retry
                if r.status_code == 503:
                    wait_time = 20  # Wait 20 seconds for model to load
                    print(f"⏳ Model is loading (503), waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)
                    # Retry once
                    request_data = {"data": [text]} if is_space_api else {"inputs": text}
                    r = await client.post(
                        url,
                        json=request_data,
                        headers=headers
                    )
                
                # Handle 404 or 410 - try Router API as fallback
                # For Space API 404, the Space might be sleeping - retry once with longer wait
                if (r.status_code == 404 or r.status_code == 410) and i == 0:
                    if is_space_api:
                        print(f"⚠️ Space API returned {r.status_code} - Space may be sleeping or not running")
                        print(f"   Error response: {r.text[:200]}")
                        # Free Spaces can sleep - try multiple times with increasing wait times
                        max_retries = 3
                        wait_times = [20, 30, 40]  # Progressive wait times
                        r_retry = None
                        for retry_num in range(max_retries):
                            wait_time = wait_times[retry_num]
                            print(f"🔄 Space might be sleeping, attempt {retry_num + 1}/{max_retries}, waiting {wait_time}s and retrying Space API...")
                            await asyncio.sleep(wait_time)
                            retry_request_data = {"data": [text]}
                            r_retry = await client.post(
                                url,
                                json=retry_request_data,
                                headers=headers
                            )
                            if r_retry.status_code == 200:
                                print(f"✅ Space API woke up after {wait_time}s! Using it for all texts.")
                                r = r_retry
                                break  # Success, exit retry loop
                            elif r_retry.status_code == 503:
                                print(f"⏳ Space is loading (503), waiting 20s more...")
                                await asyncio.sleep(20)
                                r_retry = await client.post(url, json=retry_request_data, headers=headers)
                                if r_retry.status_code == 200:
                                    print(f"✅ Space API works after loading! Using it for all texts.")
                                    r = r_retry
                                    break  # Success, exit retry loop
                                else:
                                    print(f"❌ Space API still loading/failed: {r_retry.status_code}")
                                    # Continue to next retry attempt
                            else:
                                print(f"❌ Space API retry {retry_num + 1} returned {r_retry.status_code}")
                                # Continue to next retry attempt
                        
                        # If all retries failed, fall back to Router API
                        if r_retry is None or r_retry.status_code != 200:
                            print(f"❌ Space API failed after {max_retries} retries")
                            print(f"🔄 Falling back to Router API for model: {model_path}")
                            # Try Router API as fallback
                            router_url = f"https://router.huggingface.co/v1/models/{model_path}"
                            print(f"🔄 Trying Router API: {router_url}")
                            # Prepare headers with authentication for Router API
                            router_headers = {"Content-Type": "application/json"}
                            if settings.HF_TOKEN:
                                router_headers["Authorization"] = f"Bearer {settings.HF_TOKEN}"
                                print(f"🔑 Using HF_TOKEN for Router API authentication")
                            else:
                                print(f"⚠️ No HF_TOKEN - Router API may require authentication")
                            try:
                                router_r = await client.post(
                                    router_url,
                                    json={"inputs": text},
                                    headers=router_headers
                                )
                                if router_r.status_code == 200:
                                    print(f"✅ Router API works! Using it for all texts.")
                                    url = router_url
                                    is_space_api = False
                                    r = router_r
                                elif router_r.status_code == 503:
                                    print(f"⏳ Router API model is loading (503), waiting 20s...")
                                    await asyncio.sleep(20)
                                    router_r = await client.post(
                                        router_url,
                                        json={"inputs": text},
                                        headers=router_headers
                                    )
                                    if router_r.status_code == 200:
                                        print(f"✅ Router API works after wait! Using it for all texts.")
                                        url = router_url
                                        is_space_api = False
                                        r = router_r
                                    else:
                                        error_msg = router_r.text[:200] if router_r.text else f"Status {router_r.status_code}"
                                        raise Exception(f"Router API failed after wait: {error_msg}")
                                else:
                                    error_msg = router_r.text[:200] if router_r.text else f"Status {router_r.status_code}"
                                    raise Exception(f"Router API returned {router_r.status_code}: {error_msg}")
                            except Exception as router_err:
                                print(f"❌ Router API also failed: {router_err}")
                                print(f"❌ All API fallbacks failed. Original Space API error: {r.status_code}")
                                print(f"   Router API error: {router_err}")
                                print(f"   Model path tried: {model_path}")
                                raise Exception(f"All Hugging Face APIs failed. Space API: 404 (may be sleeping), Router API: {router_err}. Please verify the Space is running or the model exists on Hugging Face.") from router_err
                                # Inference API is deprecated (returns 410) - don't try it
                                print(f"⚠️ Inference API is deprecated - skipping fallback")
                                print(f"❌ All API fallbacks failed. Original Space API error: {r.status_code}")
                                print(f"   Router API error: {router_err}")
                                print(f"   Model path tried: {model_path}")
                                print(f"   Possible issues:")
                                print(f"     1. Model '{model_path}' doesn't exist on Hugging Face")
                                print(f"     2. Model is private and requires authentication")
                                print(f"     3. Space '{url}' doesn't exist or isn't running")
                                raise Exception(f"All Hugging Face APIs failed. Space API: 404, Router API: 404 (model '{model_path}' not found). Please verify the model exists on Hugging Face or update IBTIKAR_URL to point to a valid model/Space.") from router_err
                    else:
                        # Router API fallback for non-Space API URLs
                        print(f"⚠️ API returned {r.status_code}, trying Router API as fallback...")
                        router_url = f"https://router.huggingface.co/v1/models/{model_path}"
                        print(f"🔄 Trying Router API: {router_url}")
                        router_r = await client.post(
                            router_url,
                            json={"inputs": text},  # Router API uses Inference API format
                            headers=headers
                        )
                        # If Router API works, use it for all remaining texts
                        if router_r.status_code == 200:
                            print(f"✅ Router API works! Using it for all texts.")
                            url = router_url  # Update URL for remaining texts
                            r = router_r  # Use Router API response
                        elif router_r.status_code == 503:
                            # Model loading on Router API, wait and retry
                            print(f"⏳ Router API model is loading (503), waiting 20s...")
                            await asyncio.sleep(20)
                            router_r = await client.post(
                                router_url,
                                json={"inputs": text},
                                headers=headers
                            )
                            if router_r.status_code == 200:
                                print(f"✅ Router API works after waiting! Using it for all texts.")
                                url = router_url
                                r = router_r
                            else:
                                print(f"❌ Router API still loading or failed: {router_r.status_code}")
                                raise Exception(f"Router API not available: {router_r.status_code} - {router_r.text[:200] if router_r.text else 'No error text'}")
                        else:
                            print(f"❌ Router API also failed with {router_r.status_code}")
                            error_msg = router_r.text[:200] if router_r.text else 'No error text'
                            print(f"   Error: {error_msg}")
                            # Raise error with both attempts
                            raise Exception(f"API ({r.status_code}) and Router API ({router_r.status_code}) both failed. Router error: {error_msg}")
                
                # For Space API, handle errors - but skip if 404/410 (already handled with fallback above)
                # Only raise for other error codes
                if is_space_api and r.status_code != 200 and r.status_code != 404 and r.status_code != 410:
                    error_text = r.text[:500] if r.text else "No error text"
                    print(f"❌ Space API returned {r.status_code}")
                    print(f"   URL: {url}")
                    print(f"   Request data: {request_data}")
                    print(f"   Response: {error_text}")
                    print(f"   Headers: {dict(r.headers)}")
                    raise Exception(
                        f"Space API returned {r.status_code}: {error_text}. "
                        f"URL: {url}. "
                        f"Check if the Space is running and accessible."
                    )
                
                # If still 404/410 after Router API attempt, provide helpful error
                if (r.status_code == 404 or r.status_code == 410):
                    error_text = r.text[:500] if r.text else "No error text"
                    raise Exception(
                        f"HF API HTTP {r.status_code}: Model not found or not accessible. "
                        f"Error: {error_text}. "
                        f"NOTE: If your model files on Hugging Face are Git LFS pointers (not actual files), "
                        f"the Inference API cannot load them. You need to upload the actual model files (~540MB) to Hugging Face."
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
                    request_data = {"data": [text]} if is_space_api else {"inputs": text}
                    r = await client.post(
                        url,
                        json=request_data,
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
                
                # Handle Gradio Space API response format
                # Gradio returns: {"data": [result]} where result is what the function returns
                if is_space_api and isinstance(data, dict) and "data" in data:
                    data = data["data"]
                    if isinstance(data, list) and len(data) > 0:
                        data = data[0]  # Get the actual result
                    if i == 0:
                        print(f"📋 Unwrapped Gradio response: {data}")
                
                # Handle different response formats from HF API
                # HF classification models can return:
                # - List of lists: [[{"label": "LABEL_0", "score": 0.95}, {"label": "LABEL_1", "score": 0.05}]]
                # - List of dicts: [{"label": "LABEL_0", "score": 0.95}, {"label": "LABEL_1", "score": 0.05}]
                # - Single dict: {"label": "LABEL_1", "score": 0.65}
                # Space API (already mapped): [{"label": "harmful", "score": 0.95}] or {"label": "harmful", "score": 0.95}
                
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
                        # Handle two formats:
                        # 1. HF Inference API: [{"label": "LABEL_0", "score": 0.95}, {"label": "LABEL_1", "score": 0.05}]
                        # 2. Space API (already mapped): [{"label": "harmful", "score": 0.95}] or [{"label": "safe", "score": 0.95}]
                        
                        # Check if response is already in mapped format (harmful/safe)
                        first_item = data[0] if isinstance(data[0], dict) else None
                        if first_item:
                            label_str = str(first_item.get("label", "")).lower()
                            # If it's already "harmful" or "safe", use it directly
                            if label_str in ["harmful", "safe", "unknown"]:
                                score = float(first_item.get("score", 0.5))
                                label_mapped = label_str
                                if i == 0:
                                    print(f"✅ Space API format (already mapped): {label_mapped} (score={score:.4f})")
                                results.append({"label": label_mapped, "score": float(score)})
                                continue
                        
                        # Otherwise, handle HF Inference API format (LABEL_0/LABEL_1)
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
                        # Single dict response - could be HF API or Space API format
                        label = str(data.get("label", "")).lower()
                        score = float(data.get("score", 0.5))
                        
                        # Check if already mapped (harmful/safe) or needs mapping (LABEL_0/LABEL_1)
                        if label in ["harmful", "safe", "unknown"]:
                            label_mapped = label
                        else:
                            # Map from LABEL format
                            label_upper = label.upper()
                            label_mapped = "harmful" if ("LABEL_1" in label_upper or "TOXIC" in label_upper or "1" in label_upper) else "safe"
                        
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
                print(f"   URL tried: {url}")
                
                # Try Router API as last resort if we haven't already
                if (e.response.status_code == 404 or e.response.status_code == 410) and i == 0 and "router.huggingface.co" not in url:
                    print(f"🔄 Trying Router API as fallback...")
                    try:
                        router_url = f"https://router.huggingface.co/v1/models/{model_path}"
                        router_r = await client.post(
                            router_url,
                            json={"inputs": text},
                            headers=headers
                        )
                        if router_r.status_code == 200 or router_r.status_code == 503:
                            print(f"✅ Router API works! Using it for all texts.")
                            url = router_url
                            # If 503, wait and retry
                            if router_r.status_code == 503:
                                await asyncio.sleep(20)
                                router_r = await client.post(router_url, json={"inputs": text}, headers=headers)  # Router API format
                            r = router_r
                            # Continue processing this text
                            continue
                    except Exception as router_e:
                        print(f"❌ Router API also failed: {router_e}")
                
                # If we get here, both APIs failed
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
    
    # If URL is just a model path (like "Bisharababish/arabert-toxic-classifier"),
    # convert it to Router API URL (Inference API is deprecated)
    if not url.startswith("http") and "/" in url and not url.startswith("/"):
        print(f"🔄 Converting model path to Router API URL")
        url = f"https://router.huggingface.co/v1/models/{url}"
        print(f"✅ Using Router API URL: {url}")
        print(f"ℹ️  Router API is the current recommended API (Inference API is deprecated)")
    else:
        print(f"✅ Using URL as configured: {url}")

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
