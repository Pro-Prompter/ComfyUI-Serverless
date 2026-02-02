FROM runpod/worker-comfyui:5.5.1-base

# Hugging Face token
ENV HF_TOKEN="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"

# Create model folders
RUN mkdir -p /root/.config/ComfyUI/models/{diffusion_models,text_encoders,loras,vae,frame_interpolation}

# Install custom nodes
RUN comfy node install --exit-on-fail ComfyUI-WanVideoWrapper@1.4.7 --mode remote \
 && comfy node install --exit-on-fail comfyui-kjnodes@1.2.8 \
 && comfy node install --exit-on-fail comfyui-frame-interpolation@1.0.7 \
 && comfy node install --exit-on-fail comfyui-custom-scripts@1.2.5 \
 && comfy node install --exit-on-fail comfyui-easy-use@1.3.6

# -------------------------
# Download models via comfy model download
# -------------------------

# NSFW text encoder
RUN comfy model download \
    --url "https://huggingface.co/NSFW-API/NSFW-Wan-UMT5-XXL/resolve/main/nsfw_wan_umt5-xxl_fp8_scaled.safetensors" \
    --relative-path "models/text_encoders" \
    --filename "nsfw_wan_umt5-xxl_fp8_scaled.safetensors"

# Diffusion models
RUN comfy model download \
    --url "https://huggingface.co/FX-FeiHou/wan2.2-Remix/resolve/main/NSFW/Wan2.2_Remix_NSFW_i2v_14b_low_lighting_v2.0.safetensors" \
    --relative-path "models/diffusion_models" \
    --filename "Wan2.2_Remix_NSFW_i2v_14b_low_lighting_v2.0.safetensors"

RUN comfy model download \
    --url "https://huggingface.co/FX-FeiHou/wan2.2-Remix/resolve/main/NSFW/Wan2.2_Remix_NSFW_i2v_14b_high_lighting_v2.0.safetensors" \
    --relative-path "models/diffusion_models" \
    --filename "Wan2.2_Remix_NSFW_i2v_14b_high_lighting_v2.0.safetensors"

# LoRA models
RUN comfy model download \
    --url "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22-Lightning/old/Wan2.2-Lightning_I2V-A14B-4steps-lora_LOW_fp16.safetensors" \
    --relative-path "models/loras" \
    --filename "Wan2.2-Lightning_I2V-A14B-4steps-lora_LOW_fp16.safetensors"

RUN comfy model download \
    --url "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22-Lightning/old/Wan2.2-Lightning_I2V-A14B-4steps-lora_HIGH_fp16.safetensors" \
    --relative-path "models/loras" \
    --filename "Wan2.2-Lightning_I2V-A14B-4steps-lora_HIGH_fp16.safetensors"

# VAE
RUN comfy model download \
    --url "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors" \
    --relative-path "models/vae" \
    --filename "wan_2.1_vae.safetensors"

# Frame interpolation model
RUN comfy model download \
    --url "https://huggingface.co/wavespeed/misc/resolve/main/rife/rife47.pth" \
    --relative-path "models/frame_interpolation" \
    --filename "rife47.pth"

# -------------------------
# Install additional Python dependencies
# -------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# -------------------------
# Copy user files
# -------------------------
COPY . .