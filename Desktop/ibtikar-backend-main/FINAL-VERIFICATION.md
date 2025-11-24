# Final Verification Checklist - Harmful Posts Detection

## ✅ Pre-Deployment Checklist

- [x] `app.py` uploaded to Hugging Face Space
- [x] `requirements.txt` includes: gradio, transformers, torch, sentencepiece, accelerate
- [x] `IBTIKAR_URL` environment variable set in backend
- [x] Space is building/running
- [ ] Space build completed successfully
- [ ] Backend can connect to Space API

## 🧪 Step-by-Step Testing Guide

### Step 1: Verify Space is Running

1. Go to your Space: `https://huggingface.co/spaces/Bisharababish/arabert-toxic-classifier`
2. Check the **Logs** tab - should show:
   - ✅ Model loaded successfully!
   - 📋 Model label mapping: {...}
   - No errors

3. Test the Space UI directly:
   - Enter test text: `انت غبي وما تفهم شي` (should be harmful)
   - Enter test text: `مرحبا بك كيف حالك` (should be safe)
   - Verify it returns correct labels

### Step 2: Test Space API Directly

Test the API endpoint with curl or Postman:

```bash
# Test harmful text
curl -X POST https://bisharababish-arabert-toxic-classifier.hf.space/api/predict \
  -H "Content-Type: application/json" \
  -d '{"data": ["انت غبي وما تفهم شي"]}'

# Expected response:
# {"data": [{"label": "harmful", "score": 0.95}]}

# Test safe text
curl -X POST https://bisharababish-arabert-toxic-classifier.hf.space/api/predict \
  -H "Content-Type: application/json" \
  -d '{"data": ["مرحبا بك كيف حالك"]}'

# Expected response:
# {"data": [{"label": "safe", "score": 0.95}]}
```

**✅ If both return correct labels, Space API is working!**

### Step 3: Verify Backend Environment Variable

1. Go to Render.com dashboard (or your hosting platform)
2. Navigate to Environment Variables
3. Verify `IBTIKAR_URL` is set to:
   ```
   https://bisharababish-arabert-toxic-classifier.hf.space/api/predict
   ```
   OR just:
   ```
   https://bisharababish-arabert-toxic-classifier.hf.space
   ```
   (Backend will auto-append `/api/predict`)

### Step 4: Test Backend API

Test your backend endpoint:

```bash
curl -X POST 'https://ibtikar-backend.onrender.com/v1/analysis/preview?user_id=1&authors_limit=5&per_batch=5' \
  -H 'accept: application/json' \
  -d ''
```

**Expected Response:**
```json
{
  "items": [
    {
      "post": {...},
      "label": "harmful",  // or "safe"
      "score": 0.95
    },
    ...
  ],
  "harmful_count": 2,
  "safe_count": 3,
  "unknown_count": 0
}
```

**✅ If you see `harmful_count > 0` for posts with toxic content, it's working!**

### Step 5: Check Backend Logs

Look for these log messages in your backend logs:

```
✅ IBTIKAR_URL is configured: https://...
✅ Detected as Hugging Face API
✅ Space API format (already mapped): harmful (score=0.95)
📊 Classification summary: 2 harmful, 3 safe
```

**✅ If logs show correct detection, everything is working!**

## 🔍 Troubleshooting

### Issue: Space shows "error" status
**Solution:**
- Check Logs tab in Space
- Look for model loading errors
- Verify model files are actual files (not LFS pointers)
- Check if `model.safetensors` is ~540MB (not 137 bytes)

### Issue: Backend returns 500 error
**Solution:**
- Check backend logs for API call errors
- Verify `IBTIKAR_URL` is correct
- Make sure Space is running (not in error state)
- Check if Space API is accessible from backend

### Issue: All posts detected as "safe"
**Solution:**
- Check Space logs to see what labels model returns
- Test Space API directly to verify it returns "harmful" for toxic text
- Check backend logs for response parsing
- Verify the model is actually detecting harmful content

### Issue: Backend can't connect to Space
**Solution:**
- Verify Space URL is correct
- Check if Space requires authentication (usually doesn't for public Spaces)
- Test Space API directly from your machine
- Check backend network/firewall settings

## ✅ Success Criteria

Your system is working correctly when:

1. ✅ Space loads without errors
2. ✅ Space API returns `{"label": "harmful", ...}` for toxic Arabic text
3. ✅ Space API returns `{"label": "safe", ...}` for normal Arabic text
4. ✅ Backend successfully calls Space API
5. ✅ Backend returns `harmful_count > 0` when analyzing posts with toxic content
6. ✅ Backend logs show correct label detection

## 📊 Expected Behavior

### For Harmful Posts (Toxic Arabic Text):
- Model returns: `LABEL_1` with high score
- Space API returns: `{"label": "harmful", "score": 0.95}`
- Backend returns: `{"label": "harmful", "score": 0.95}`
- Analysis shows: `harmful_count` increases

### For Safe Posts (Normal Arabic Text):
- Model returns: `LABEL_0` with high score
- Space API returns: `{"label": "safe", "score": 0.95}`
- Backend returns: `{"label": "safe", "score": 0.95}`
- Analysis shows: `safe_count` increases

## 🎯 Final Verification

Once your Space build is complete:

1. **Test Space API** → Should return harmful/safe correctly
2. **Test Backend API** → Should call Space and return results
3. **Check Logs** → Should show correct label detection
4. **Verify Counts** → `harmful_count` should be > 0 for toxic posts

**If all 4 steps pass, you're done! 🎉**

