# Wan2.2 Image-to-Video Serverless Worker

Deploy **Wan2.2 Remix Image-to-Video** as a serverless endpoint on RunPod.

## Quick Start

1. Push this repo to GitHub
2. Connect GitHub to RunPod (Settings → Connections → GitHub)
3. Create New Serverless Endpoint
4. Select your repository
5. Configure GPU: **48GB minimum, 80GB recommended**
6. Deploy

## Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Builds the container with ComfyUI, custom nodes, and models |
| `handler.py` | Serverless handler that processes API requests |
| `workflow_runpod.json` | The ComfyUI workflow in API format |
| `requirements.txt` | Python dependencies |

## API Usage

### Endpoint URL
```
POST https://api.runpod.ai/v2/{ENDPOINT_ID}/run
```

### Headers
```
Authorization: Bearer YOUR_RUNPOD_API_KEY
Content-Type: application/json
```

### Request Body
```json
{
  "input": {
    "start_image_base64": "BASE64_ENCODED_PNG_OR_JPG",
    "end_image_base64": "BASE64_ENCODED_PNG_OR_JPG",
    "steps": 25,
    "resolution": 720
  }
}
```

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `start_image_base64` | string | ✅ Yes | - | Base64 encoded starting frame |
| `end_image_base64` | string | ✅ Yes | - | Base64 encoded ending frame |
| `steps` | integer | No | 25 | Sampling steps (higher = better quality, slower) |
| `resolution` | integer | No | 720 | Vertical resolution (480, 720, 1080) |

### Response
```json
{
  "id": "job-abc123",
  "status": "COMPLETED",
  "output": "BASE64_ENCODED_VIDEO"
}
```

## Environment Variables

Set these in RunPod when deploying:

| Variable | Value | Purpose |
|----------|-------|---------|
| `COMFY_POLLING_MAX_RETRIES` | `2000` | Cold start timeout |
| `COMFY_POLLING_INTERVAL_MS` | `500` | Polling frequency |

## GPU Requirements

The Wan2.2 14B model requires significant VRAM:

| GPU VRAM | Status |
|----------|--------|
| 24 GB | ❌ Will fail |
| 32 GB | ❌ Will fail |
| 48 GB | ⚠️ Minimum |
| **80 GB** | ✅ **Recommended** |

## Models Included

The Dockerfile downloads these models automatically:

- `nsfw_wan_umt5-xxl_fp8_scaled.safetensors` (Text Encoder)
- `Wan2.2_Remix_NSFW_i2v_14b_high_lighting_v2.0.safetensors` (Diffusion Model)
- `Wan2.2_Remix_NSFW_i2v_14b_low_lighting_v2.0.safetensors` (Diffusion Model)
- `Wan2.2-Lightning_I2V-A14B-4steps-lora_HIGH_fp16.safetensors` (LoRA)
- `Wan2.2-Lightning_I2V-A14B-4steps-lora_LOW_fp16.safetensors` (LoRA)
- `wan_2.1_vae.safetensors` (VAE)
- `rife47.pth` (Frame Interpolation)

## Troubleshooting

### "ComfyUI server unreachable"
Increase `COMFY_POLLING_MAX_RETRIES` to `5000`

### "No output generated"
Check the endpoint logs for workflow errors

### Build fails
Verify HuggingFace URLs use `resolve/main/` not `blob/main/`
