# Quick Start Guide - Deploy Everything Today

## 🎯 Goal
Deploy your backend to Render (free) and model to Hugging Face (free) with Twitter OAuth working.

## ⚡ Fast Track (30 minutes)

### Step 1: Upload Model to Hugging Face (10 min)

1. **Create Hugging Face account:**
   - Go to https://huggingface.co/join
   - Sign up (free)

2. **Get your token:**
   - Go to https://huggingface.co/settings/tokens
   - Create a new token (read + write permissions)
   - Copy it

3. **Upload model:**
   ```bash
   cd IbtikarAI
   # Set your token
   export HF_TOKEN=your_token_here  # or set in Windows: set HF_TOKEN=your_token_here
   
   # Run upload script
   python upload_to_hf.py
   ```
   When prompted, enter: `your-username/arabert-toxic-classifier`
   (Replace `your-username` with your HF username)

4. **Note your model URL:**
   ```
   https://api-inference.huggingface.co/models/your-username/arabert-toxic-classifier
   ```

### Step 2: Update Render Environment Variables (5 min)

1. Go to Render Dashboard → Your Service → Environment tab

2. **Update these variables:**
   - **IBTIKAR_URL** = `https://api-inference.huggingface.co/models/your-username/arabert-toxic-classifier`
   - **X_REDIRECT_URI** = `https://ibtikar-backend.onrender.com/v1/oauth/x/callback`
     (Replace `ibtikar-backend` with your actual Render service name)

3. **Verify these are set correctly:**
   - **FERNET_KEY** = `RIWdmx00ubIno6pbQUBWzam0Ukamrg6ZQdK71IYiqzY=` (exactly 44 chars)
   - **X_CLIENT_ID** = Your Twitter Client ID
   - **ENV** = `production`

4. **Save changes** (this will trigger a redeploy)

### Step 3: Update Twitter OAuth Settings (5 min)

1. Go to https://developer.twitter.com/en/portal/dashboard
2. Select your app
3. Go to **Settings** → **User authentication settings**
4. Click **Edit**
5. Set **Callback URI / Redirect URL** to:
   ```
   https://ibtikar-backend.onrender.com/v1/oauth/x/callback
   ```
   (Replace with your actual Render URL)
6. Set **Website URL** to:
   ```
   https://ibtikar-backend.onrender.com
   ```
7. **Save**

### Step 4: Test Everything (10 min)

1. **Wait for Render to redeploy** (check logs)

2. **Test Twitter OAuth:**
   - Open: `https://ibtikar-backend.onrender.com/v1/oauth/x/start?user_id=1`
   - Should redirect to Twitter login
   - After login, should redirect back to your app

3. **Test Model API:**
   - The backend will automatically use Hugging Face API
   - Check Render logs for any errors

## ✅ Success Checklist

- [ ] Model uploaded to Hugging Face
- [ ] IBTIKAR_URL set in Render
- [ ] X_REDIRECT_URI set in Render (matches Render URL)
- [ ] Twitter callback URL updated
- [ ] Render service deployed successfully
- [ ] Twitter OAuth flow works
- [ ] No ngrok needed!

## 🆘 Troubleshooting

**Model not found?**
- Check model is public on Hugging Face
- Verify URL format is correct
- Wait a few minutes after upload (HF needs to process)

**OAuth not working?**
- Verify X_REDIRECT_URI matches Twitter callback URL exactly
- Check Render service is not sleeping (first request may be slow)
- Verify X_CLIENT_ID is correct

**Build fails?**
- Check FERNET_KEY is exactly 44 characters
- Verify all environment variables are set
- Check Render logs for specific errors

## 📚 More Details

See `DEPLOYMENT_CHECKLIST.md` for comprehensive guide.
See `HUGGINGFACE_DEPLOYMENT.md` for Hugging Face details.




