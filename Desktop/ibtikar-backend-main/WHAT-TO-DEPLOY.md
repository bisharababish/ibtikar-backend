# What to Deploy to Render

## Summary

You have 3 separate repositories:

1. **Backend** (`ibtikar-backend-main`) → ✅ **DEPLOY TO RENDER**
2. **IbtikarAI Model API** (`IbtikarAI`) → ✅ **DEPLOY TO RENDER** (separate service)
3. **Frontend/Expo App** (`ibtikarapp`) → ❌ **DO NOT DEPLOY TO RENDER**

## 1. Backend (ibtikar-backend-main) ✅

**Deploy this to Render as a Web Service**

- This is your main API
- Handles OAuth, database, Twitter API calls
- **Repository:** `ibtikar-backend-main`
- **Service Type:** Web Service
- **Port:** 8000 (or Render's $PORT)
- **Already configured:** ✅

## 2. IbtikarAI Model API ✅

**Deploy this to Render as a SEPARATE Web Service**

- This is your ML model API
- Backend calls this via HTTP
- **Repository:** `IbtikarAI` (separate repo)
- **Service Type:** Web Service
- **Port:** 9000 (or Render's $PORT)
- **Needs configuration:** See below

## 3. Frontend/Expo App ❌

**DO NOT deploy to Render**

- Expo apps are mobile apps, not web services
- They run on phones/devices
- Deploy via Expo's services (expo.dev) or build standalone apps
- **Just update the `.env` file** to point to your Render backend URL

---

## Deployment Plan

### Step 1: Deploy Backend

1. Push `ibtikar-backend-main` to GitHub
2. Deploy to Render as Web Service
3. Get backend URL: `https://ibtikar-backend.onrender.com`

### Step 2: Deploy IbtikarAI Model API

1. Push `IbtikarAI` repo to GitHub
2. Deploy to Render as **separate** Web Service
3. Get model API URL: `https://ibtikar-ai.onrender.com`
4. Update backend's `IBTIKAR_URL` environment variable

### Step 3: Connect Them

1. In **Backend** Render service:
   - Add environment variable: `IBTIKAR_URL=https://ibtikar-ai.onrender.com`

2. In **Expo app**:
   - Update `.env`: `EXPO_PUBLIC_BACKEND_URL=https://ibtikar-backend.onrender.com`

---

## IbtikarAI Model API Setup for Render

If your IbtikarAI repo needs setup, you'll need:

**Build Command:**
```bash
pip install -r requirements.txt
```

**Start Command:**
```bash
uvicorn ibtikar_api:app --host 0.0.0.0 --port $PORT
```

**Environment Variables:**
- Any model-specific config (if needed)

---

## Quick Checklist

- [ ] Backend deployed to Render ✅
- [ ] IbtikarAI Model API deployed to Render ✅
- [ ] Backend's `IBTIKAR_URL` points to Model API ✅
- [ ] Expo `.env` points to Backend URL ✅
- [ ] Twitter callback URL updated ✅
- [ ] Test OAuth login ✅

---

## Architecture

```
Phone (Expo App)
    ↓
Backend (Render) ←→ IbtikarAI Model API (Render)
    ↓
Twitter API
```

Both services run on Render, but as **separate web services**.

