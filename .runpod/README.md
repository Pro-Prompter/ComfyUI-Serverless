# Wan2.1 Remix Image-to-Video - Serverless Worker

This repository contains the configuration to deploy the **Wan2.1 Remix Image-to-Video (I2V)** workflow as a Serverless Endpoint on **RunPod**, including all necessary custom nodes (WanVideoWrapper) and models.

## Deployment Method: GitHub + Dockerfile

We rely on RunPod's **Dockerfile** build system. The repository includes a `Dockerfile` that:
1.  Extends the base ComfyUI image.
2.  Installs the required Custom Nodes (`ComfyUI-WanVideoWrapper`, `comfyui-kjnodes`, etc.).
3.  **Downloads all necessary models** (Wan2.2 Checkpoints, LoRAs, VAE, UMT5) directly into the image.

### Steps to Deploy

1.  **Push this repository to GitHub** (Private or Public).
2.  Go to the [RunPod Console](https://www.runpod.io/console/serverless).
3.  Click **New Endpoint**.
4.  **Connect your GitHub Repository**.
5.  **Build Method**: Select **Dockerfile**.
6.  **GPU Configuration**: Select **H100 80GB** (Recommended for Wan2.1 14B).
7.  **Environment Variables** (Optional, for tuning):
    - `COMFY_POLLING_MAX_RETRIES`: `2000` (Increase wait time for cold starts)
    - `COMFY_POLLING_INTERVAL_MS`: `500`
8.  **Deploy**.
    > **Note**: The first build/start will take significant time (10-15 minutes) as it downloads ~20GB of models into the container image.

---

## API Usage

The worker uses a custom `handler.py` that simplifies the input. You do **not** need to send the full workflow JSON every time.

### Endpoint Input

**POST** to your RunPod Serverless URL (e.g., `https://api.runpod.ai/v2/<endpoint_id>/run`)

**Headers**:
- `Authorization`: `Bearer <YOUR_RUNPOD_KEY>`

**Body**:
```json
{
  "input": {
    "start_image_base64": "<BASE64_STRING_OF_START_IMAGE>",
    "end_image_base64": "<BASE64_STRING_OF_END_IMAGE>",
    "steps": 25,
    "resolution": 720
  }
}
```

### Parameters

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `start_image_base64` | String | **Required** | Base64 encoded string of the starting image (PNG/JPG). |
| `end_image_base64` | String | **Required** | Base64 encoded string of the ending image (PNG/JPG). |
| `steps` | Integer | `25` | Number of sampling steps. |
| `resolution` | Integer | `720` | Vertical resolution of the output video. |

### Response

The response follows the standard RunPod Serverless format.

```json
{
  "id": "<JOB_ID>",
  "status": "COMPLETED",
  "output": "<BASE64_VIDEO_STRING>"
}
```

If the status is `IN_PROGRESS`, you must poll the status endpoint (`/status/<JOB_ID>`) until it completes.

---

## Local Development / Files

- **`Dockerfile`**: Defines the build environment and model downloads.
- **`handler.py`**: The Python script that processes requests, updates the workflow, and interacts with ComfyUI.
- **`workflow_runpod.json`**: The base API-format workflow used as a template.
- **`runpod.yaml`**: Configuration file linking the handler.
