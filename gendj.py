import time
import zmq
import sdl2
import sdl2.ext
import numpy as np
import ctypes
import numpy as np
import torch
import torch.nn.functional as F
from turbojpeg import TurboJPEG, TJPF_RGB
from threaded_worker import ThreadedWorker
from diffusion_processor import DiffusionProcessor
from settings import Settings
from settings_api import SettingsAPI
from osc_settings_controller import OscSettingsController
# from threaded_websocket import ThreadedWebsocket
# from broadcast_stream import BroadcastStream
from batching_worker_new import BatchingWorker
from image_utils import unpack_rgb444_image, uyvy_to_rgb_batch, half_size_batch, get_texture_size
import threading
import asyncio
import websockets
import cv2
import numpy as np
from turbojpeg import TurboJPEG, TJPF_BGR
import msgpack
import time
from threaded_worker import ThreadedWorker
from concurrent.futures import ThreadPoolExecutor
import asyncio
from PIL import Image

# class ThreadedWebsocket(ThreadedWorker):
#     def __init__(self, settings):
#         super().__init__(has_input=False, has_output=True)
#         self.ws_port = settings.websocket_port
#         self.jpeg = TurboJPEG()
#         self.websocket = None
#         self.batch = []
#         self.settings_batch = []
#         self.batch_size = settings.batch_size

#     # def setup(self):
#     #     self.batch = []
#     #     self.settings_batch = []

#     async def handler(self, websocket, path):
#         self.websocket = websocket
#         print("WebSocket connection opened")
#         try:
#             while True:
#                 frame_data = await websocket.recv()
#                 print(f"Received frame of size {len(frame_data)} bytes")

#                 # Convert bytes to numpy array
#                 frame_data_np = np.frombuffer(frame_data, dtype=np.uint8)
#                 frame = self.jpeg.decode(frame_data_np, pixel_format=TJPF_RGB)

#                 # print("case1")
#                 # encoded_frame = self.jpeg.encode(frame)

#                 img = torch.from_numpy(frame).permute(2, 0, 1)

#                 # Convert the tensor to a PIL Image and save it
#                 img_pil = Image.fromarray(img.permute(1, 2, 0).cpu().numpy())
#                 img_pil.save('output_image.jpg')
#                 # self.batch.append(img) # on CPU from here
#                 self.batch.append(img.to("cuda"))  # on GPU from here
#                 self.settings_batch.append(settings.copy())

#                 n = self.batch_size
#                 if len(self.batch) >= n:
#                     batch = torch.stack(self.batch[:n])  # save the first n elements
#                     batch = batch.to(torch.float32) / 255.0
#                     batch = half_size_batch(batch)

#                     # batch = F.interpolate(batch, scale_factor=0.5, mode='area')
#                     settings_batch = self.settings_batch[:n]
#                     self.batch = self.batch[n:]  # drop the first n elements
#                     self.settings_batch = self.settings_batch[n:]
#                     # print("sending batch for processing", batch.shape)
#                     # return batch, settings_batch
#                     self.output_queue.put((batch, settings_batch))

#         except websockets.exceptions.ConnectionClosed:
#             print("WebSocket connection closed")
#         except Exception as e:
#             print(f"Error in WebSocket handler: {e}")
#         finally:
#             print("WebSocket handler finished")

#     async def send_data(self, data):
#         if self.websocket is not None:
#             await self.websocket.send(data)
#         else:
#             print("No active WebSocket connection")

#     def setup(self):
#         self.start_time = time.time()
#         self.frame_number = 0
#         self.loop = asyncio.new_event_loop()
#         asyncio.set_event_loop(self.loop)
#         self.server = websockets.serve(self.handler, "0.0.0.0", self.ws_port)
#         self.loop.run_until_complete(self.server)
#         print(f"WebSocket server1212 started on port {self.ws_port}")

#     def work(self):
#         try:
#             self.loop.run_forever()
#         except KeyboardInterrupt:
#             print("Server interrupted")
#         finally:
#             self.cleanup()

#     def cleanup(self):
#         if self.loop.is_running():
#             self.loop.stop()
#         print("WebSocket server stopped")

#     def start(self):
# self.parallel = threading.Thread(target=self.run)
# super().start()

