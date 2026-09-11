import torch
from pathlib import Path
from diffusers import (
    StableDiffusionPipeline,
    StableDiffusionXLPipeline,
    ControlNetModel,
    StableDiffusionControlNetPipeline,
    MultiControlNetModel,
)
from diffusers.utils import load_image
from PIL import Image

try:
    from compel import Compel
    _COMPEL_AVAILABLE = True
except ImportError:
    _COMPEL_AVAILABLE = False
    print("[WARN] compel not installed — falling back to raw text prompts (77-token limit).")

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
        # Half precision is supported by CUDA SD kernels, but not by the CPU
        # fallback.  Select the dtype once and use it consistently while
        # loading every component; otherwise a machine with an unavailable
        # driver reaches the renderer and fails later with an opaque CUDA/CPU
        # invalid-argument error.
        self.use_cuda = device == "cuda" and torch.cuda.is_available()
        self.runtime_device = "cuda" if self.use_cuda else "cpu"
        self.dtype = torch.float16 if self.use_cuda else torch.float32
        
        print(f"[SD] Loading model: {model_path}")
        
        if base == "SDXL":
            self.pipe = StableDiffusionXLPipeline.from_pretrained(
                model_path,
                torch_dtype=self.dtype,
                use_safetensors=True,
                variant="fp16" if self.use_cuda else None,
            )
        elif base == "SDv1.5":
            if self.controlnet_infos:
                control_models = []
                for info in self.controlnet_infos:
                    path = info.get("path")
                    if not path or not Path(path).exists():
                        continue
                    print(f"[SD] Loading ControlNet ({info.get('mode','unknown')}): {path}")
                    control_models.append(
                        ControlNetModel.from_single_file(path, torch_dtype=self.dtype)
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
                        torch_dtype=self.dtype,
                    )
                else:
                    self.controlnet_infos = []
                    self.controlnet_modes = []
                    self.controlnet_scales = []
                    self.pipe = StableDiffusionPipeline.from_single_file(
                        model_path,
                        torch_dtype=self.dtype,
                    )
            else:
                self.pipe = StableDiffusionPipeline.from_single_file(
                    model_path,
                    torch_dtype=self.dtype,
                )
        else:
            raise ValueError(f"Unsupported base: {base}")
        
        if self.use_cuda:
            self.pipe.to(self.runtime_device)
            # self.pipe.enable_model_cpu_offload() # Uncomment to save VRAM
        else:
            print("[WARN] CUDA not available or not selected. Running on CPU.")
            self.pipe.to(self.runtime_device)
        
        # Disable slicing to maximize speed (uses more VRAM)
        # self.pipe.enable_attention_slicing()
        # self.pipe.enable_vae_slicing()
        print(f"[SD] OK Model loaded on {self.runtime_device} ({self.dtype})")
        
        # Text-only conditioning avoids reference-image composition leakage.
            
        if negative_embedding_path and Path(negative_embedding_path).exists():
            self._load_negative_embedding(negative_embedding_path)

        # --- Compel: long-prompt chunking & weighting -----------------
        # Initialise *after* textual-inversion tokens have been registered
        # so that Compel's tokenizer copy knows about them.
        self.compel: Compel | None = None
        if _COMPEL_AVAILABLE and self.base == "SDv1.5":
            try:
                self.compel = Compel(
                    tokenizer=self.pipe.tokenizer,
                    text_encoder=self.pipe.text_encoder,
                    truncate_long_prompts=False,
                )
                print("[SD] OK Compel initialised (long-prompt chunking enabled)")
            except Exception as exc:
                print(f"[WARN] Compel init failed ({exc}). Using raw text prompts.")
                self.compel = None
        elif self.base == "SDXL":
            # SDXL has two text encoders and pooled conditioning; keep the
            # native diffusers prompt path until an SDXL-specific Compel
            # adapter is configured, rather than passing SD1.5 embeddings to
            # the SDXL pipeline.
            print("[SD] SDXL native prompt encoding enabled")
    
    def _load_negative_embedding(self, embedding_path: str):
        try:
            print(f"[SD] Loading negative embedding: {embedding_path}")
            embedding_dict = torch.load(embedding_path, map_location=self.runtime_device)
            
            if isinstance(embedding_dict, dict):
                if "name" in embedding_dict:
                    self.negative_embedding_token = embedding_dict["name"]
                elif "string_to_param" in embedding_dict:
                    string_to_param = embedding_dict["string_to_param"]
                    if isinstance(string_to_param, dict) and len(string_to_param) > 0:
                        self.negative_embedding_token = list(string_to_param.keys())[0]
                
                if self.negative_embedding_token:
                    self.pipe.load_textual_inversion(embedding_path, token=self.negative_embedding_token)
                    print(f"[SD] OK Negative embedding loaded and applied: token='{self.negative_embedding_token}'")
                else:
                    print(f"[WARN] Cannot find embedding token name")
            else:
                print(f"[WARN] Embedding file format not recognized")
        except Exception as e:
            print(f"[WARN] Failed to load negative embedding: {e}")
            self.negative_embedding_token = None

    def load_lora(self, lora_path: str, scale: float = 1):
        if not lora_path:
            return False
        print(f"[SD] Loading LoRA: {lora_path} (scale={scale})")
        try:
            self.pipe.load_lora_weights(lora_path)
            self.pipe.fuse_lora(lora_scale=scale)
            print(f"[SD] LoRA loaded and fused: {lora_path}")
            return True
        except (IndexError, KeyError, ValueError, RuntimeError, ImportError) as exc:
            print(f"[WARN] Could not load LoRA '{lora_path}': {exc}. Continuing without LoRA.")
            return False

    def _encode_prompt_pair(
        self, positive: str, negative: str
    ) -> tuple[torch.Tensor, torch.Tensor] | tuple[None, None]:
        """Encode positive & negative prompts via Compel and pad to equal length.

        Returns (prompt_embeds, negative_prompt_embeds) tensors, or
        (None, None) when Compel is unavailable and the caller should
        fall back to raw text.
        """
        if self.compel is None:
            return None, None
        try:
            prompt_embeds = self.compel(positive)
            negative_embeds = self.compel(negative)
            # Positive and negative embeddings MUST have the same sequence
            # length for the UNet cross-attention to work correctly.
            [prompt_embeds, negative_embeds] = (
                self.compel.pad_conditioning_tensors_to_same_length(
                    [prompt_embeds, negative_embeds]
                )
            )
            pos_chunks = prompt_embeds.shape[1] // 77 if prompt_embeds.ndim >= 2 else 1
            neg_chunks = negative_embeds.shape[1] // 77 if negative_embeds.ndim >= 2 else 1
            print(
                f"[COMPEL] Encoded: positive {prompt_embeds.shape[1]} dims "
                f"({pos_chunks} chunks), negative {negative_embeds.shape[1]} dims "
                f"({neg_chunks} chunks)"
            )
            return prompt_embeds, negative_embeds
        except Exception as exc:
            print(f"[WARN] Compel encoding failed ({exc}). Falling back to raw text.")
            return None, None

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
            generator = torch.Generator(device=self.runtime_device).manual_seed(seed)
        
        negative_prompt = base_negative or ""
        if self.negative_embedding_token:
            if negative_prompt:
                negative_prompt = f"{self.negative_embedding_token}, {negative_prompt}"
            else:
                negative_prompt = self.negative_embedding_token
        
        # --- Try Compel embedding path first, fall back to raw text ----
        prompt_embeds, negative_embeds = self._encode_prompt_pair(
            context, negative_prompt
        )

        kwargs: dict = {"num_inference_steps": sep}

        if prompt_embeds is not None:
            # Compel path: pass pre-computed embeddings
            kwargs["prompt_embeds"] = prompt_embeds
            kwargs["negative_prompt_embeds"] = negative_embeds
        else:
            # Fallback: raw text (truncated at 77 tokens by the pipeline)
            kwargs["prompt"] = context
            kwargs["negative_prompt"] = negative_prompt
        
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
