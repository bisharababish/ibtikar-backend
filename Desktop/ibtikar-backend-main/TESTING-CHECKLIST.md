# Complete Testing Checklist

## ✅ Step 1: Verify Space is Running

1. **Check Space Status:**
   - Go to: https://huggingface.co/spaces/Bisharababish/arabert-toxic-classifier
   - Should show "Running" status ✅

2. **Test Space UI:**
   - Visit: https://bisharababish-arabert-toxic-classifier.hf.space
   - Try typing some Arabic text
   - Should return predictions ✅

## ✅ Step 2: Test Space API Endpoint

Test if the API endpoint works:

**Using curl (in terminal/PowerShell):**
```bash
curl -X POST https://bisharababish-arabert-toxic-classifier.hf.space/api/predict \
  -H "Content-Type: application/json" \
  -d "{\"data\": [\"هذا نص تجريبي\"]}"
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

**If you get 200 OK:** ✅ API is working!
**If you get 405:** ❌ API endpoint issue (we'll fix this)
**If you get 404:** ❌ Space might be sleeping

## ✅ Step 3: Update Backend Configuration

1. **Go to Render Dashboard:**
   - Visit: https://dashboard.render.com
   - Click your backend service

2. **Update IBTIKAR_URL:**
   - Go to "Environment" tab
   - Find `IBTIKAR_URL`
   - Set it to: `https://bisharababish-arabert-toxic-classifier.hf.space`
   - Click "Save Changes"
   - Wait 2-3 minutes for redeploy

## ✅ Step 4: Test Backend API

After Render redeploys, test the backend:

**Test the preview endpoint:**
```bash
curl -X POST "https://ibtikar-backend.onrender.com/v1/analysis/preview?user_id=1&authors_limit=5&per_batch=5"
```

**Check Render logs:**
- Go to Render dashboard → Your service → "Logs" tab
- Look for:
  - ✅ `✅ IBTIKAR_URL is configured: https://bisharababish-arabert-toxic-classifier.hf.space`
  - ✅ `✅ Detected as Hugging Face API`
  - ✅ `✅ Space API works! Using it for all texts.`
  - ❌ If you see errors, note them down

## ✅ Step 5: Test Your Mobile App

1. **Open your Expo app**
2. **Login with Twitter** (if not already logged in)
3. **Go to main screen**
4. **Toggle the AI activation button**
5. **Wait for processing** (may take 30-60 seconds if Space is sleeping)
6. **Check results:**
   - Should see posts classified as "harmful" or "safe"
   - Should NOT see errors

## ✅ Step 6: Verify Everything Works

### Check These Things:

- [ ] Space is running (green status)
- [ ] Space UI works (can classify text in browser)
- [ ] Space API works (curl test returns 200)
- [ ] IBTIKAR_URL is set in Render
- [ ] Backend redeployed successfully
- [ ] Backend logs show Space API is being used
- [ ] Mobile app can activate AI
- [ ] Mobile app shows classifications (not errors)
- [ ] Toxic Arabic text is marked as "harmful"
- [ ] Safe text is marked as "safe"

## 🔧 Troubleshooting

### If Space API returns 405:
- The endpoint might need a different format
- Check backend logs for exact error
- Try using the Space URL without `/api/predict` (code will add it)

### If Space API returns 404:
- Space might be sleeping
- Visit the Space in browser to wake it up
- Wait 30-60 seconds and try again

### If Backend returns 500:
- Check Render logs for detailed error
- Verify IBTIKAR_URL is set correctly
- Make sure Space is running

### If Mobile app shows errors:
- Check backend logs in Render
- Verify Twitter API rate limits aren't exceeded
- Check network connectivity

## 📋 Quick Test Commands

**Test Space API:**
```bash
curl -X POST https://bisharababish-arabert-toxic-classifier.hf.space/api/predict \
  -H "Content-Type: application/json" \
  -d "{\"data\": [\"test\"]}"
```

**Test Backend:**
```bash
curl -X POST "https://ibtikar-backend.onrender.com/v1/analysis/preview?user_id=1&authors_limit=3&per_batch=3"
```

## ✅ Success Criteria

Everything is working if:
1. ✅ Space API returns 200 with predictions
2. ✅ Backend logs show "Space API works!"
3. ✅ Mobile app shows classifications (not errors)
4. ✅ Toxic text is correctly identified as "harmful"
5. ✅ Safe text is correctly identified as "safe"

## 🎯 Next Steps After Testing

Once everything works:
1. Test with real Twitter feed
2. Verify classifications are accurate
3. Monitor for any rate limits
4. Check performance (response times)


