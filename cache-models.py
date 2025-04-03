import os
import torch
from diffusers import AutoPipelineForImage2Image, AutoencoderTiny
# Remove the local DiffusionProcessor definition if it's not needed elsewhere
# from diffusion_processor import DiffusionProcessor # Assuming this isn't needed just for caching
import sys
import traceback

# --- Configuration ---
BASE_MODEL_REPO = "stabilityai/sdxl-turbo"
VAE_MODEL_REPO = "madebyollin/taesdxl"
SAVE_DIR_BASE = "./saved_pipeline/sdxl-turbo"
SAVE_DIR_VAE = "./saved_pipeline/taesdxl"

# --- Main Caching Logic ---
def cache_models():
    print("--- Starting Model Caching ---")
    print(f"Attempting to download/cache Base Model: {BASE_MODEL_REPO}")
    print(f"Attempting to download/cache VAE Model: {VAE_MODEL_REPO}")

    pipe = None
    vae = None

    # --- Load/Download Base Model Pipeline ---
    try:
        pipe = AutoPipelineForImage2Image.from_pretrained(
            BASE_MODEL_REPO,
            torch_dtype=torch.float16, # Load in FP16
            variant="fp16",
            local_files_only=False, # Ensure downloading is enabled
            # cache_dir=os.path.join(".", "huggingface_cache") # Optional: specify cache dir
        )
        print(f"Successfully loaded base model pipeline: {BASE_MODEL_REPO}")
    except Exception as e:
        print(f"\n!!! ERROR loading base model pipeline ({BASE_MODEL_REPO}): {e}")
        print("Please check the repository name, your internet connection, and Hugging Face status.")
        traceback.print_exc()
        # Don't exit yet, try loading VAE separately

    # --- Load/Download VAE Model ---
    try:
        vae = AutoencoderTiny.from_pretrained(
            VAE_MODEL_REPO,
            torch_dtype=torch.float16, # Load in FP16
            local_files_only=False, # Ensure downloading is enabled
            # cache_dir=os.path.join(".", "huggingface_cache") # Optional: specify cache dir
        )
        print(f"Successfully loaded VAE model: {VAE_MODEL_REPO}")
    except Exception as e:
        print(f"\n!!! ERROR loading VAE model ({VAE_MODEL_REPO}): {e}")
        print("Please check the repository name, your internet connection, and Hugging Face status.")
        traceback.print_exc()
        # If the pipeline loaded but VAE failed, we might still be able to save the pipeline part
        # If the pipeline also failed, we definitely can't proceed

    if pipe is None:
         print("\n!!! Cannot proceed with saving as the base pipeline failed to load.")
         return False # Indicate failure

    # Assign VAE if loaded successfully
    if vae is not None:
        pipe.vae = vae
    else:
        print("\n!!! VAE failed to load. The main pipeline might be saved without the correct VAE.")
        # Decide if you want to proceed without the VAE or fail completely
        # return False # Option to fail if VAE is mandatory

    # --- Save Models to Target Directory ---
    print("\n--- Saving Models to ./saved_pipeline ---")

    # Ensure the save directories exist
    os.makedirs(SAVE_DIR_BASE, exist_ok=True)
    os.makedirs(SAVE_DIR_VAE, exist_ok=True)

    save_success = True

    # Save the base model pipeline components
    try:
        # Note: This saves the *entire* pipeline structure, including its default VAE
        # if the specific one wasn't loaded/assigned above.
        # If you only want to save specific components, adjust accordingly.
        pipe.save_pretrained(
            SAVE_DIR_BASE,
            safe_serialization=True, # Recommended
            variant="fp16", # Save in FP16 variant
        )
        print(f"Base model pipeline saved to {SAVE_DIR_BASE}")
    except Exception as e:
        print(f"\n!!! ERROR saving base model pipeline to {SAVE_DIR_BASE}: {e}")
        traceback.print_exc()
        save_success = False

    # Save the VAE separately IF it was loaded successfully
    # This ensures the specific VAE files are in the VAE directory
    if vae is not None:
        try:
            vae.save_pretrained(
                SAVE_DIR_VAE,
                safe_serialization=True, # Revert to True (recommended)
                variant="fp16", # Still specify fp16 variant if applicable
            )
            print(f"VAE model saved to {SAVE_DIR_VAE} (using .safetensors format)") # Update log message
        except Exception as e:
            print(f"\n!!! ERROR saving VAE model to {SAVE_DIR_VAE}: {e}")
            traceback.print_exc()
            save_success = False
    else:
         print(f"Skipping VAE save to {SAVE_DIR_VAE} as it failed to load.")
         # If VAE is essential, ensure this reflects in overall success
         # save_success = False

    if save_success:
        print("\n--- Model Caching Finished Successfully ---")
        return True
    else:
        print("\n!!! Model Caching Finished with Errors ---")
        return False

# --- Script Entry Point ---
if __name__ == "__main__":
    if not cache_models():
        sys.exit(1) # Exit with error code if caching failed
