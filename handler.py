import runpod
from runpod.serverless.utils import rp_upload
import json
import urllib.request
import urllib.parse
import time
import os
import requests
import base64
from io import BytesIO
import websocket
import uuid
import random
import string
import traceback

# -----------------------------
# Configuration
# -----------------------------

COMFY_API_AVAILABLE_INTERVAL_MS = int(os.environ.get("COMFY_POLLING_INTERVAL_MS", 500))
COMFY_API_AVAILABLE_MAX_RETRIES = int(os.environ.get("COMFY_POLLING_MAX_RETRIES", 2000))
COMFY_HOST = os.environ.get("COMFY_HOST", "127.0.0.1:8188")
WORKFLOW_FILE = "workflow_runpod.json"

# -----------------------------
# Utility Functions
# -----------------------------

def check_server(url, retries=COMFY_API_AVAILABLE_MAX_RETRIES, delay=COMFY_API_AVAILABLE_INTERVAL_MS):
    """Poll ComfyUI server until available."""
    for _ in range(retries):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(delay / 1000)
    return False

def upload_base64_image(base64_string, filename):
    """Upload base64 image to ComfyUI."""
    try:
        if not base64_string:
            return False

        base64_string = base64_string.strip()
        if "," in base64_string:
            base64_string = base64_string.split(",", 1)[1]

        image_data = base64.b64decode(base64_string)
        files = {"image": (filename, BytesIO(image_data), "image/png")}
        data = {"overwrite": "true"}

        response = requests.post(f"http://{COMFY_HOST}/upload/image", files=files, data=data, timeout=30)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error uploading {filename}: {e}")
        return False

def get_history(prompt_id):
    """Fetch workflow execution history."""
    response = requests.get(f"http://{COMFY_HOST}/history/{prompt_id}", timeout=30)
    response.raise_for_status()
    return response.json()

def get_image_data(filename, subfolder, image_type):
    """Fetch image/gif/video bytes from ComfyUI."""
    data = {"filename": filename, "subfolder": subfolder, "type": image_type}
    url_values = urllib.parse.urlencode(data)
    try:
        response = requests.get(f"http://{COMFY_HOST}/view?{url_values}", timeout=60)
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"Error fetching image data: {e}")
        return None

def queue_workflow(workflow, client_id):
    """Submit workflow to ComfyUI."""
    payload = {"prompt": workflow, "client_id": client_id}
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    response = requests.post(f"http://{COMFY_HOST}/prompt", data=data, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()

def generate_random_filename(extension=".png"):
    """Generate random filename for uploaded images."""
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=10)) + extension

# -----------------------------
# Handler Function
# -----------------------------

