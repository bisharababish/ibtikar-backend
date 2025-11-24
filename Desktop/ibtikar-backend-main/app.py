"""
Hugging Face Space app for AraBERT Toxic Classifier.
This app downloads model files properly to handle Git LFS pointers.
"""

import gradio as gr
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
from huggingface_hub import snapshot_download, hf_hub_download
import os
import torch

# Model name from Hugging Face Hub
model_name = "Bisharababish/arabert-toxic-classifier"

print("=" * 60)
print("Loading Arabic Toxic Text Classifier")
print("=" * 60)
print(f"Model: {model_name}")

# Strategy: Use snapshot_download to get all files (handles LFS)
# Then load from the downloaded directory
try:
    print("📥 Downloading model files from Hugging Face Hub...")
    print("   This will resolve Git LFS pointers automatically...")
    
    # Download all model files using snapshot_download
    # This should automatically resolve LFS pointers
    model_cache_dir = snapshot_download(
        repo_id=model_name,
        revision="main",
        local_files_only=False,  # Force download from Hub
        resume_download=True
    )
    
    print(f"✅ Model files downloaded to: {model_cache_dir}")
    
    # Verify model.safetensors file size
    model_file = os.path.join(model_cache_dir, "model.safetensors")
    if os.path.exists(model_file):
        file_size = os.path.getsize(model_file)
        print(f"📊 Model file size: {file_size} bytes ({file_size / 1024 / 1024:.2f} MB)")
        
        if file_size < 1000000:  # Less than 1MB = still a pointer
            raise Exception(
                f"❌ Model file is still a Git LFS pointer ({file_size} bytes). "
                f"The actual model file (~540MB) needs to be uploaded to Hugging Face. "
                f"Please upload the real model.safetensors file, not just the LFS pointer."
            )
    
    print("🔄 Loading model from downloaded files...")
    
    # Load model using pipeline with the cached directory
    classifier = pipeline(
        "text-classification",
        model=model_cache_dir,  # Use local cache directory
        trust_remote_code=True,
        device_map="auto" if torch.cuda.is_available() else None
    )
    
    print("✅ Model loaded successfully!")
    
    # Get model's label mapping for debugging
    try:
        model = classifier.model
        if hasattr(model, 'config'):
            if hasattr(model.config, 'id2label') and model.config.id2label:
                print(f"📋 Model label mapping: {model.config.id2label}")
            elif hasattr(model.config, 'label2id') and model.config.label2id:
                id2label = {v: k for k, v in model.config.label2id.items()}
                print(f"📋 Model label mapping: {id2label}")
    except Exception as e:
        print(f"⚠️ Could not get label mapping: {e}")
        
except Exception as e:
    error_msg = str(e)
    print(f"❌ Error loading model: {error_msg}")
    
    # Provide helpful error message
    if "LFS" in error_msg or "pointer" in error_msg.lower() or "137" in error_msg:
        print("\n" + "=" * 60)
        print("⚠️  GIT LFS POINTER DETECTED")
        print("=" * 60)
        print("The model file on Hugging Face is a Git LFS pointer, not the actual file.")
        print("You need to upload the REAL model.safetensors file (~540MB) to Hugging Face.")
        print("\nTo fix this:")
        print("1. Go to your model repo: https://huggingface.co/Bisharababish/arabert-toxic-classifier")
        print("2. Delete the current model.safetensors file (137 bytes)")
        print("3. Upload the actual model.safetensors file (~540MB)")
        print("4. Make sure it's uploaded as a regular file, not via Git LFS")
        print("=" * 60)
    
    import traceback
    traceback.print_exc()
    raise

