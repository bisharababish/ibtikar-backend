# Complete Render Deployment Guide

## ✅ What's Already Configured

- ✅ `requirements-prod.txt` - Production dependencies (includes PostgreSQL driver)
- ✅ `render.yaml` - Render configuration file
- ✅ Database session updated to support PostgreSQL
- ✅ Backend code ready for deployment

## Step 1: Push Code to GitHub

```bash
cd C:\Users\Leo\Desktop\ibtikar-backend-main
git init  # if not already a git repo
git add .
git commit -m "Prepare for Render deployment"
git remote add origin YOUR_GITHUB_REPO_URL
git push -u origin main
```

## Step 2: Sign Up for Render

1. Go to: https://render.com
2. Sign up with GitHub
3. Authorize Render to access your repositories

## Step 3: Create Database (Optional but Recommended)

1. In Render dashboard, click **"New +"** → **"PostgreSQL"**
2. Name: `ibtikar-db`
3. Database: `ibtikar`
4. User: `ibtikar`
5. Plan: **Free** (or paid if you want)
6. Click **"Create Database"**
7. **Copy the Internal Database URL** (you'll need this)

## Step 4: Create Web Service

1. Click **"New +"** → **"Web Service"**
2. Connect your GitHub account if not already
3. Select your repository: `ibtikar-backend-main`
4. Click **"Connect"**

## Step 5: Configure Service

**Basic Settings:**
- **Name:** `ibtikar-backend`
- **Environment:** `Python 3`
- **Region:** Choose closest (e.g., `Oregon (US West)`)
- **Branch:** `main`

**Build & Deploy:**
- **Build Command:** `pip install -r requirements-prod.txt`
- **Start Command:** `uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT`

**Environment Variables:**
Click **"Add Environment Variable"** for each:

1. **ENV**
   - Key: `ENV`
   - Value: `production`

2. **X_CLIENT_ID**
   - Key: `X_CLIENT_ID`
   - Value: `YOUR_TWITTER_CLIENT_ID` (from your local .env file)

3. **X_REDIRECT_URI** (Update after deployment!)
   - Key: `X_REDIRECT_URI`
   - Value: `https://ibtikar-backend.onrender.com/v1/oauth/x/callback`
   - **Note:** Replace `ibtikar-backend` with your actual service name!

4. **FERNET_KEY**
   - Key: `FERNET_KEY`
   - Value: `YOUR_FERNET_KEY` (from your local .env file)

5. **IBTIKAR_URL** (Optional - for model API)
   - Key: `IBTIKAR_URL`
   - Value: `http://localhost:9000` (or your model API URL)

6. **DATABASE_URL** (If you created a database)
   - Key: `DATABASE_URL`
   - Value: `YOUR_POSTGRESQL_CONNECTION_STRING` (from Render database dashboard)
   - OR: Link it in render.yaml (already configured)

## Step 6: Deploy

1. Click **"Create Web Service"**
2. Wait 5-10 minutes for first deployment
3. Watch the build logs for any errors
4. Once deployed, copy your service URL (e.g., `https://ibtikar-backend-xxxx.onrender.com`)

## Step 7: Update Environment Variables with Actual URL

1. Go to your service in Render dashboard
2. Click **"Environment"** tab
3. Find `X_REDIRECT_URI`
4. Update it to: `https://YOUR-ACTUAL-SERVICE-URL.onrender.com/v1/oauth/x/callback`
5. Click **"Save Changes"** (this will trigger a redeploy)

## Step 8: Update Twitter Developer Portal

1. Go to: https://developer.twitter.com/en/portal/dashboard
2. Click your app
3. Go to **Settings** → **User authentication settings**
4. Click **"Edit"**
5. Update **Callback URI / Redirect URL** to:
   ```
   https://YOUR-ACTUAL-SERVICE-URL.onrender.com/v1/oauth/x/callback
   ```
6. Update **Website URL** to:
   ```
   https://YOUR-ACTUAL-SERVICE-URL.onrender.com
   ```
7. Click **"Save"**

## Step 9: Update Expo App

1. Update your Expo `.env` file:
   ```
   EXPO_PUBLIC_BACKEND_URL=https://YOUR-ACTUAL-SERVICE-URL.onrender.com
   ```

2. Restart Expo:
   ```bash
   cd C:\Users\Leo\Desktop\ibtikarapp\ibtikar
   npx expo start --clear
   ```

## Step 10: Test!

1. Open your Expo app
2. Click "Login with Twitter"
3. **No more ngrok warning!** 🎉
4. Complete OAuth flow
5. Should work perfectly!

## Troubleshooting

**Build fails:**
- Check build logs in Render dashboard
- Make sure `requirements-prod.txt` has all dependencies
- Verify Python version (Render uses Python 3.11 by default)

**Service won't start:**
- Check logs in Render dashboard
- Verify start command is correct
- Make sure all environment variables are set

**Database errors:**
- Make sure DATABASE_URL is set correctly
- Check database is created and running
- Verify connection string format

**OAuth not working:**
- Double-check X_REDIRECT_URI matches Twitter callback URL exactly
- Make sure you updated Twitter settings after deployment
- Check Render logs for OAuth errors

## Notes

- **Free tier:** Services sleep after 15 minutes of inactivity
- **First request:** May be slow (30-60 seconds) if service is sleeping
- **Upgrade:** $7/month keeps service always running
- **Database:** Free for 90 days, then $7/month

## Success Checklist

- [ ] Code pushed to GitHub
- [ ] Render account created
- [ ] Database created (optional)
- [ ] Web service deployed
- [ ] Environment variables set
- [ ] X_REDIRECT_URI updated with actual URL
- [ ] Twitter callback URL updated
- [ ] Expo app .env updated
- [ ] OAuth login tested and working!

