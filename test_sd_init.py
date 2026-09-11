from diffusers import StableDiffusionPipeline
import torch

try:
    pipe = StableDiffusionPipeline.from_single_file(
        "models/base/comicBabes_v2.safetensors",
        torch_dtype=torch.float16,
    )
    print("Success")
except Exception as e:
    import traceback
    traceback.print_exc()
