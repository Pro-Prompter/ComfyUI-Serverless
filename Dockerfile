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

# Download models with authentication header
RUN wget --header="Authorization: Bearer ${HF_TOKEN}" \
    -O /root/.config/ComfyUI/models/text_encoders/nsfw_wan_umt5-xxl_fp8_scaled.safetensors \
    "https://huggingface.co/NSFW-API/NSFW-Wan-UMT5-XXL/resolve/main/nsfw_wan_umt5-xxl_fp8_scaled.safetensors" \
 && wget --header="Authorization: Bearer ${HF_TOKEN}" \
    -O /root/.config/ComfyUI/models/diffusion_models/Wan2.2_Remix_NSFW_i2v_14b_low_lighting_v2.0.safetensors \
    "https://huggingface.co/FX-FeiHou/wan2.2-Remix/resolve/main/NSFW/Wan2.2_Remix_NSFW_i2v_14b_low_lighting_v2.0.safetensors" \
 && wget --header="Authorization: Bearer ${HF_TOKEN}" \
    -O /root/.config/ComfyUI/models/diffusion_models/Wan2.2_Remix_NSFW_i2v_14b_high_lighting_v2.0.safetensors \
    "https://huggingface.co/FX-FeiHou/wan2.2-Remix/resolve/main/NSFW/Wan2.2_Remix_NSFW_i2v_14b_high_lighting_v2.0.safetensors" \
 && wget --header="Authorization: Bearer ${HF_TOKEN}" \
    -O /root/.config/ComfyUI/models/loras/Wan2.2-Lightning_I2V-A14B-4steps-lora_LOW_fp16.safetensors \
    "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22-Lightning/old/Wan2.2-Lightning_I2V-A14B-4steps-lora_LOW_fp16.safetensors" \
 && wget --header="Authorization: Bearer ${HF_TOKEN}" \
    -O /root/.config/ComfyUI/models/loras/Wan2.2-Lightning_I2V-A14B-4steps-lora_HIGH_fp16.safetensors \
    "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/LoRAs/Wan22-Lightning/old/Wan2.2-Lightning_I2V-A14B-4steps-lora_HIGH_fp16.safetensors" \
 && wget --header="Authorization: Bearer ${HF_TOKEN}" \
    -O /root/.config/ComfyUI/models/vae/wan_2.1_vae.safetensors \
    "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors" \
 && wget --header="Authorization: Bearer ${HF_TOKEN}" \
    -O /root/.config/ComfyUI/models/frame_interpolation/rife47.pth \
    "https://huggingface.co/wavespeed/misc/resolve/main/rife/rife47.pth"

# Install additional Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy user files
COPY . .