def classify(text):
    """
    Classify text as harmful or safe.
    
    The model returns:
    - LABEL_0 or class 0 = safe/non-toxic
    - LABEL_1 or class 1 = harmful/toxic
    
    We need to correctly identify LABEL_1 as harmful.
    """
    try:
        if not text or not text.strip():
            return [{"label": "safe", "score": 0.5}]
        
        # Get prediction from model
        result = classifier(text)
        
        # Pipeline returns a list of dicts with label and score
        # Format: [{"label": "LABEL_0", "score": 0.95}, {"label": "LABEL_1", "score": 0.05}]
        # Or sometimes just the top result: [{"label": "LABEL_0", "score": 0.95}]
        
        if not isinstance(result, list) or len(result) == 0:
            return [{"label": "unknown", "score": 0.5}]
        
        # Get model's label mapping if available
        model = classifier.model
        id2label = None
        if hasattr(model, 'config'):
            if hasattr(model.config, 'id2label') and model.config.id2label:
                id2label = model.config.id2label
            elif hasattr(model.config, 'label2id') and model.config.label2id:
                id2label = {v: k for k, v in model.config.label2id.items()}
        
        # Find LABEL_1 (harmful) in the results
        harmful_item = None
        safe_item = None
        
        for item in result:
            if not isinstance(item, dict):
                continue
                
            label = str(item.get("label", ""))
            label_upper = label.upper()
            score = float(item.get("score", 0.0))
            
            # Check if this is LABEL_1 (harmful/toxic)
            is_harmful = (
                "LABEL_1" in label_upper or
                label == "1" or
                (id2label and id2label.get(1) == label) or
                "toxic" in label.lower() or
                "harmful" in label.lower()
            )
            
            # Check if this is LABEL_0 (safe/non-toxic)
            is_safe = (
                "LABEL_0" in label_upper or
                label == "0" or
                (id2label and id2label.get(0) == label) or
                "safe" in label.lower() or
                "non-toxic" in label.lower() or
                "non_toxic" in label.lower()
            )
            
            if is_harmful:
                harmful_item = {"label": label, "score": score}
            elif is_safe:
                safe_item = {"label": label, "score": score}
        
        # If we found both, compare scores
        if harmful_item and safe_item:
            harmful_score = harmful_item["score"]
            safe_score = safe_item["score"]
            
            # If harmful score is higher, it's harmful
            if harmful_score > safe_score:
                return [{"label": "harmful", "score": harmful_score}]
            else:
                return [{"label": "safe", "score": safe_score}]
        
        # If we only found harmful
        if harmful_item:
            return [{"label": "harmful", "score": harmful_item["score"]}]
        
        # If we only found safe
        if safe_item:
            return [{"label": "safe", "score": safe_item["score"]}]
        
        # If we couldn't identify, check the top result by score
        # Sort by score descending
        sorted_results = sorted(result, key=lambda x: float(x.get("score", 0)), reverse=True)
        top_result = sorted_results[0] if sorted_results else None
        
        if top_result:
            label = str(top_result.get("label", ""))
            score = float(top_result.get("score", 0.5))
            
            # Last resort: check if label contains "1" (harmful) or "0" (safe)
            if "1" in label or "LABEL_1" in label.upper():
                return [{"label": "harmful", "score": score}]
            else:
                return [{"label": "safe", "score": score}]
        
        # Fallback
        return [{"label": "unknown", "score": 0.5}]
        
    except Exception as e:
        print(f"❌ Classification error: {e}")
        import traceback
        traceback.print_exc()
        return [{"label": "unknown", "score": 0.5}]

# Create Gradio interface with API endpoint
iface = gr.Interface(
    fn=classify,
    inputs=gr.Textbox(
        placeholder="Enter Arabic text to analyze...",
        label="Text",
        lines=3
    ),
    outputs=gr.JSON(label="Prediction"),
    title="Arabic Toxic Text Classifier",
    description="Classify Arabic text as safe or harmful/toxic. Returns 'harmful' for toxic content and 'safe' for normal content.",
    examples=[
        ["مرحبا بك كيف حالك"],
        ["انت غبي وما تفهم شي"],
    ],
    api_name="predict"  # This creates the /api/predict endpoint
)

if __name__ == "__main__":
    iface.launch(server_name="0.0.0.0", server_port=7860)

