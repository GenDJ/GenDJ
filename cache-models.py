import os
import torch
from diffusers import AutoPipelineForImage2Image, AutoencoderTiny
from diffusion_processor import DiffusionProcessor


class DiffusionProcessor:
    def __init__(self, warmup=None, local_files_only=True):
        base_model = "stabilityai/sdxl-turbo"
        vae_model = "madebyollin/taesdxl"

        self.pipe = AutoPipelineForImage2Image.from_pretrained(
            base_model,
            torch_dtype=torch.float16,
            variant="fp16",
            local_files_only=local_files_only,
        )

        self.pipe.vae = AutoencoderTiny.from_pretrained(
            vae_model, torch_dtype=torch.float16, local_files_only=local_files_only
        )

        print("Models loaded")

        # Other initializations (e.g., compiling the model) can go here

    def save_models(
        self,
        save_directory_base,
        save_directory_vae,
        safe_serialization=True,
        variant=None,
        push_to_hub=False,
        **kwargs,
    ):
        # Ensure the save directories exist
        if not os.path.exists(save_directory_base):
            os.makedirs(save_directory_base)
        if not os.path.exists(save_directory_vae):
            os.makedirs(save_directory_vae)

        # Save the base model
        self.pipe.save_pretrained(
            save_directory_base,
            safe_serialization=safe_serialization,
            variant=variant,
            push_to_hub=push_to_hub,
            **kwargs,
        )
        print(f"Base model saved to {save_directory_base}")

        # Save the VAE model
        self.pipe.vae.save_pretrained(
            save_directory_vae,
            safe_serialization=safe_serialization,
            variant=variant,
            push_to_hub=push_to_hub,
            **kwargs,
        )
        print(f"VAE model saved to {save_directory_vae}")


# Example usage
processor = DiffusionProcessor(local_files_only=False)
save_dir_base = "./saved_pipeline/sdxl-turbo"
save_dir_vae = "./saved_pipeline/taesdxl"
processor.save_models(
    save_directory_base=save_dir_base,
    save_directory_vae=save_dir_vae,
    safe_serialization=True,
    variant="fp16",
    push_to_hub=False,  # Change to True if you want to push to Hugging Face hub
)
