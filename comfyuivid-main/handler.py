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
import tempfile
import random
import string
import traceback

# Time to wait between API check attempts in milliseconds
COMFY_API_AVAILABLE_INTERVAL_MS = int(os.environ.get("COMFY_POLLING_INTERVAL_MS", 50))
# Maximum number of API check attempts
COMFY_API_AVAILABLE_MAX_RETRIES = int(os.environ.get("COMFY_POLLING_MAX_RETRIES", 500))

# Host where ComfyUI is running
COMFY_HOST = os.environ.get("COMFY_HOST", "127.0.0.1:8188")

# Workflow File (RunPod Provided API Format)
WORKFLOW_FILE = "workflow_runpod.json"

def check_server(url, retries=500, delay=50):
    for i in range(retries):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(delay / 1000)
    return False

def upload_base64_image(base64_string, filename):
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
    response = requests.get(f"http://{COMFY_HOST}/history/{prompt_id}", timeout=30)
    response.raise_for_status()
    return response.json()

def get_image_data(filename, subfolder, image_type):
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
    payload = {"prompt": workflow, "client_id": client_id}
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    response = requests.post(f"http://{COMFY_HOST}/prompt", data=data, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()

def generate_random_filename(extension=".png"):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=10)) + extension

def handler(job):
    job_input = job.get("input")
    if not job_input:
        return {"error": "No input provided"}

    # 1. Parse Inputs (sanitize keys)
    normalized_input = {k.strip(): v for k, v in job_input.items()}
    
    start_image_b64 = normalized_input.get("start_image_base64")
    end_image_b64 = normalized_input.get("end_image_base64")
    steps = normalized_input.get("steps", 25)
    resolution = normalized_input.get("resolution", 720)
    
    if not start_image_b64:
        return {"error": "start_image_base64 is required."}
    if not end_image_b64:
        return {"error": "end_image_base64 is required."}

    # 2. Check Server
    if not check_server(f"http://{COMFY_HOST}/", COMFY_API_AVAILABLE_MAX_RETRIES, COMFY_API_AVAILABLE_INTERVAL_MS):
        return {"error": "ComfyUI server unreachable."}

    # 3. Upload Images
    start_filename = generate_random_filename()
    end_filename = generate_random_filename()
    
    if not upload_base64_image(start_image_b64, start_filename):
        return {"error": "Failed to upload start image"}
    if not upload_base64_image(end_image_b64, end_filename):
        return {"error": "Failed to upload end image"}

    # 4. Load Workflow
    try:
        with open(WORKFLOW_FILE, 'r') as f:
            json_data = json.load(f)
            # RunPod provided structure is {"input": {"workflow": {...}}}
            if "input" in json_data and "workflow" in json_data["input"]:
                workflow = json_data["input"]["workflow"]
            else:
                # Fallback if I saved it differently
                workflow = json_data
    except Exception as e:
        return {"error": f"Failed to load workflow file: {e}"}

    # 5. Modify Workflow
    
    # A. Set Resolution (Node 147 - easy int)
    if "147" in workflow:
        workflow["147"]["inputs"]["int"] = resolution 
        # Note: I corrected 'value' back to 'int' in my json file SAVE step, so 'int' is correct here.
        
    # B. Set Steps (Node 150 - INTConstant)
    if "150" in workflow:
        workflow["150"]["inputs"]["value"] = steps

    # C. Configure Start Image (Node 148 - LoadImage)
    if "148" in workflow:
        workflow["148"]["inputs"]["image"] = start_filename
    else:
        return {"error": "Start Image Node (148) not found"}

    # D. Inject End Image Node
    end_node_id = "9001"
    workflow[end_node_id] = {
        "inputs": {
            "image": end_filename,
            "upload": "image"
        },
        "class_type": "LoadImage"
    }

    # E. Connect End Image to Encoder (Node 156)
    if "156" in workflow:
        # Connect end_image input. 
        workflow["156"]["inputs"]["end_image"] = [end_node_id, 0]
    else:
        return {"error": "WanVideoImageToVideoEncode Node (156) not found"}


    # 6. Execute
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

        # Fetch Results
        history = get_history(prompt_id)
        prompt_history = history.get(prompt_id, {})
        outputs = prompt_history.get("outputs", {})
        
        results = []
        for nid, output in outputs.items():
             if "images" in output: 
                 for img in output["images"]:
                     fname = img["filename"]
                     ftype = img["type"]
                     subfolder = img["subfolder"]
                     content = get_image_data(fname, subfolder, ftype)
                     if content:
                         b64_out = base64.b64encode(content).decode("utf-8")
                         results.append(b64_out)
             elif "gifs" in output:
                 for img in output["gifs"]:
                     fname = img["filename"]
                     ftype = img["type"]
                     subfolder = img["subfolder"]
                     content = get_image_data(fname, subfolder, ftype)
                     if content:
                         b64_out = base64.b64encode(content).decode("utf-8")
                         results.append(b64_out)
             elif "video" in output:
                 # Start handling raw video bytes if images/gifs list logic fails or usage varies
                 # output['video'] is likely a list of dicts too?
                 # Assuming output['video'] is similar structure if using SaveVideo
                  for img in output["video"]:
                     fname = img["filename"]
                     ftype = img["type"]
                     subfolder = img["subfolder"]
                     content = get_image_data(fname, subfolder, ftype)
                     if content:
                         b64_out = base64.b64encode(content).decode("utf-8")
                         results.append(b64_out)

        if not results:
             return {"error": "No output generated", "details": str(outputs)}
             
        return {
            "output": results[0]
        }

    except Exception as e:
        return {"error": f"Execution failed: {e}", "traceback": traceback.format_exc()}
    finally:
        if ws:
            ws.close()

if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
