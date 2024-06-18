import time
import sdl2
import sdl2.ext
import numpy as np
import numpy as np
import torch
import torch.nn.functional as F
from turbojpeg import TurboJPEG, TJPF_RGB
from threaded_worker import ThreadedWorker
from diffusion_processor import DiffusionProcessor
from settings import Settings
from settings_api import SettingsAPI
from osc_settings_controller import OscSettingsController
from image_utils import unpack_rgb444_image, uyvy_to_rgb_batch, half_size_batch, get_texture_size
import threading
import asyncio
import websockets
import numpy as np
from turbojpeg import TurboJPEG, TJPF_BGR
import time
from threaded_worker import ThreadedWorker
from concurrent.futures import ThreadPoolExecutor
import asyncio
from PIL import Image
class ThreadedWebsocket(ThreadedWorker):
    def __init__(self, settings):
        super().__init__(has_input=False, has_output=True)
        self.ws_port = settings.websocket_port
        self.jpeg = TurboJPEG()
        self.websocket = None
        self.batch = []
        self.settings_batch = []
        self.batch_size = settings.batch_size

    async def handler(self, websocket, path):
        self.websocket = websocket
        print("WebSocket connection opened")
        try:
            while True:
                frame_data = await websocket.recv()
                print(f"Received frame of size {len(frame_data)} bytes")
                frame_data_np = np.frombuffer(frame_data, dtype=np.uint8)
                frame = self.jpeg.decode(frame_data_np, pixel_format=TJPF_RGB)
                img = torch.from_numpy(frame).permute(2, 0, 1)
                self.batch.append(img.to("cuda"))  # on GPU from here
                self.settings_batch.append(settings.copy())

                n = self.batch_size
                if len(self.batch) >= n:
                    batch = torch.stack(self.batch[:n])
                    batch = batch.to(torch.float32) / 255.0
                    settings_batch = self.settings_batch[:n]
                    self.batch = self.batch[n:]  # drop the first n elements
                    self.settings_batch = self.settings_batch[n:]
                    self.output_queue.put((batch, settings_batch))

        except websockets.exceptions.ConnectionClosed:
            print("WebSocket connection closed")
        except Exception as e:
            print(f"Error in WebSocket handler: {e}")
        finally:
            print("WebSocket handler finished")

    async def send_data(self, data):
        if self.websocket is not None:
            await self.websocket.send(data)
        else:
            print("No active WebSocket connection")

    def setup(self):
        self.start_time = time.time()
        self.frame_number = 0
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.server = websockets.serve(self.handler, "0.0.0.0", self.ws_port)
        self.loop.run_until_complete(self.server)
        print(f"WebSocket server1212 started on port {self.ws_port}")

    def work(self):
        try:
            self.loop.run_forever()
        except KeyboardInterrupt:
            print("Server interrupted")
        finally:
            self.cleanup()

    def cleanup(self):
        if self.loop.is_running():
            self.loop.stop()
        print("WebSocket server stopped")

    def start(self):
        self.parallel = threading.Thread(target=self.run)
        super().start()
class Processor(ThreadedWorker):
    def __init__(self, settings):
        super().__init__(has_input=True, has_output=True, debug=True)
        self.batch_size = settings.batch_size
        self.settings = settings
        self.jpeg = TurboJPEG()

    def setup(self):
        self.diffusion_processor = DiffusionProcessor()
        self.clear_input()  # drop old frames
        self.runs = 0

    def work(self, args):
        images, settings_batch = args

        results = self.diffusion_processor.run(
            images=images,
            prompt=self.settings.prompt,
            use_compel=True,
            num_inference_steps=2,
            strength=0.7,
            seed=self.settings.seed,
        )

        for frame_settings, image, result in zip(settings_batch, images, results):
            result_uint8 = (result * 255).astype(np.uint8)
            result_bytes = self.jpeg.encode(result_uint8, pixel_format=TJPF_RGB)
            self.output_queue.put(result_bytes)

        self.runs += 1
        if self.runs < 3:
            print("warming up, dropping old frames")
            self.clear_input()

class BroadcastStream(ThreadedWorker):
    def __init__(self, port, settings, threaded_websocket):
        super().__init__(has_input=True, has_output=False)
        self.port = port
        self.fullscreen = False
        self.settings = settings
        self.threaded_websocket = threaded_websocket
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.batch_size = settings.batch_size

    def setup(self):
        self.jpeg = TurboJPEG()

    def broadcast_msg(self, jpg):
        try:
            if self.threaded_websocket is not None:
                asyncio.run(self.threaded_websocket.send_data(jpg))
            else:
                print("No active WebSocket connection1212")
        except Exception as e:
            print(f"Error in broadcast_msg: {e}")


    def work(self, frame):
        try:
            while self.input_queue.qsize() > self.settings.batch_size:
                frame = self.input_queue.get()

            if self.threaded_websocket is not None:
                self.broadcast_msg(frame)
            else:
                print("No active WebSocket connection1212")
        except Exception as e:
            print(f"Error in work: {e}")

    def cleanup(self):
        sdl2.SDL_DestroyTexture(self.texture)
        sdl2.ext.quit()


settings = Settings()
settings_api = SettingsAPI(settings)
settings_controller = OscSettingsController(settings)

receiver = ThreadedWebsocket(settings)

processor = Processor(settings).feed(receiver)
display = BroadcastStream(settings.output_port, settings, receiver).feed(processor)


settings_api.start()
settings_controller.start()
display.start()
processor.start()
receiver.start()

try:
    while True:
        time.sleep(1)
except:
    pass

settings_api.close()
settings_controller.close()
display.close()
processor.close()
receiver.close()
