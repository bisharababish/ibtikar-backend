# Complete Deployment Checklist

## ✅ Pre-Deployment Checklist

### 1. Hugging Face Setup
- [ ] Create Hugging Face account at https://huggingface.co
- [ ] Get your access token from https://huggingface.co/settings/tokens
- [ ] Upload model using `python IbtikarAI/upload_to_hf.py`
- [ ] Note your model URL: `https://api-inference.huggingface.co/models/<username>/<model-name>`
- [ ] (Optional) Create Hugging Face Space for custom API endpoint

### 2. Render Backend Setup
- [ ] Ensure all code is committed and pushed to GitHub
- [ ] Verify `requirements-prod.txt` exists and is correct
- [ ] Verify `render.yaml` is configured correctly
- [ ] Check that Root Directory is set to `Desktop/ibtikar-backend-main` (or empty)

### 3. Environment Variables in Render
Go to Render Dashboard → Your Service → Environment tab and set:

- [ ] **ENV** = `production`
- [ ] **FERNET_KEY** = `RIWdmx00ubIno6pbQUBWzam0Ukamrg6ZQdK71IYiqzY=` (exactly 44 chars, no spaces)
- [ ] **IBTIKAR_URL** = `https://api-inference.huggingface.co/models/<your-username>/arabert-toxic-classifier`
- [ ] **X_CLIENT_ID** = Your Twitter/X Client ID
- [ ] **X_REDIRECT_URI** = `https://ibtikar-backend.onrender.com/v1/oauth/x/callback` (replace with your actual Render URL)
- [ ] **DATABASE_URL** = (Auto-set if you linked a PostgreSQL database, or set manually)

### 4. Twitter/X OAuth Configuration
- [ ] Go to https://developer.twitter.com/en/portal/dashboard
- [ ] Select your app
- [ ] Go to Settings → User authentication settings
- [ ] Set **Callback URI / Redirect URL** to: `https://ibtikar-backend.onrender.com/v1/oauth/x/callback`
- [ ] Set **Website URL** to: `https://ibtikar-backend.onrender.com`
- [ ] Save changes

### 5. Render Service Configuration
- [ ] **Build Command:** `pip install -r Desktop/ibtikar-backend-main/requirements-prod.txt`
- [ ] **Start Command:** `sh -c "cd Desktop/ibtikar-backend-main && export PYTHONPATH=. && uvicorn backend.api.main:app --host 0.0.0.0 --port $PORT"`
- [ ] **Root Directory:** `Desktop/ibtikar-backend-main` (or leave empty if using full paths)

## 🚀 Deployment Steps

1. **Upload Model to Hugging Face:**
   ```bash
   cd IbtikarAI
   python upload_to_hf.py
   ```

2. **Verify Render Deployment:**
   - Check build logs for any errors
   - Verify all dependencies install correctly
   - Check that the service starts without errors

3. **Test Twitter OAuth:**
   - Open your Render service URL
   - Navigate to `/v1/oauth/x/start?user_id=1`
   - Should redirect to Twitter login
   - After login, should redirect back to your app

4. **Test Model API:**
   - Verify `IBTIKAR_URL` is set correctly
   - Test an analysis endpoint to ensure it calls Hugging Face

## 🔍 Troubleshooting

### FERNET_KEY Issues
- Must be exactly 44 characters
- No leading/trailing spaces
- No newlines

### Twitter OAuth Issues
- Ensure `X_REDIRECT_URI` in Render matches Twitter callback URL exactly
- Check Twitter Developer Portal settings
- Verify Render service URL is accessible (not sleeping)

### Hugging Face API Issues
- Check model is public (or use token in URL)
- Verify model URL format is correct
- Check Hugging Face API status

### Build/Start Command Issues
- Ensure Root Directory is set correctly
- Check that all paths are correct
- Verify PYTHONPATH is set

## 📝 Notes

- **Free Tier Limits:**
  - Render: Services sleep after 15 min inactivity
  - Hugging Face: Few hundred requests/hour on free tier
  - First request after sleep may be slow (cold start)

- **No ngrok needed:** Render provides a public URL for OAuth callbacks

- **Model hosting:** Hugging Face handles all PyTorch/Transformers dependencies


