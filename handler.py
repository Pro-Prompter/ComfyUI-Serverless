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
    
    start_image_b64 = normalized_input.get("start_image_base64")
    end_image_b64 = normalized_input.get("end_image_base64")
    
    # Duration / Multiplier logic
    try:
        duration = int(normalized_input.get("duration_seconds", 8))
    except ValueError:
        duration = 8
        
    # Clamp duration to 4-15 defaults
    multiplier = max(4, min(15, duration))
    
    model_name = normalized_input.get("model", "rife47.pth")

    if not start_image_b64 or not end_image_b64:
        return {"error": "start_image_base64 and end_image_base64 are required."}

    # 3. Check Server (Redundant but safe)
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
            workflow = json.load(f)
    except Exception as e:
        return {"error": f"Failed to load workflow file: {e}"}

    # 6. Modify Workflow
    # Node 3: Start Image
    if "3" in workflow:
        workflow["3"]["inputs"]["image"] = start_filename
    else:
        return {"error": "Node 3 (Start Image) not found in workflow"}

    # Node 4: End Image
    if "4" in workflow:
        workflow["4"]["inputs"]["image"] = end_filename
    else:
        return {"error": "Node 4 (End Image) not found in workflow"}
        
    # Node 5: RIFE VFI
    if "5" in workflow:
        workflow["5"]["inputs"]["multiplier"] = multiplier
        workflow["5"]["inputs"]["ckpt_name"] = model_name
        # Ensure connections are correct (frames from 3, frames2 from 4)
        workflow["5"]["inputs"]["frames"] = ["3", 0]
        workflow["5"]["inputs"]["frames2"] = ["4", 0]
    else:
        return {"error": "Node 5 (RIFE VFI) not found in workflow"}

    # Node 6: VHS Video Combine (output)
    if "6" in workflow:
        workflow["6"]["inputs"]["frame_rate"] = 30
        workflow["6"]["inputs"]["format"] = "image/webp"
    else:
        return {"error": "Node 6 (VHS Video Combine) not found in workflow"}

    # 7. Execute Workflow
    client_id = str(uuid.uuid4())
    ws = None
    try:
        ws_url = f"ws://{COMFY_HOST}/ws?clientId={client_id}"
        ws = websocket.WebSocket()
        ws.connect(ws_url, timeout=10)

        queue_resp = queue_workflow(workflow, client_id)
        prompt_id = queue_resp["prompt_id"]

        # Poll
        while True:
            out = ws.recv()
            if isinstance(out, str):
                msg = json.loads(out)
                if msg["type"] == "executing":
                    data = msg["data"]
                    if data["node"] is None and data["prompt_id"] == prompt_id:
                        break # Done
            else:
                continue

        # 8. Fetch Results
        history = get_history(prompt_id)
        prompt_history = history.get(prompt_id, {})
        outputs = prompt_history.get("outputs", {})

        # Extract WebP from Node 6
        output_data = None
        
        # VHS Combine outputs to 'gifs' usually, but safe to check all
        node_output = outputs.get("6", {})
        
        for key in ["gifs", "images", "video"]:
             if key in node_output:
                 for item in node_output[key]:
                     fname = item["filename"]
                     ftype = item["type"]
                     subfolder = item["subfolder"]
                     
                     content = get_image_data(fname, subfolder, ftype)
                     if content:
                         output_data = base64.b64encode(content).decode("utf-8")
                         break
             if output_data: 
                 break

        if not output_data:
             return {"error": "No output video generated", "details": str(outputs)}

        return {
            "output": output_data,
            "metadata": {
                "format": "webp",
                "duration_seconds": float(multiplier), # Approx
                "frame_rate": 30,
                "interpolation_model": model_name
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
