import asyncio
import websockets
import threading
import time
from threaded_worker import ThreadedWorker
from turbojpeg import TurboJPEG
import numpy as np


class ThreadedWebsocket(ThreadedWorker):
    def __init__(self, settings):
        super().__init__(has_input=False)
        self.ws_port = settings.websocket_port
        self.jpeg = TurboJPEG()
        self.websocket = None

    async def handler(self, websocket, path):
        self.websocket = websocket
        print("WebSocket connection opened")
        try:
            while True:
                frame_data = await websocket.recv()
                print(f"Received frame of size {len(frame_data)} bytes")
                frame = self.jpeg.decode(np.frombuffer(frame_data, dtype=np.uint8))
                timestamp = time.time()
                self.frame_number += 1

                # Encode the frame back to JPEG bytes
                encoded_frame = self.jpeg.encode(frame)
                result = (timestamp, self.frame_number, encoded_frame)

                if result is not None and hasattr(self, "output_queue"):
                    self.output_queue.put(result)

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
