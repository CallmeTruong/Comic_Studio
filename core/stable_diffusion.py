import torch
from pathlib import Path
from diffusers import (
    StableDiffusionPipeline,
    ControlNetModel,
    StableDiffusionControlNetPipeline,
    MultiControlNetModel,
)
from diffusers.utils import load_image
from PIL import Image

class SD:
    def __init__(
        self,
        model_path: str,
        device: str = "cuda",
        base: str = "SDv1.5",
        negative_embedding_path: str | None = None,
        controlnet_infos: list[dict] | None = None,
    ):
        self.device = device
        self.base = base
        self.negative_embedding_path = negative_embedding_path
        self.negative_embedding_token = None
        self.controlnet_infos = controlnet_infos or []
        self.controlnet_modes = [info.get("mode") for info in self.controlnet_infos]
        self.controlnet_scales = [info.get("scale", 1.0) for info in self.controlnet_infos]
        
        print(f"[SD] Loading model: {model_path}")
        
        if base == "SDv1.5":
            if self.controlnet_infos:
                control_models = []
                for info in self.controlnet_infos:
                    path = info.get("path")
                    if not path or not Path(path).exists():
                        continue
                    print(f"[SD] Loading ControlNet ({info.get('mode','unknown')}): {path}")
                    control_models.append(
                        ControlNetModel.from_single_file(path, torch_dtype=torch.float16)
                    )
                if control_models:
                    controlnet = (
                        control_models[0]
                        if len(control_models) == 1
                        else MultiControlNetModel(control_models)
                    )
                    self.pipe = StableDiffusionControlNetPipeline.from_single_file(
                        model_path,
                        controlnet=controlnet,
                        torch_dtype=torch.float16,
                    )
                else:
                    self.controlnet_infos = []
                    self.controlnet_modes = []
                    self.controlnet_scales = []
                    self.pipe = StableDiffusionPipeline.from_single_file(
                        model_path,
                        torch_dtype=torch.float16,
                    )
            else:
                self.pipe = StableDiffusionPipeline.from_single_file(
                    model_path,
                    torch_dtype=torch.float16,
                )
        else:
            raise ValueError(f"Unsupported base: {base}")
        
        if device == "cuda" and torch.cuda.is_available():
            self.pipe.to(device)
            # self.pipe.enable_model_cpu_offload() # Uncomment to save VRAM
        else:
            print("[WARN] CUDA not available or not selected. Running on CPU.")
            self.pipe.to("cpu")
        
        # Disable slicing to maximize speed (uses more VRAM)
        # self.pipe.enable_attention_slicing()
        # self.pipe.enable_vae_slicing()
        print(f"[SD] ✓ Model loaded on {device}")
        
        if negative_embedding_path and Path(negative_embedding_path).exists():
            self._load_negative_embedding(negative_embedding_path)
    
    def _load_negative_embedding(self, embedding_path: str):
        try:
            print(f"[SD] Loading negative embedding: {embedding_path}")
            embedding_dict = torch.load(embedding_path, map_location=self.device)
            
            if isinstance(embedding_dict, dict):
                if "name" in embedding_dict:
                    self.negative_embedding_token = embedding_dict["name"]
                elif "string_to_param" in embedding_dict:
                    string_to_param = embedding_dict["string_to_param"]
                    if isinstance(string_to_param, dict) and len(string_to_param) > 0:
                        self.negative_embedding_token = list(string_to_param.keys())[0]
                
                if self.negative_embedding_token:
                    self.pipe.load_textual_inversion(embedding_path, token=self.negative_embedding_token)
                    print(f"[SD] ✓ Negative embedding loaded and applied: token='{self.negative_embedding_token}'")
                else:
                    print(f"[WARN] Cannot find embedding token name")
            else:
                print(f"[WARN] Embedding file format not recognized")
        except Exception as e:
            print(f"[WARN] Failed to load negative embedding: {e}")
            self.negative_embedding_token = None

    def load_lora(self, lora_path: str, scale: float = 1):
        if lora_path:
            print(f"[SD] Loading LoRA: {lora_path} (scale={scale})")
            self.pipe.load_lora_weights(lora_path)
            self.pipe.fuse_lora(lora_scale=scale)
            print(f"[SD] ✓ LoRA loaded")

    def gen_image(
        self,
        context: str,
        base_negative: str = None,
        pipe=None,
        sep: int = 50,
        seed: int = None,
        width: int = None,
        height: int = None,
        guidance_scale: float = None,
        control_images: dict | None = None,
    ) -> Image.Image:
        if pipe is None:
            pipe = self.pipe
        
        generator = None
        if seed is not None:
            generator = torch.Generator(device=self.device).manual_seed(seed)
        
        negative_prompt = base_negative or ""
        if self.negative_embedding_token:
            if negative_prompt:
                negative_prompt = f"{self.negative_embedding_token}, {negative_prompt}"
            else:
                negative_prompt = self.negative_embedding_token
        
        kwargs = {
            "prompt": context,
            "negative_prompt": negative_prompt,
            "num_inference_steps": sep
        }
        
        if generator is not None:
            kwargs["generator"] = generator
        if width is not None and height is not None:
            kwargs["width"] = width
            kwargs["height"] = height
        if guidance_scale is not None:
            kwargs["guidance_scale"] = guidance_scale
        if control_images and self.controlnet_infos:
            ordered = []
            scales = []
            for mode, scale in zip(self.controlnet_modes, self.controlnet_scales):
                img = control_images.get(mode) if control_images else None
                if img is None:
                    continue
                ordered.append(img)
                scales.append(scale)
            if ordered:
                kwargs["image"] = ordered if len(ordered) > 1 else ordered[0]
                if scales:
                    kwargs["controlnet_conditioning_scale"] = (
                        scales if len(ordered) > 1 else scales[0]
                    )
        
        image = pipe(**kwargs).images[0]
        return image

