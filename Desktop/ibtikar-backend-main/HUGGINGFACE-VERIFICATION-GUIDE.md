# Hugging Face Space Verification Guide

## ✅ Step 1: Check Your Space Status

1. **Visit your Space page:**
   - URL: https://huggingface.co/spaces/Bisharababish/arabert-toxic-classifier
   - **What to look for:** It should show "Running" status (green indicator)
   - **If it shows "Sleeping":** Click the "Play" button or refresh the page to wake it up

2. **Test the Space directly:**
   - Visit: https://bisharababish-arabert-toxic-classifier.hf.space
   - You should see a Gradio interface where you can type text and test it
   - Try typing some Arabic text to verify it's working

## ✅ Step 2: Test the Space API Endpoint

You can test the API endpoint directly using curl or a tool like Postman:

**Using curl (in terminal/PowerShell):**
```bash
curl -X POST https://bisharababish-arabert-toxic-classifier.hf.space/api/predict \
  -H "Content-Type: application/json" \
  -d '{"data": ["هذا نص تجريبي"]}'
```

**Expected response:**
```json
{
  "data": [
    [
      {"label": "safe", "score": 0.95},
      {"label": "harmful", "score": 0.05}
    ]
  ]
}
```

**If you get 404:**
- The Space is sleeping - wait 30-60 seconds and try again
- Or visit https://bisharababish-arabert-toxic-classifier.hf.space in your browser first to wake it up

## ✅ Step 3: Verify Render Environment Variables

1. **Go to Render Dashboard:**
   - Visit: https://dashboard.render.com
   - Log in to your account
   - Click on your backend service (e.g., `ibtikar-backend`)

2. **Check Environment Variables:**
   - Click on **"Environment"** tab
   - Look for `IBTIKAR_URL` variable
   - **It should be set to one of these:**
     - ✅ `https://bisharababish-arabert-toxic-classifier.hf.space/api/predict` (Space API - recommended)
     - ✅ `https://bisharababish-arabert-toxic-classifier.hf.space` (Space URL - will auto-add /api/predict)
     - ✅ `https://router.huggingface.co/v1/models/bisharababish/arabert-toxic-classifier` (Router API - fallback)
     - ✅ `bisharababish/arabert-toxic-classifier` (Model path - will auto-convert to Router API)

3. **If IBTIKAR_URL is missing or wrong:**
   - Click **"Add Environment Variable"** or **"Edit"**
   - **Key:** `IBTIKAR_URL`
   - **Value:** `https://bisharababish-arabert-toxic-classifier.hf.space/api/predict`
   - Click **"Save Changes"** (this will trigger a redeploy)

4. **Optional: Set HF_TOKEN (if using Router API):**
   - If you want to use Router API as fallback, you can set `HF_TOKEN`
   - Get your token from: https://huggingface.co/settings/tokens
   - **Key:** `HF_TOKEN`
   - **Value:** `hf_your_token_here` (must start with `hf_`)

## ✅ Step 4: Wake Up the Space (If Sleeping)

Free Hugging Face Spaces sleep after ~1 hour of inactivity. To wake it up:

1. **Method 1: Visit the Space in browser**
   - Go to: https://bisharababish-arabert-toxic-classifier.hf.space
   - Wait 30-60 seconds for it to wake up
   - You should see the Gradio interface load

2. **Method 2: Make an API call**
   - The backend code will automatically retry with longer wait times (30s, 45s, 60s)
   - But it's faster to wake it up manually first

## ✅ Step 5: Test Your Backend API

After setting the environment variables and waking up the Space:

1. **Wait for Render to redeploy** (2-3 minutes after saving environment variables)

2. **Test the preview endpoint:**
   ```bash
   curl -X POST "https://ibtikar-backend.onrender.com/v1/analysis/preview?user_id=1&authors_limit=5&per_batch=5"
   ```

3. **Check Render logs:**
   - Go to Render dashboard → Your service → **"Logs"** tab
   - Look for these messages:
     - ✅ `✅ IBTIKAR_URL is configured: https://bisharababish-arabert-toxic-classifier.hf.space/api/predict`
     - ✅ `✅ Detected as Hugging Face API`
     - ✅ `✅ Space API works! Using it for all texts.`
     - ❌ If you see errors, they'll tell you what's wrong

## 🔧 Troubleshooting

### Error: "Space API: 404 (may be sleeping)"

**Solution:**
1. Visit https://bisharababish-arabert-toxic-classifier.hf.space in your browser
2. Wait 30-60 seconds
3. Try your API call again

### Error: "Router API returned 404: Not Found"

**Possible causes:**
1. Model path is wrong - should be `bisharababish/arabert-toxic-classifier`
2. Model doesn't exist - verify at: https://huggingface.co/Bisharababish/arabert-toxic-classifier

**Solution:**
- Make sure `IBTIKAR_URL` is set to the Space URL (not Router API)
- Space URL: `https://bisharababish-arabert-toxic-classifier.hf.space/api/predict`

### Error: "IBTIKAR_URL not configured"

**Solution:**
- Go to Render dashboard → Environment Variables
- Add `IBTIKAR_URL` with value: `https://bisharababish-arabert-toxic-classifier.hf.space/api/predict`
- Save and wait for redeploy

### Space keeps sleeping

**Solutions:**
1. **Upgrade to paid Space** (keeps it always running) - $0.60/month
2. **Use Router API instead** - Set `IBTIKAR_URL` to: `https://router.huggingface.co/v1/models/bisharababish/arabert-toxic-classifier`
   - Requires `HF_TOKEN` to be set
   - Router API doesn't sleep but may have rate limits

## 📋 Quick Checklist

- [ ] Space shows "Running" at https://huggingface.co/spaces/Bisharababish/arabert-toxic-classifier
- [ ] Space API works: https://bisharababish-arabert-toxic-classifier.hf.space
- [ ] `IBTIKAR_URL` is set in Render environment variables
- [ ] `IBTIKAR_URL` value is: `https://bisharababish-arabert-toxic-classifier.hf.space/api/predict`
- [ ] Render service has been redeployed after setting environment variables
- [ ] Tested the preview endpoint and it works

## 🎯 Recommended Configuration

**For best results, use the Space API:**

```
IBTIKAR_URL=https://bisharababish-arabert-toxic-classifier.hf.space/api/predict
```

**Or just the Space URL (will auto-add /api/predict):**

```
IBTIKAR_URL=https://bisharababish-arabert-toxic-classifier.hf.space
```

**Optional fallback (Router API - requires HF_TOKEN):**

```
IBTIKAR_URL=https://router.huggingface.co/v1/models/bisharababish/arabert-toxic-classifier
HF_TOKEN=hf_your_token_here
```

