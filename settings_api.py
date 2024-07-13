import threading
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import aiofiles
import os

import time
import json

from safety_checker import SafetyChecker


class SettingsAPI:
    def __init__(self, settings):
        self.shutdown = False
        self.settings = settings
        port = settings.settings_port
        self.thread = threading.Thread(target=self.run, args=(port,))
        self.prompt_0 = settings.prompt
        self.prompt_1 = "A psychedelic landscape."
        self.blend = 0

    def update_blend(self):
        if self.blend == 0:
            self.settings.prompt = self.prompt_0
        elif self.blend == 1:
            self.settings.prompt = self.prompt_1
        else:
            a = self.prompt_0
            b = self.prompt_1
            t = self.blend
            self.settings.prompt = f'("{a}", "{b}").blend({1-t:.2f}, {t:.2f})'

    def start(self):
        print("SettingsAPI starting1212")
        if not self.thread.is_alive():
            self.thread.start()

    def run(self, port):
        if self.settings.safety:
            safety_checker = SafetyChecker()

        app = FastAPI()

        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @app.post("/prompt/{msg}")
        async def prompt(msg: str):
            prompt = msg

            override = "-f" in prompt
            if override:
                prompt = prompt.replace("-f", "").strip()
            if self.settings.safety and not override:
                safety = safety_checker(prompt)
                if safety != "safe":
                    print(f"Ignoring prompt ({safety}):", prompt)
                    return {"safety": "unsafe"}

            self.prompt_0 = prompt
            self.update_blend()
            print("Updated prompt:", prompt)
            return {"safety": "safe"}

        @app.post("/secondprompt/{msg}")
        async def secondprompt(msg: str):
            prompt = msg

            override = "-f" in prompt
            if override:
                prompt = prompt.replace("-f", "").strip()
            if self.settings.safety and not override:
                safety = safety_checker(prompt)
                if safety != "safe":
                    print(f"Ignoring prompt ({safety}):", prompt)
                    return {"safety": "unsafe"}

            self.prompt_1 = prompt
            self.update_blend()
            print("Updated secondprompt:", prompt)
            return {"safety": "safe"}

        @app.post("/blend/{msg}")
        async def blend(msg: str):
            try:
                blend_value = float(msg)
                if 0 <= blend_value <= 1:
                    self.blend = blend_value
                    self.update_blend()
                    return {"status": "success", "blend": self.blend}
                else:
                    return {
                        "status": "error",
                        "message": "Blend value must be between 0 and 1",
                    }
            except ValueError:
                return {"status": "error", "message": "Invalid blend value"}

        @app.get("/directory/{status}")
        async def directory(status: str):
            self.settings.directory = "data/" + status
            print("Updated directory status:", self.settings.directory)
            return {"status": "updated"}

        @app.get("/debug/{status}")
        async def debug(status: bool):
            self.settings.debug = status
            print("Updated debug status:", status)
            return {"status": "updated"}

        @app.get("/compel/{status}")
        async def compel(status: bool):
            self.settings.compel = status
            print("Updated compel status:", status)
            return {"status": "updated"}

        @app.get("/passthrough/{status}")
        async def passthrough(status: bool):
            self.settings.passthrough = status
            print("Updated passthrough status:", self.settings.passthrough)
            return {"status": "updated"}

        @app.get("/fixed_seed/{status}")
        async def fixed_seed(status: bool):
            self.settings.fixed_seed = status
            print("Updated fixed_seed status:", self.settings.fixed_seed)
            return {"status": "updated"}

        @app.get("/mirror/{status}")
        async def mirror(status: bool):
            self.settings.mirror = status
            print("Updated mirror status:", status)
            return {"status": "updated"}

        @app.get("/batch_size/{value}")
        async def batch_size(value: int):
            self.settings.batch_size = value
            print("Updated batch_size:", self.settings.batch_size)
            return {"status": "updated"}

        @app.get("/seed/{value}")
        async def seed(value: int):
            self.settings.seed = value
            print("Updated seed:", self.settings.seed)
            return {"status": "updated"}

        @app.get("/steps/{value}")
        async def steps(value: int):
            self.settings.num_inference_steps = value
            print("Updated num_inference_steps:", self.settings.num_inference_steps)
            return {"status": "updated"}

        @app.get("/strength/{value}")
        async def strength(value: float):
            self.settings.strength = value
            print("Updated strength:", self.settings.strength)
            return {"status": "updated"}

        @app.get("/opacity/{value}")
        async def opacity(value: float):
            value = min(max(value, 0), 1)
            self.settings.opacity = value
            print("Updated opacity:", self.settings.opacity)
            return {"status": "updated"}

        if "READY_WEBHOOK_URL" not in os.environ:
            app.mount("/", StaticFiles(directory="fe", html=True), name="static")

        config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
        self.server = uvicorn.Server(config=config)
        try:
            self.server.run()
        except KeyboardInterrupt:
            pass

    def close(self):
        print("SettingsAPI closing")
        if hasattr(self, "server"):
            self.server.should_exit = True
        self.thread.join()
