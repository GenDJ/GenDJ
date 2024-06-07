import cv2
import numpy as np
from turbojpeg import TurboJPEG, TJPF_BGR
import zmq
import msgpack
import time
from threaded_worker import ThreadedWorker
from concurrent.futures import ThreadPoolExecutor
import asyncio


class BroadcastStream(ThreadedWorker):
    def __init__(self, port, settings, threaded_websocket):
        super().__init__(has_input=False, has_output=False)
        self.port = port
        self.fullscreen = False
        self.settings = settings
        self.threaded_websocket = threaded_websocket
        self.executor = ThreadPoolExecutor(max_workers=1)

    def setup(self):
        self.jpeg = TurboJPEG()

        self.context = zmq.Context()
        self.sock = self.context.socket(zmq.SUB)
        self.sock.setsockopt(zmq.RCVTIMEO, 100)
        self.sock.setsockopt(zmq.RCVHWM, 1)
        self.sock.setsockopt(zmq.LINGER, 0)
        address = f"tcp://localhost:{self.port}"
        print(f"Connecting to {address}")
        self.sock.connect(address)
        self.sock.setsockopt(zmq.SUBSCRIBE, b"")

    def show_msg(self, msg):
        timestamp, index, jpg = msgpack.unpackb(msg)
        img = self.jpeg.decode(jpg, pixel_format=TJPF_BGR)  # Decode to BGR format
        # img = cv2.resize(img, (512, 512))  # Resize to 512x512
        input_h, input_w = img.shape[:2]

        if self.settings.mirror:
            img = img[:, ::-1, :]

        if self.threaded_websocket is not None:
            print("sending1212")
            _, img_encoded = cv2.imencode(".jpg", img)  # Convert numpy array to JPEG
            img_bytes = img_encoded.tobytes()  # Convert JPEG image to bytes
            asyncio.run(self.threaded_websocket.send_data(img_bytes))
        else:
            print("No active WebSocket connection1212")

    def work(self):
        try:
            msg = self.sock.recv(flags=zmq.NOBLOCK, copy=False).bytes
            self.show_msg(msg)
        except zmq.Again:
            pass

    def cleanup(self):
        self.sock.close()
        self.context.term()