def handler(job):
    # 1. Robust Health Check (Prevents deployment failures due to empty test jobs)
    if not job or "input" not in job or not job.get("input"):
        if check_server(f"http://{COMFY_HOST}/", COMFY_API_AVAILABLE_MAX_RETRIES, COMFY_API_AVAILABLE_INTERVAL_MS):
            return {"status": "success", "message": "ComfyUI server is ready (test/health-check request)"}
        else:
            return {"error": "ComfyUI server failed to start within the timeout period."}

    job_input = job.get("input")

    # 2. Parse and Validate Inputs
    normalized_input = {k.strip(): v for k, v in job_input.items()}

    # Required: Start and end images (base64 encoded)
    start_image_b64 = normalized_input.get("start_image_base64")
    end_image_b64 = normalized_input.get("end_image_base64")

    # Optional: Prompts for AI-guided video generation
    positive_prompt = normalized_input.get("positive_prompt", "")
    negative_prompt = normalized_input.get("negative_prompt",
        "low quality, lowres, bad hands, extra limbs, missing fingers, poorly drawn face, bad anatomy, blurred, jpeg artifacts, deformed, ugly, bad proportions, disfigured, watermark, text, logo, signature")

    # Optional: Steps (default 8, range 4-20)
    try:
        steps = int(normalized_input.get("steps", 8))
    except (ValueError, TypeError):
        steps = 8
    steps = max(4, min(20, steps))

    # Optional: Resolution (default 640)
    try:
        resolution = int(normalized_input.get("resolution", 640))
    except (ValueError, TypeError):
        resolution = 640
    resolution = max(480, min(1080, resolution))

    # Optional: Frame length (default 65, range 17-129)
    try:
        frame_length = int(normalized_input.get("frame_length", 65))
    except (ValueError, TypeError):
        frame_length = 65
    frame_length = max(17, min(129, frame_length))

    # Optional: Random seed (0 = random)
    try:
        seed = int(normalized_input.get("seed", 0))
    except (ValueError, TypeError):
        seed = 0
    if seed == 0:
        seed = random.randint(0, 2**32 - 1)

    # Validate required inputs
    if not start_image_b64 or not end_image_b64:
        return {"error": "start_image_base64 and end_image_base64 are required."}

    # 3. Check Server
    if not check_server(f"http://{COMFY_HOST}/", COMFY_API_AVAILABLE_MAX_RETRIES, COMFY_API_AVAILABLE_INTERVAL_MS):
        return {"error": "ComfyUI server unreachable."}

    # 4. Upload Images
    start_filename = generate_random_filename()
    end_filename = generate_random_filename()

    if not upload_base64_image(start_image_b64, start_filename):
        return {"error": "Failed to upload start image"}
    if not upload_base64_image(end_image_b64, end_filename):
        return {"error": "Failed to upload end image"}

    # 5. Load Workflow
    try:
        with open(WORKFLOW_FILE, 'r') as f:
            workflow_data = json.load(f)
        # Extract workflow from input.workflow structure (matches wan_api_postman.json format)
        workflow = workflow_data.get("input", {}).get("workflow", workflow_data)
    except Exception as e:
        return {"error": f"Failed to load workflow file: {e}"}

    # 6. Modify Workflow Nodes

    # Node 148: Start Image
    if "148" in workflow:
        workflow["148"]["inputs"]["image"] = start_filename
    else:
        return {"error": "Node 148 (Start Image) not found in workflow"}

    # Node 149: End Image
    if "149" in workflow:
        workflow["149"]["inputs"]["image"] = end_filename
    else:
        return {"error": "Node 149 (End Image) not found in workflow"}

    # Node 134: Positive Prompt
    if "134" in workflow:
        workflow["134"]["inputs"]["text"] = positive_prompt
    else:
        return {"error": "Node 134 (Positive Prompt) not found in workflow"}

    # Node 137: Negative Prompt
    if "137" in workflow:
        workflow["137"]["inputs"]["text"] = negative_prompt
    else:
        return {"error": "Node 137 (Negative Prompt) not found in workflow"}

    # Node 150: Steps
    if "150" in workflow:
        workflow["150"]["inputs"]["value"] = steps
    else:
        return {"error": "Node 150 (Steps) not found in workflow"}

    # Node 151: Split Step (half of total steps)
    split_step = steps // 2
    if "151" in workflow:
        workflow["151"]["inputs"]["value"] = split_step
    else:
        return {"error": "Node 151 (Split Step) not found in workflow"}

    # Node 147: Resolution
    if "147" in workflow:
        workflow["147"]["inputs"]["value"] = resolution
    else:
        return {"error": "Node 147 (Resolution) not found in workflow"}

    # Node 156: WanVideoImageToVideoEncode (dimensions and frame length)
    if "156" in workflow:
        # Calculate width/height based on resolution (using 16:9 aspect ratio)
        # Resolution maps to height, calculate width accordingly
        if resolution <= 480:
            width, height = 854, 480
        elif resolution <= 640:
            width, height = 1138, 640
        elif resolution <= 720:
            width, height = 1280, 720
        else:  # 1080
            width, height = 1920, 1080

        workflow["156"]["inputs"]["width"] = width
        workflow["156"]["inputs"]["height"] = height
        workflow["156"]["inputs"]["length"] = frame_length
        workflow["156"]["inputs"]["num_frames"] = frame_length
    else:
        return {"error": "Node 156 (WanVideoImageToVideoEncode) not found in workflow"}

    # Node 139: WanVideoSampler HIGH (steps, seed, end_step)
    if "139" in workflow:
        workflow["139"]["inputs"]["steps"] = steps
        workflow["139"]["inputs"]["seed"] = seed
        workflow["139"]["inputs"]["end_step"] = split_step
    else:
        return {"error": "Node 139 (WanVideoSampler HIGH) not found in workflow"}

    # Node 140: WanVideoSampler LOW (steps, seed, start_step)
    if "140" in workflow:
        workflow["140"]["inputs"]["steps"] = steps
        workflow["140"]["inputs"]["seed"] = seed
        workflow["140"]["inputs"]["start_step"] = split_step
    else:
        return {"error": "Node 140 (WanVideoSampler LOW) not found in workflow"}

    # 7. Execute Workflow
    client_id = str(uuid.uuid4())
    ws = None
    try:
        ws_url = f"ws://{COMFY_HOST}/ws?clientId={client_id}"
        ws = websocket.WebSocket()
        ws.connect(ws_url, timeout=10)

        queue_resp = queue_workflow(workflow, client_id)
        prompt_id = queue_resp["prompt_id"]

        # Poll for completion
        while True:
            out = ws.recv()
            if isinstance(out, str):
                msg = json.loads(out)
                if msg["type"] == "executing":
                    data = msg["data"]
                    if data["node"] is None and data["prompt_id"] == prompt_id:
                        break  # Done
            else:
                continue

        # 8. Fetch Results - Extract all interpolated frames
        history = get_history(prompt_id)
        prompt_history = history.get(prompt_id, {})
        outputs = prompt_history.get("outputs", {})

        # Extract frames from SaveImage node 117
        frames = []
        node_output = outputs.get("117", {})
        
        if "images" in node_output:
            for item in node_output["images"]:
                fname = item.get("filename", "")
                ftype = item.get("type", "output")
                subfolder = item.get("subfolder", "")
                
                content = get_image_data(fname, subfolder, ftype)
                if content:
                    frames.append(base64.b64encode(content).decode("utf-8"))

        if not frames:
            return {"error": "No interpolated frames generated", "details": str(outputs)}

        return {
            "frames": frames,
            "metadata": {
                "format": "png",
                "frame_count": len(frames),
                "steps": steps,
                "resolution": resolution,
                "frame_length": frame_length,
                "seed": seed,
                "positive_prompt": positive_prompt[:100] + "..." if len(positive_prompt) > 100 else positive_prompt,
                "negative_prompt": negative_prompt[:100] + "..." if len(negative_prompt) > 100 else negative_prompt
            }
        }

    except Exception as e:
        return {"error": f"Execution failed: {e}", "traceback": traceback.format_exc()}
    finally:
        if ws:
            ws.close()

# -----------------------------
# Entrypoint
# -----------------------------

if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
