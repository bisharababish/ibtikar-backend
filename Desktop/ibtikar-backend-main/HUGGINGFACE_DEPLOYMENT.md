# Hugging Face Deployment Guide

## Overview
This guide will help you deploy the AraBERT toxic classifier model to Hugging Face and update the backend to use it.

## Step 1: Upload Model to Hugging Face Hub

### Option A: Using Hugging Face CLI (Recommended)

1. **Install Hugging Face CLI:**
   ```bash
   pip install huggingface_hub
   ```

2. **Login to Hugging Face:**
   ```bash
   huggingface-cli login
   ```
   Enter your Hugging Face token (get it from https://huggingface.co/settings/tokens)

3. **Upload the model:**
   ```bash
   cd IbtikarAI
   huggingface-cli upload <your-username>/arabert-toxic-classifier arabert_toxic_classifier/ --repo-type model
   ```

### Option B: Using Python Script

Run the provided script:
```bash
python upload_to_hf.py
```

## Step 2: Create Hugging Face Space (Free CPU)

1. Go to https://huggingface.co/spaces
2. Click "Create new Space"
3. Choose:
   - **Name:** `arabert-toxic-classifier`
   - **SDK:** `Gradio` or `Docker`
   - **Hardware:** `CPU Basic` (Free)
   - **Visibility:** Public or Private

4. Upload the model files and create an API endpoint

## Step 3: Update Backend Configuration

The backend will automatically use Hugging Face Inference API if `IBTIKAR_URL` is not set or points to Hugging Face.

### For Hugging Face Inference API:
Set environment variable in Render:
```
IBTIKAR_URL=https://api-inference.huggingface.co/models/<your-username>/arabert-toxic-classifier
```

### For Hugging Face Space:
Set environment variable in Render:
```
IBTIKAR_URL=https://<your-username>-arabert-toxic-classifier.hf.space
```

## Step 4: Update Twitter OAuth

1. Go to Render dashboard → Environment tab
2. Set `X_REDIRECT_URI` to:
   ```
   https://ibtikar-backend.onrender.com/v1/oauth/x/callback
   ```
   (Replace `ibtikar-backend` with your actual Render service name)

3. Update Twitter Developer Portal:
   - Go to https://developer.twitter.com/en/portal/dashboard
   - Edit your app → User authentication settings
   - Set **Callback URI** to: `https://ibtikar-backend.onrender.com/v1/oauth/x/callback`
   - Set **Website URL** to: `https://ibtikar-backend.onrender.com`

## Benefits

✅ **Free hosting** - Both Render and Hugging Face free tiers
✅ **No ngrok needed** - Direct Render URL for OAuth
✅ **Scalable** - Hugging Face handles model inference
✅ **Lightweight backend** - No PyTorch/Transformers in Render service




