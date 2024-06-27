import re
import numpy as np
import time
from fixed_seed import fix_seed

from sfast.compilers.stable_diffusion_pipeline_compiler import (
    compile,
    CompilationConfig,
)

from diffusers.utils.logging import disable_progress_bar
from diffusers import AutoPipelineForImage2Image, AutoencoderTiny
import torch
import warnings

from compel import Compel, ReturnedEmbeddingsType
from fixed_size_dict import FixedSizeDict


class DiffusionProcessor:
    def __init__(
        self, warmup=None, local_files_only=True, use_cached=False, settings=None
    ):
        self.settings = settings
        print("Settings2:", settings)

        if use_cached:
            base_model = "./saved_pipeline/sdxl-turbo"
            vae_model = "./saved_pipeline/taesdxl"
        else:
            base_model = "stabilityai/sdxl-turbo"
            vae_model = "madebyollin/taesdxl"

        warnings.filterwarnings("ignore", category=torch.jit.TracerWarning)

        disable_progress_bar()

        if use_cached:
            self.pipe = AutoPipelineForImage2Image.from_pretrained(
                base_model,
                torch_dtype=torch.float16,
                variant="fp16",
                local_files_only=local_files_only,
            )

            self.pipe.vae = AutoencoderTiny.from_pretrained(
                vae_model,
                subfolder="diffusion_pytorch_model.fp16.safetensors",
                torch_dtype=torch.float16,
                local_files_only=local_files_only,
            )
        else:
            self.pipe = AutoPipelineForImage2Image.from_pretrained(
                base_model,
                torch_dtype=torch.float16,
                variant="fp16",
                local_files_only=local_files_only,
            )

            self.pipe.vae = AutoencoderTiny.from_pretrained(
                vae_model, torch_dtype=torch.float16, local_files_only=local_files_only
            )

        fix_seed(self.pipe)

        print("Model loaded")

        config = CompilationConfig.Default()
        config.enable_xformers = True
        config.enable_triton = True
        config.enable_cuda_graph = True
        self.pipe = compile(self.pipe, config=config)

        print("Model compiled")

        self.pipe.to(device="cuda", dtype=torch.float16)
        self.pipe.set_progress_bar_config(disable=True)

        print("Model moved to GPU", flush=True)

        self.compel = Compel(
            tokenizer=[self.pipe.tokenizer, self.pipe.tokenizer_2],
            text_encoder=[self.pipe.text_encoder, self.pipe.text_encoder_2],
            returned_embeddings_type=ReturnedEmbeddingsType.PENULTIMATE_HIDDEN_STATES_NON_NORMALIZED,
            requires_pooled=[False, True],
        )
        self.prompt_cache = FixedSizeDict(32)
        print("Prepared compel")

        self.generator = torch.manual_seed(0)

        if warmup:
            print("Starting warmup")
            warmup_shape = [int(e) for e in warmup.split("x")]
            images = np.zeros(warmup_shape, dtype=np.float32)
            for i in range(2):
                print(f"Warmup {warmup} {i+1}/2")
                start_time = time.time()
                self.run(
                    images=images,
                    prompt=self.settings.prompt,
                    use_compel=True,
                    num_inference_steps=2,
                    strength=0.7,
                    seed=self.settings.seed,
                )
                end_time = time.time()
                duration = end_time - start_time
                print(f"Warmup {i+1}/2 took {duration:.2f} seconds", flush=True)
            print("Warmup finished", flush=True)

    def embed_prompt(self, prompt):
        if prompt not in self.prompt_cache:
            start_time = time.time()
            with torch.no_grad():
                print("embedding prompt", prompt)
                self.prompt_cache[prompt] = self.compel(prompt)
            end_time = time.time()
            elapsed_time = end_time - start_time
            print(f"Time taken to embed the prompt: {elapsed_time:.4f} seconds")
        return self.prompt_cache[prompt]

    def meta_embed_prompt(self, prompt):
        pattern = r'\("(.*?)"\s*,\s*"(.*?)"\)\.blend\((.*?),(.*?)\)'
        match = re.search(pattern, prompt)
        if not match:
            return self.embed_prompt(prompt)
        str1, str2, t1, t2 = match.groups()
        t1 = float(t1)
        t2 = float(t2)
        cond1, pool1 = self.embed_prompt(str1)
        cond2, pool2 = self.embed_prompt(str2)
        cond = cond1 * t1 + cond2 * t2
        pool = pool1 * t1 + pool2 * t2
        return cond, pool

    def run(
        self, images, prompt, num_inference_steps, strength, use_compel=False, seed=None
    ):
        strength = min(max(1 / num_inference_steps, strength), 1)
        if seed is not None:
            self.generator = torch.manual_seed(seed)
        kwargs = {}
        if use_compel:
            conditioning, pooled = self.meta_embed_prompt(prompt)
            batch_size = len(images)
            conditioning_batch = conditioning.expand(batch_size, -1, -1)
            pooled_batch = pooled.expand(batch_size, -1)
            kwargs["prompt_embeds"] = conditioning_batch
            kwargs["pooled_prompt_embeds"] = pooled_batch
        else:
            kwargs["prompt"] = [prompt] * len(images)
        return self.pipe(
            image=images,
            generator=self.generator,
            num_inference_steps=num_inference_steps,
            guidance_scale=0,
            strength=strength,
            output_type="np",
            **kwargs,
        ).images
