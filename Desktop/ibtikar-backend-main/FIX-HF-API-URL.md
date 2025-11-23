# Fix: Hugging Face API URL Issue

## The Problem

The Router API formats we tried are not working:
- ❌ `https://router.huggingface.co/v1/models/...` → 404 Not Found
- ❌ `https://router.huggingface.co/hf-inference/v1/models/...` → 401 Invalid username/password
- ❌ `https://huggingface.co/api/models/...` → Repository not found

## Solution: Use Hugging Face Space API (Recommended)

The **most reliable solution** is to deploy your model as a **Hugging Face Space** and use the Space API.

### Step 1: Create Hugging Face Space

1. Go to https://huggingface.co/spaces
2. Click "Create new Space"
3. Configure:
   - **Name:** `arabert-toxic-classifier` (or any name)
   - **SDK:** Choose `Gradio` or `Docker`
   - **Hardware:** `CPU Basic` (Free tier)
   - **Visibility:** Public

### Step 2: Deploy Model in Space

Create a `app.py` file in your Space:

```python
import gradio as gr
from transformers import pipeline

# Load your model
classifier = pipeline("text-classification", model="bisharababish/arabert-toxic-classifier")

def classify(text):
    result = classifier(text)
    return result

# Create Gradio interface with API endpoint
iface = gr.Interface(
    fn=classify,
    inputs="text",
    outputs="json",
    api_name="predict"
)

iface.launch()
```

### Step 3: Get Space API URL

Once deployed, your Space will have an API endpoint:
```
https://bisharababish-arabert-toxic-classifier.hf.space/api/predict
```

Or if your username is different:
```
https://{your-username}-arabert-toxic-classifier.hf.space/api/predict
```

### Step 4: Update IBTIKAR_URL in Render

In Render dashboard → Environment Variables:
```
IBTIKAR_URL=https://bisharababish-arabert-toxic-classifier.hf.space/api/predict
```

### Step 5: Update Backend Code (if needed)

The backend already supports `hf.space` URLs, so it should work automatically.

## Alternative: Check Model Availability

If you prefer using the Router API, check:
1. Is the model actually deployed on Hugging Face Hub?
2. Does it have Inference API enabled?
3. Check the model page: https://huggingface.co/bisharababish/arabert-toxic-classifier

If the model page shows "Inference API" section, use that exact endpoint format shown there.

## Current Status

The code now uses the URL **exactly as configured** in `IBTIKAR_URL` - no auto-conversion.
Set the correct working URL format yourself.

