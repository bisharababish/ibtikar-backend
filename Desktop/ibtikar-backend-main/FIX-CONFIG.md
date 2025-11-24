# Fix: Vocabulary Size Mismatch

## Problem
The model file has embeddings for **64,000 tokens**, but `config.json` says `vocab_size: 32000`.

Error: `size mismatch for weight: copying a param with shape torch.Size([64000, 768]) from checkpoint, the shape in current model is torch.Size([32000, 768])`

## Solution
Update `config.json` on Hugging Face to have `vocab_size: 64000` instead of `32000`.

## Updated config.json

Go to: https://huggingface.co/Bisharababish/arabert-toxic-classifier/blob/main/config.json

Replace the current config.json with this:

```json
{
  "_name_or_path": "aubmindlab/bert-base-arabertv02",
  "architectures": [
    "BertForSequenceClassification"
  ],
  "attention_probs_dropout_prob": 0.1,
  "classifier_dropout": null,
  "hidden_act": "gelu",
  "hidden_dropout_prob": 0.1,
  "hidden_size": 768,
  "id2label": {
    "0": "LABEL_0",
    "1": "LABEL_1"
  },
  "initializer_range": 0.02,
  "intermediate_size": 3072,
  "label2id": {
    "LABEL_0": 0,
    "LABEL_1": 1
  },
  "layer_norm_eps": 1e-12,
  "max_position_embeddings": 512,
  "model_type": "bert",
  "num_attention_heads": 12,
  "num_hidden_layers": 12,
  "num_labels": 2,
  "pad_token_id": 0,
  "position_embedding_type": "absolute",
  "torch_dtype": "float32",
  "transformers_version": "4.30.0",
  "type_vocab_size": 2,
  "use_cache": true,
  "vocab_size": 64000
}
```

**Key change:** `"vocab_size": 64000` (was 32000)

## Steps to Fix

1. Go to: https://huggingface.co/Bisharababish/arabert-toxic-classifier
2. Click on `config.json`
3. Click "Edit" button
4. Change `"vocab_size": 32000` to `"vocab_size": 64000`
5. Save/Commit the change
6. Wait for Space to rebuild (it will auto-detect the change)

After this, the model should load correctly!

