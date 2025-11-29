# Fix for Space API 405 Error

## Problem

Your Space is running, but it's returning **405 Method Not Allowed** when trying to use `/api/predict`. This means the Gradio Space API endpoint is not properly configured to accept POST requests.

**Error from logs:**
```
[405] POST /api/predict
Error: POST method not allowed. No form actions exist for this page
```

## Solution: Use Router API Instead

The **Router API** is more reliable and doesn't have this configuration issue. It's the recommended way to access Hugging Face models.

## How to Fix

### Step 1: Update IBTIKAR_URL in Render

1. Go to: https://dashboard.render.com
2. Click your backend service
3. Click **"Environment"** tab
4. Find `IBTIKAR_URL`
5. Change it to one of these:

**Option 1 (Full Router API URL):**
```
https://router.huggingface.co/v1/models/bisharababish/arabert-toxic-classifier
```

**Option 2 (Just model path - will auto-convert):**
```
bisharababish/arabert-toxic-classifier
```

6. Click **"Save Changes"** (this will trigger a redeploy)

### Step 2: Optional - Set HF_TOKEN (Recommended)

Router API works better with authentication:

1. Get your Hugging Face token:
   - Go to: https://huggingface.co/settings/tokens
   - Create a new token with "Read" permissions
   - Copy the token (starts with `hf_`)

2. In Render, add environment variable:
   - **Key:** `HF_TOKEN`
   - **Value:** `hf_your_token_here`
   - Click **"Save Changes"**

### Step 3: Wait for Redeploy

Wait 2-3 minutes for Render to redeploy with the new settings.

### Step 4: Test

Try your app again. The Router API should work without the 405 error.

## Why Router API is Better

- ✅ More reliable (no sleeping issues)
- ✅ Better error handling
- ✅ No 405 errors
- ✅ Faster response times
- ✅ Official Hugging Face API

## Alternative: Fix the Space API

If you want to keep using the Space API, you need to fix the Gradio app configuration. The issue is that the Space app needs to properly expose the `/api/predict` endpoint. However, using Router API is the recommended solution.

## Summary

**Current (not working):**
```
IBTIKAR_URL=https://bisharababish-arabert-toxic-classifier.hf.space/api/predict
```

**Fixed (use this):**
```
IBTIKAR_URL=https://router.huggingface.co/v1/models/bisharababish/arabert-toxic-classifier
```

Or simply:
```
IBTIKAR_URL=bisharababish/arabert-toxic-classifier
```

The code will automatically convert the model path to the Router API URL.

