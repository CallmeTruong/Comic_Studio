from pathlib import Path
from core.stable_diffusion import SD

print("Initializing SD...")
try:
    sd = SD(
        model_path="models/base/comicBabes_v2.safetensors",
        device="cuda",
        base="SDv1.5",
        negative_embedding_path="models/embeddings/negative_hand-neg.pt",
        controlnet_infos=None
    )
    print("SD initialized successfully.")
    
    print("Loading LoRA...")
    sd.load_lora("models/loras/ghibli_style_offset.safetensors", 1.0)
    print("LoRA loaded successfully.")
except Exception as e:
    print(f"FAILED WITH EXCEPTION: {type(e).__name__}: {str(e)}")
