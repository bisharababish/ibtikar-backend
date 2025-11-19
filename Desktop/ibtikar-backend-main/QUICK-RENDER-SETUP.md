# Quick Render Setup Guide

## Step 1: Push Code to GitHub

1. Make sure your code is in a Git repository
2. Push to GitHub (if not already there)

## Step 2: Sign Up for Render

1. Go to: https://render.com
2. Sign up with GitHub (free account)

## Step 3: Create Web Service

1. Click **"New +"** → **"Web Service"**
2. Connect your GitHub repository
3. Select the `ibtikar-backend-main` repository

## Step 4: Configure

**Settings:**
- **Name:** `ibtikar-backend`
- **Environment:** `Python 3`
- **Region:** Choose closest
- **Branch:** `main`

**Build & Start:**
- **Build Command:** `pip install -r requirements-prod.txt`
- **Start Command:** `uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT`

**Environment Variables** (click "Add Environment Variable" for each):

```
ENV=production
X_CLIENT_ID=your_twitter_client_id_from_env
X_REDIRECT_URI=https://ibtikar-backend.onrender.com/v1/oauth/x/callback
FERNET_KEY=your_fernet_key_from_env
IBTIKAR_URL=http://localhost:9000
```

**Note:** Replace `ibtikar-backend` with your actual service name after deployment!

## Step 5: Deploy

1. Click **"Create Web Service"**
2. Wait 5-10 minutes for deployment
3. Copy your URL (e.g., `https://ibtikar-backend-xxxx.onrender.com`)

## Step 6: Update Twitter

1. Go to Twitter Developer Portal
2. Update **Callback URI** to: `https://your-render-url.onrender.com/v1/oauth/x/callback`
3. Update **Website URL** to: `https://your-render-url.onrender.com`
4. **Save**

## Step 7: Update Render Environment Variables

1. Go back to Render dashboard
2. Update `X_REDIRECT_URI` with your actual Render URL
3. Click **"Save Changes"** (will redeploy)

## Step 8: Update Expo App

1. Update `.env` file:
```
EXPO_PUBLIC_BACKEND_URL=https://your-render-url.onrender.com
```

2. Restart Expo: `npx expo start --clear`

## Done! 

No more ngrok warning page! 🎉

**Note:** Free tier sleeps after 15 min inactivity (first request will be slow to wake up)

