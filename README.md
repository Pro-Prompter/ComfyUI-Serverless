# Heritage - RunPod Serverless Video Frame Interpolation API

AI-powered video frame interpolation using Wan2.2 I2V Remix + RIFE VFI on RunPod Serverless.

## 🎯 What This Does

Takes **two images** (start + end) and generates **interpolated frames** between them using:
- **Wan2.2 I2V Remix**: AI-guided image-to-video generation with text prompts
- **RIFE VFI**: Optical flow interpolation for smooth motion

**Output**: Array of base64-encoded PNG frames (your web app converts them to video)

---

## 📋 Requirements

- RunPod account with H100/H200 GPU access
- GitHub repository (this repo)
- Postman or any HTTP client

---

## 🚀 Deployment

### 1. Push to GitHub

```bash
git add .
git commit -m "Deploy Wan2.2 I2V Remix workflow"
git push origin main
```

### 2. Deploy on RunPod

1. Go to [RunPod Serverless](https://www.runpod.io/console/serverless)
2. Click **"New Endpoint"**
3. Select **"GitHub"** as source
4. Enter your repository URL
5. Set **GPU**: `H100_80GB` or `H200`
6. Set **Container Disk**: `50 GB`
7. Click **"Deploy"**

### 3. Get Your Endpoint

After deployment completes:
- Copy your **Endpoint ID** (e.g., `49k48743eh9bie`)
- Copy your **API Key** from RunPod dashboard

---

## 📡 API Usage

### Endpoint URL

```
https://api.runpod.ai/v2/49k48743eh9bie/runsync
```

Replace `49k48743eh9bie` with your actual endpoint ID.

### Request Format

**POST** to `/runsync` (synchronous) or `/run` (async)

```json
{
  "input": {
    "start_image_base64": "iVBORw0KGgoAAAANS...",
    "end_image_base64": "iVBORw0KGgoAAAANS...",
    "positive_prompt": "smooth motion, high quality, cinematic",
    "negative_prompt": "static, blurry, low quality",
    "steps": 8,
    "resolution": 640,
    "frame_length": 65,
    "seed": 0
  }
}
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `start_image_base64` | string | ✅ Yes | - | Base64-encoded start image |
| `end_image_base64` | string | ✅ Yes | - | Base64-encoded end image |
| `positive_prompt` | string | No | "" | Guide what to generate |
| `negative_prompt` | string | No | (default) | What to avoid |
| `steps` | int | No | 8 | Sampling steps (4-20) |
| `resolution` | int | No | 640 | Output resolution (480/640/720/1080) |
| `frame_length` | int | No | 65 | Video frames (17-129) |
| `seed` | int | No | 0 | Random seed (0 = random) |

### Response Format

```json
{
  "id": "job-abc123",
  "status": "COMPLETED",
  "output": {
    "frames": [
      "iVBORw0KGgoAAAANS...",  // Frame 1 (base64 PNG)
      "iVBORw0KGgoAAAANS...",  // Frame 2
      "..."                      // ~130 frames total
    ],
    "metadata": {
      "format": "png",
      "frame_count": 130,
      "steps": 8,
      "resolution": 640,
      "frame_length": 65
    }
  }
}
```

---

## 🧪 Testing with Postman

### 1. Import Collection

Import `postman_collection.json` into Postman.

### 2. Set Environment Variables

Create a new environment with:

| Variable | Value |
|----------|-------|
| `RUNPOD_API_KEY` | Your RunPod API key |
| `ENDPOINT_ID` | `49k48743eh9bie` |
| `START_IMAGE_B64` | Base64 of your start image |
| `END_IMAGE_B64` | Base64 of your end image |

### 3. Run Requests

- **Health Check**: Verify the endpoint is running
- **Generate Frames (Sync)**: Get interpolated frames immediately
- **Generate Frames (Async)**: Queue job and check status later

---

## 🛠️ Technical Details

### Workflow Architecture

```
Start Image (148) ──┐
                    ├──> WanVideoImageToVideoEncode (156) ──> WanVideoSampler HIGH (139)
End Image (149) ────┘                                                    │
                                                                          ├──> WanVideoSampler LOW (140)
Positive Prompt (134) ──> CLIPTextEncode ──────────────────────────────┘
Negative Prompt (137) ──> CLIPTextEncode                                │
                                                                          ├──> VAEDecode (158)
                                                                          │
                                                                          ├──> RIFE VFI (115) [2x interpolation]
                                                                          │
                                                                          └──> SaveImage (117) [PNG frames]
```

### Models Used

- **Diffusion**: `Wan2.2_Remix_NSFW_i2v_14b_high/low_lighting_v2.0.safetensors`
- **LoRA**: `Wan2.2-Lightning_I2V-A14B-4steps-lora_HIGH/LOW_fp16.safetensors`
- **Text Encoder**: `nsfw_wan_umt5-xxl_fp8_scaled.safetensors`
- **VAE**: `wan_vae_v1.safetensors`
- **Interpolation**: `rife47.pth`

### Performance

- **Cold Start**: ~2-3 minutes (model loading)
- **Warm Inference**: ~30-60 seconds (H100)
- **Output Size**: ~130 frames × ~500KB = ~65MB base64 data

---

## 🐛 Troubleshooting

### "ComfyUI server unreachable"
- Wait 2-3 minutes for cold start
- Check RunPod dashboard for deployment errors

### "No interpolated frames generated"
- Verify both images are valid base64 PNG/JPEG
- Check `frame_length` is between 17-129
- Review RunPod logs for workflow errors

### "Out of memory"
- Reduce `resolution` to 480 or 640
- Reduce `frame_length` to 33 or 49

---

## 📝 Example cURL Request

```bash
curl -X POST https://api.runpod.ai/v2/49k48743eh9bie/runsync \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "start_image_base64": "iVBORw0KGgo...",
      "end_image_base64": "iVBORw0KGgo...",
      "positive_prompt": "smooth cinematic motion",
      "steps": 8,
      "resolution": 640,
      "frame_length": 65
    }
  }'
```

---

## 📄 License

MIT License - See LICENSE file for details.

---

## 🤝 Support

For issues or questions:
1. Check RunPod logs in the dashboard
2. Review `handler.py` error messages in response
3. Contact support with job ID and error details
