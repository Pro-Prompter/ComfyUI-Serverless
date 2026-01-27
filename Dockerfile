# clean base image containing only comfyui, comfy-cli and comfyui-manager
FROM runpod/worker-comfyui:5.5.1-base

# install custom nodes into comfyui
RUN comfy node install --exit-on-fail ComfyUI-WanVideoWrapper@1.4.5 --mode remote
RUN comfy node install --exit-on-fail comfyui-wanvideowrapper@1.4.5
RUN comfy node install --exit-on-fail comfyui-kjnodes@1.2.8
RUN comfy node install --exit-on-fail comfyui-frame-interpolation@1.0.7
RUN comfy node install --exit-on-fail comfyui-custom-scripts@1.2.5
RUN comfy node install --exit-on-fail comfyui-easy-use@1.3.6

# download models into comfyui
RUN comfy model download --url https://huggingface.co/NSFW-API/NSFW-Wan-UMT5-XXL/resolve/main/nsfw_wan_umt5-xxl_fp8_scaled.safetensors --relative-path models/text_encoders --filename nsfw_wan_umt5-xxl_fp8_scaled.safetensors

# Wan2.2 Remix I2V NSFW models
RUN comfy model download --url https://huggingface.co/FX-FeiHou/wan2.2-Remix/resolve/main/NSFW/Wan2.2_Remix_NSFW_i2v_14b_low_lighting_v2.0.safetensors --relative-path models/diffusion_models --filename Wan2.2_Remix_NSFW_i2v_14b_low_lighting_v2.0.safetensors
RUN comfy model download --url https://huggingface.co/FX-FeiHou/wan2.2-Remix/resolve/main/NSFW/Wan2.2_Remix_NSFW_i2v_14b_high_lighting_v2.0.safetensors --relative-path models/diffusion_models --filename Wan2.2_Remix_NSFW_i2v_14b_high_lighting_v2.0.safetensors

# LoRAs (Required by workflow)
RUN comfy model download --url https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan22-Lightning/Wan2.2-Lightning_I2V-A14B-4steps-lora_LOW_fp16.safetensors --relative-path models/loras --filename Wan2.2-Lightning_I2V-A14B-4steps-lora_LOW_fp16.safetensors
RUN comfy model download --url https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Wan22-Lightning/Wan2.2-Lightning_I2V-A14B-4steps-lora_HIGH_fp16.safetensors --relative-path models/loras --filename Wan2.2-Lightning_I2V-A14B-4steps-lora_HIGH_fp16.safetensors

# VAE
RUN comfy model download --url https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors --relative-path models/vae --filename wan_2.1_vae.safetensors

# RIFE interpolation model
RUN comfy model download --url https://huggingface.co/wavespeed/misc/resolve/main/rife/rife47.pth --relative-path models/frame_interpolation --filename rife47.pth

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Uncomment if you want to preload input data
# COPY input/ /comfyui/input/