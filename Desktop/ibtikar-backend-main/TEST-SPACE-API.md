# Test Space API - Quick Guide

## Step 1: Test Space API Directly

The Space is running! Now let's test if the API endpoint works.

**Option A: Use your browser**
1. Go to: https://bisharababish-arabert-toxic-classifier.hf.space
2. Type some Arabic text in the text box
3. Click "Classify"
4. Should return a prediction ✅

**Option B: Test API endpoint (if you have curl)**
```bash
curl -X POST https://bisharababish-arabert-toxic-classifier.hf.space/api/predict \
  -H "Content-Type: application/json" \
  -d '{"data": ["test"]}'
```

## Step 2: Update Render Configuration

1. Go to: https://dashboard.render.com
2. Click your backend service
3. Click "Environment" tab
4. Find `IBTIKAR_URL`
5. Set it to: `https://bisharababish-arabert-toxic-classifier.hf.space`
6. Click "Save Changes"
7. Wait 2-3 minutes for redeploy

## Step 3: Test Your App

1. Open your Expo app
2. Make sure you're logged in
3. Go to main screen
4. Toggle AI activation
5. Wait 30-60 seconds
6. Check if it works!

## What to Check

- [ ] Space UI works (can classify text in browser)
- [ ] IBTIKAR_URL is set in Render
- [ ] Backend redeployed
- [ ] Mobile app works (no errors)

