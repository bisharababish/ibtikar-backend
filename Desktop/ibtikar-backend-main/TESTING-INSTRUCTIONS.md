# Testing Instructions for Toxicity Classification

## ✅ Step 1: Verify Environment Variables in Render

Go to your Render dashboard → Service Settings → Environment Variables:

**Required:**
- `IBTIKAR_URL` = `https://api-inference.huggingface.co/models/bisharababish/arabert-toxic-classifier`
  OR `https://router.huggingface.co/v1/models/bisharababish/arabert-toxic-classifier` (will auto-convert)
- `HF_TOKEN` = `hf_your_token_here` (must start with `hf_`)

## ✅ Step 2: Wait for Deployment

After pushing code, wait 2-3 minutes for Render to:
1. Build the new code
2. Deploy it
3. Start the service

Check the Render logs to see: `Your service is live 🎉`

## ✅ Step 3: Test the Endpoint

**URL:** `POST https://ibtikar-backend.onrender.com/v1/analysis/preview?user_id=1&authors_limit=5&per_batch=5`

**Expected Results:**
- Toxic Arabic text like "سأكسر رأسك وأحرق بيتك" should return `"label": "harmful"` with score > 0.5
- Safe text should return `"label": "safe"` with appropriate score
- You should see a mix of harmful and safe classifications (NOT all "safe" with 0.7)

## ✅ Step 4: Check Logs

If you get an error or all "safe" results:

1. Go to Render dashboard → Logs
2. Look for these log messages:
   - `🔄 FORCING Inference API format: https://api-inference.huggingface.co/models/...`
   - `🔍 Using Hugging Face Inference API: ...`
   - `🔍 Processing text 1/5: ...`
   - `📋 HF API response for text 1: ...`
   - `✅ Final decision: harmful (score=...)` or `safe (score=...)`

**If you see errors:**
- `❌ HF API HTTP error: 404` → Model URL is wrong
- `❌ HF API HTTP error: 401` → HF_TOKEN is invalid/expired
- `❌ HF API HTTP error: 429` → Rate limited, wait and retry
- `❌ IBTIKAR_URL not configured` → Environment variable missing

## ✅ Step 5: What Should Work

After the fix:
- ✅ All router API URLs automatically convert to Inference API format
- ✅ Errors are raised instead of silently falling back to stub
- ✅ Detailed logging shows exactly what's happening
- ✅ Toxic Arabic text should be correctly classified as "harmful"

## 🔧 Troubleshooting

**All posts still showing as "safe" with 0.7:**
- Check logs for API errors
- Verify HF_TOKEN is valid (starts with `hf_`)
- Verify IBTIKAR_URL is set in Render

**Getting 404 errors:**
- The code should auto-convert to Inference API format
- If still 404, manually set IBTIKAR_URL to: `https://api-inference.huggingface.co/models/bisharababish/arabert-toxic-classifier`

**Getting 401 errors:**
- Regenerate your Hugging Face token
- Make sure it has "Read" permissions
- Update HF_TOKEN in Render

**No logs showing:**
- Wait a few more minutes for deployment
- Try the endpoint again
- Check Render logs in real-time

