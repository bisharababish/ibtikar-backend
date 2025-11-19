# Deploy Backend to Render

## Step 1: Prepare Your Code

1. Make sure your code is in a Git repository (GitHub, GitLab, or Bitbucket)
2. Push all your code to the repository

## Step 2: Create Render Account

1. Go to: https://render.com
2. Sign up (free account works)
3. Connect your GitHub/GitLab account

## Step 3: Create New Web Service

1. Click "New +" → "Web Service"
2. Connect your repository
3. Select the repository with your backend code

## Step 4: Configure the Service

**Basic Settings:**
- **Name:** `ibtikar-backend` (or any name you want)
- **Environment:** `Python 3`
- **Region:** Choose closest to you
- **Branch:** `main` (or your main branch)

**Build & Deploy:**
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT`

**Environment Variables:**
Add these in the Render dashboard:

```
ENV=production
X_CLIENT_ID=your_twitter_client_id_here
X_REDIRECT_URI=https://your-render-url.onrender.com/v1/oauth/x/callback
FERNET_KEY=your_fernet_key_here
IBTIKAR_URL=http://localhost:9000
DATABASE_URL= (Render will provide this if you create a database)
```

**Important:** 
- `X_REDIRECT_URI` will be `https://your-service-name.onrender.com/v1/oauth/x/callback`
- You'll get the exact URL after deploying

## Step 5: Create Database (Optional)

If you need a database:
1. Click "New +" → "PostgreSQL"
2. Name it: `ibtikar-db`
3. Copy the connection string
4. Add it to your environment variables as `DATABASE_URL`

## Step 6: Deploy

1. Click "Create Web Service"
2. Wait for deployment (5-10 minutes)
3. Copy your service URL (e.g., `https://ibtikar-backend.onrender.com`)

## Step 7: Update Twitter Developer Portal

1. Go to: https://developer.twitter.com/en/portal/dashboard
2. Edit your app → User authentication settings
3. Update **Callback URI** to: `https://your-render-url.onrender.com/v1/oauth/x/callback`
4. Update **Website URL** to: `https://your-render-url.onrender.com`
5. Click **Save**

## Step 8: Update Expo App

1. Update your Expo `.env` file:
```
EXPO_PUBLIC_BACKEND_URL=https://your-render-url.onrender.com
```

2. Restart Expo: `npx expo start --clear`

## Step 9: Test

Try the OAuth login - it should work without the ngrok warning!

## Notes

- **Free tier:** Services sleep after 15 minutes of inactivity (first request will be slow)
- **Upgrade:** Paid plans ($7/month) keep services always running
- **Database:** Free PostgreSQL database available (90 days, then $7/month)

## Troubleshooting

**Service won't start:**
- Check build logs in Render dashboard
- Make sure `requirements.txt` has all dependencies
- Verify start command is correct

**OAuth still not working:**
- Make sure `X_REDIRECT_URI` in Render matches Twitter callback URL exactly
- Check Render logs for errors
- Verify all environment variables are set

