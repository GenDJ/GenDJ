import time
import sdl2
import sdl2.ext
import numpy as np
import torch
import torch.nn.functional as F
from turbojpeg import TurboJPEG, TJPF_RGB
from threaded_worker import ThreadedWorker
from diffusion_processor import DiffusionProcessor
from settings import Settings
from settings_api import SettingsAPI
from osc_settings_controller import OscSettingsController
from image_utils import (
    unpack_rgb444_image,
    uyvy_to_rgb_batch,
    half_size_batch,
    get_texture_size,
)
import threading
import asyncio
import websockets
from threaded_worker import ThreadedWorker
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from PIL import Image
import signal
import sys
import argparse
import os

from websockets.server import serve


class ThreadedWebsocket(ThreadedWorker):
    def __init__(self, settings):
        super().__init__(has_input=False, has_output=True)
        self.ws_port = settings.websocket_port
        self.jpeg = TurboJPEG()
        self.websocket = None
        self.batch = []
        self.settings_batch = []
        self.batch_size = settings.batch_size
        self.loop = None
        self.settings = settings
        self.server = None
        self.stop_event = threading.Event()
        self.cleanup_called = False  # Add this flag

    async def handler(self, websocket, path):
        self.websocket = websocket
        print("WebSocket connection opened")
        first_frame = True
        try:
            while True:
                frame_data = await websocket.recv()
                if first_frame:
                    print(f"Received frame of size {len(frame_data)} bytes")
                    first_frame = False
                frame_data_np = np.frombuffer(frame_data, dtype=np.uint8)
                frame = self.jpeg.decode(frame_data_np, pixel_format=TJPF_RGB)
                img = torch.from_numpy(frame).permute(2, 0, 1)
                self.batch.append(img.to("cuda"))  # on GPU from here
                self.settings_batch.append(self.settings.copy())

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
        if self.websocket is not None and self.websocket.open:
            try:
                await self.websocket.send(data)
            except Exception as e:
                print(f"Error sending data: {e}")
        else:
            print("No active WebSocket connection")

    def setup(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.server = self.loop.run_until_complete(
            serve(self.handler, "0.0.0.0", self.ws_port)
        )
        print(f"WebSocket server started on port {self.ws_port}")

    def work(self):
        try:
            self.loop.run_until_complete(self.run_server())
        except Exception as e:
            print(f"Error in ThreadedWebsocket work: {e}")
        finally:
            self.loop.call_soon_threadsafe(self.cleanup)

    async def run_server(self):
        while not self.stop_event.is_set():
            await asyncio.sleep(0.1)

    async def async_cleanup(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        remaining_tasks = [
            task
            for task in asyncio.all_tasks(self.loop)
            if task is not asyncio.current_task()
        ]
        for task in remaining_tasks:
            task.cancel()
        await asyncio.gather(*remaining_tasks, return_exceptions=True)

    def stop_loop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)

    def cleanup(self):
        if self.cleanup_called:
            return
        self.cleanup_called = True

        print("ThreadedWebsocket cleanup")
        if self.loop and not self.loop.is_closed():
            try:
                self.stop_loop()
                future = asyncio.run_coroutine_threadsafe(
                    self.async_cleanup(), self.loop
                )
                try:
                    future.result(timeout=2)  # Wait for up to 2 seconds
                except TimeoutError:
                    print("ThreadedWebsocket async cleanup timed out")
            except Exception as e:
                print(f"Error during ThreadedWebsocket async cleanup: {e}")
            finally:
                if self.loop and not self.loop.is_closed():
                    self.loop.close()

        print("WebSocket server stopped")

    def start(self):
        self.parallel = threading.Thread(target=self.run)
        super().start()

    def close(self):
        print("ThreadedWebsocket closing")
        self.stop_event.set()
        self.loop.call_soon_threadsafe(self.cleanup)
        super().close()


class Processor(ThreadedWorker):
    def __init__(self, settings, use_cached=False):
        super().__init__(has_input=True, has_output=True, debug=True)
        self.batch_size = settings.batch_size
        self.settings = settings
        print("Settings1:", settings)

        self.jpeg = TurboJPEG()
        self.use_cached = use_cached

    def setup(self):
        warmup = None
        if self.settings.warmup:
            warmup = self.settings.warmup  # f"{settings.batch_size}x{settings.warmup}"
            print(f"warmup from settings is: {warmup}")
        self.diffusion_processor = DiffusionProcessor(
            warmup=warmup, use_cached=self.use_cached, settings=self.settings
        )
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
                future = asyncio.run_coroutine_threadsafe(
                    self.threaded_websocket.send_data(jpg), self.threaded_websocket.loop
                )
                future.result()  # Wait for the coroutine to complete
            else:
                print("No active WebSocket connection")
        except Exception as e:
            print(f"Error in broadcast_msg: {e}")

    def work(self, frame):
        try:
            while self.input_queue.qsize() > self.settings.batch_size:
                frame = self.input_queue.get()

            if self.threaded_websocket is not None:
                self.broadcast_msg(frame)
            else:
                print("No active WebSocket connection")
        except Exception as e:
            print(f"Error in work: {e}")

    def cleanup(self):
        try:
            if hasattr(self, "texture") and self.texture is not None:
                sdl2.SDL_DestroyTexture(self.texture)
            sdl2.ext.quit()
        except Exception as e:
            print(f"Error during cleanup: {e}")


def main():
    parser = argparse.ArgumentParser(description="Run gendj.py with specified options.")
    parser.add_argument(
        "--use_cached",
        action="store_true",
        help="Use cached models in DiffusionProcessor",
    )
    args = parser.parse_args()

    settings = Settings()
    print(f"Using websocket_port from Settings: {settings.websocket_port}")
    settings_api = SettingsAPI(settings)
    settings_controller = OscSettingsController(settings)

    receiver = ThreadedWebsocket(settings)
    processor = Processor(settings, use_cached=args.use_cached).feed(receiver)
    display = BroadcastStream(settings.output_port, settings, receiver).feed(processor)

    # Main program signal handling
    def signal_handler(signal, frame):
        print("Signal received, closing...")
        components = [display, processor, receiver, settings_controller, settings_api]

        for component in components:
            component_name = getattr(component, "name", component.__class__.__name__)
            print(f"Closing {component_name}...")
            if hasattr(component, "close"):
                component.close()

        # Wait for all components to finish
        for component in components:
            if hasattr(component, "parallel"):
                try:
                    component.parallel.join(timeout=10)
                except TimeoutError:
                    print(f"{component.__class__.__name__} failed to close in time")

        print("All components closed, exiting...")
        os._exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start the components
    settings_api.start()
    settings_controller.start()
    display.start()
    processor.start()
    receiver.start()

    exit_event = threading.Event()
    try:
        while not exit_event.is_set():
            exit_event.wait(1)
    except KeyboardInterrupt:
        pass
    finally:
        print("Main loop exiting, closing components...")
        signal_handler(signal.SIGINT, None)


if __name__ == "__main__":
    main()