class ThreadedWebsocket(ThreadedWorker):
    def __init__(self, settings):
        super().__init__(has_input=False, has_output=True)
        self.ws_port = settings.websocket_port
        self.jpeg = TurboJPEG()
        self.websocket = None
        self.batch = []
        self.settings_batch = []
        self.batch_size = settings.batch_size

    # def setup(self):
    #     self.batch = []
    #     self.settings_batch = []

    async def handler(self, websocket, path):
        self.websocket = websocket
        print("WebSocket connection opened")
        try:
            while True:
                frame_data = await websocket.recv()
                print(f"Received frame of size {len(frame_data)} bytes")

                # Convert bytes to numpy array
                frame_data_np = np.frombuffer(frame_data, dtype=np.uint8)
                frame = self.jpeg.decode(frame_data_np, pixel_format=TJPF_RGB)

                # # print("case1")
                # # encoded_frame = self.jpeg.encode(frame)

                img = torch.from_numpy(frame).permute(2, 0, 1)

                # # Convert the tensor to a PIL Image and save it
                # img_pil = Image.fromarray(img.permute(1, 2, 0).cpu().numpy())
                # img_pil.save('output_image.jpg')
                # # self.batch.append(img) # on CPU from here
                self.batch.append(img.to("cuda"))  # on GPU from here
                # self.batch.append(frame / 255)
                self.settings_batch.append(settings.copy())

                n = self.batch_size
                if len(self.batch) >= n:
                    batch = torch.stack(self.batch[:n])  # save the first n elements
                    batch = batch.to(torch.float32) / 255.0
                    # batch = half_size_batch(batch)

                    # batch = F.interpolate(batch, scale_factor=0.5, mode='area')
                    settings_batch = self.settings_batch[:n]
                    self.batch = self.batch[n:]  # drop the first n elements
                    self.settings_batch = self.settings_batch[n:]
                    # print("sending batch for processing", batch.shape)
                    # return batch, settings_batch
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
        # cuda_images = torch.FloatTensor(np.array(images)).to("cuda")

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
            # if frame_settings.opacity == 1:

            # else:
            #     opacity = float(frame_settings.opacity)
            #     input_image = np.transpose(image.cpu().numpy(), (1, 2, 0))[
            #         : result.shape[0]
            #     ]
            #     blended = result * opacity + input_image * (1 - opacity)
            #     blended = blended.astype(np.uint8)  # Ensure the numpy array is of type uint8
            #     # _, blended_encoded = cv2.imencode(".jpg", blended)  # Convert numpy array to JPEG
            #     # blended_bytes = blended_encoded.tobytes()  # Convert JPEG image to bytes

            #     # blended_bytes = self.jpeg.encode(blended, pixel_format=TJPF_RGB)
            #     # # img = torch.from_numpy(blended_bytes).permute(2, 0, 1)
            #     # # img_pil = Image.fromarray(img.permute(1, 2, 0).cpu().numpy())
            #     # # img_pil.save('output_image.jpg')
            #     # # self.output_queue.put(blended_bytes)

            #     # blended_array = np.frombuffer(blended_bytes, dtype=np.uint8).reshape(blended.shape)
            #     # img = torch.from_numpy(blended_array).permute(2, 0, 1)
            #     # img_pil = Image.fromarray(img.permute(1, 2, 0).cpu().numpy())
            #     # img_pil.save('output_image.jpg')
            #     # self.output_queue.put(blended_bytes)
            #     blended_bytes = self.jpeg.encode(blended, pixel_format=TJPF_RGB)
            #     blended_array = cv2.imdecode(np.frombuffer(blended_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
            #     img = torch.from_numpy(blended_array).permute(2, 0, 1)
            #     img_pil = Image.fromarray(img.permute(1, 2, 0).cpu().numpy())
            #     img_pil.save('output_image.jpg')
            #     self.output_queue.put(blended_bytes)

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
        # self.frame_repeat = 2

    def setup(self):
        self.jpeg = TurboJPEG()

    # def broadcast_msg(self, jpg):
    #     # timestamp, index, jpg = msgpack.unpackb(msg)
    #     # img = self.jpeg.decode(jpg, pixel_format=TJPF_BGR)  # Decode to BGR format
    #     # img = cv2.resize(img, (512, 512))  # Resize to 512x512
    #     # input_h, input_w = img.shape[:2]

    #     if self.settings.mirror:
    #         img = img[:, ::-1, :]

    #     if self.threaded_websocket is not None:
    #         print("sending1212")
    #         jpg = np.array(jpg)
    #         _, img_encoded = cv2.imencode(".jpg", jpg)  # Convert numpy array to JPEG
    #         img_bytes = img_encoded.tobytes()  # Convert JPEG image to bytes
    #         asyncio.run(self.threaded_websocket.send_data(img_bytes))
    #     else:
    #         print("No active WebSocket connection1212")


    def broadcast_msg(self, jpg):
        try:
            # Decode the JPEG image to a numpy array
            # nparr = np.frombuffer(jpg, np.uint8)
            # img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            # if img is None:
            #     print("Failed to decode image")
            #     return

            # if self.settings.mirror:
            #     img = img[:, ::-1, :]

            if self.threaded_websocket is not None:
                print("sending1212")
                # _, img_encoded = cv2.imencode(".jpg", img)  # Convert numpy array to JPEG
                # if not _:
                    # print("Failed to encode image")
                    # return
                # img_bytes = img_encoded.tobytes()  # Convert JPEG image to bytes
                # _, jpg_encoded = cv2.imencode(".jpg", jpg)

                # jpg = jpg_encoded.tobytes()

                asyncio.run(self.threaded_websocket.send_data(jpg))
            else:
                print("No active WebSocket connection1212")
        except Exception as e:
            print(f"Error in broadcast_msg: {e}")


    def work(self, frame):
        try:
            while self.input_queue.qsize() > self.settings.batch_size:
                # print("dropping display frame")
                frame = self.input_queue.get()

            # # Update texture
            # # image_data = (frame * 255).astype(np.uint8)
            # # Convert the frame to BGR format.
            # bgr_image = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            # # Encode the BGR image into a JPEG.
            # # Ensure you have a valid encoder setup, e.g., TurboJPEG
            # jpeg_image = self.jpeg.encode(bgr_image, pixel_format=TJPF_BGR)

            # if jpeg_image is None:
            #     print("Failed to encode image to JPEG")
            #     return

            if self.threaded_websocket is not None:
                # print("sending1212")
                # _, img_encoded = cv2.imencode(".jpg", image_data)  # Convert numpy array to JPEG
                # img_bytes = img_encoded.tobytes()  # Convert JPEG image to bytes
                # asyncio.run(self.threaded_websocket.send_data(img_bytes))
                self.broadcast_msg(frame)
            else:
                print("No active WebSocket connection1212")
        except Exception as e:
            print(f"Error in work: {e}")

    def cleanup(self):
        self.sock.close()
        self.context.term()
        sdl2.SDL_DestroyTexture(self.texture)
        sdl2.ext.quit()


settings = Settings()
settings_api = SettingsAPI(settings)
settings_controller = OscSettingsController(settings)

receiver = ThreadedWebsocket(settings)

processor = Processor(settings).feed(receiver)
# display = Display(settings.batch_size).feed(processor)
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
