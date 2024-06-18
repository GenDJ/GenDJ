const croppedCanvas = document.getElementById("croppedCanvas");
const processedCanvas = document.getElementById("processedCanvas");
const croppedCtx = croppedCanvas.getContext("2d");
const processedCtx = processedCanvas.getContext("2d");
let toClose;
let isStreaming = false;
const toggleButton = document.getElementById("toggle");

toggleButton.addEventListener("click", function () {
  isStreaming = !isStreaming;
  this.textContent = isStreaming ? "Stop" : "Start";
});

const frameQueue = [];
const frameTimestamps = [];
let isRendering = false;
let currentStream = null; // Track the current stream globally
let socket = null; // Global socket variable
let stopFrameCapture = false; // Flag to stop frame capture
let dropEvery = "none";

console.log("js loaded");

const dropFrame = { // this is so dum lol
  none: () => {
    return true;
  },
  2: (frameCounter) => {
    return frameCounter === 0 || frameCounter === 1 || frameCounter % 2 !== 0;
  },
  3: (frameCounter) => {
    return frameCounter === 0 || frameCounter === 1 || frameCounter % 3 !== 0;
  },
  4: (frameCounter) => {
    return frameCounter === 0 || frameCounter === 1 || frameCounter % 4 !== 0;
  },
  5: (frameCounter) => {
    return frameCounter === 0 || frameCounter === 1 || frameCounter % 5 !== 0;
  },
};


async function getVideoDevices() {
  const devices = await navigator.mediaDevices.enumerateDevices();
  return devices.filter((device) => device.kind === "videoinput");
}

async function selectVideoDevice() {
  const devices = await getVideoDevices();
  const deviceList = document.getElementById("deviceList");
  deviceList.innerHTML = "";

  devices.forEach((device, index) => {
    const option = document.createElement("option");
    option.value = device.deviceId;
    option.textContent = device.label || `Camera ${index + 1}`;
    deviceList.appendChild(option);
  });

  let selectedDeviceId = devices.length > 0 ? devices[0].deviceId : null;

  if (selectedDeviceId) {
    console.log("Initial selected device ID:", selectedDeviceId);
  }

  deviceList.addEventListener("change", async () => {
    selectedDeviceId = deviceList.value;
    console.log("User selected device ID:", selectedDeviceId);
    if (currentStream) {
      stopCurrentStream(); // Stop the current stream
    }
    if (toClose) {
      toClose();
    }
    await startVideoStream(selectedDeviceId); // Start a new stream with the selected device ID
  });

  return selectedDeviceId;
}

async function startVideoStream(deviceId) {
  try {
    stopFrameCapture = true; // Stop any ongoing frame capture
    const stream = await navigator.mediaDevices.getUserMedia({
      video: {
        deviceId: { exact: deviceId },
        width: { ideal: 512 },
        height: { ideal: 512 },
      },
    });

    stopFrameCapture = false; // Allow frame capture for the new stream
    currentStream = stream; // Update the current stream

    if (!socket) {
      socket = new WebSocket("ws://localhost:8765");

      socket.binaryType = "arraybuffer";

      socket.onopen = () => {
        console.log("WebSocket connection opened");
      };

      socket.onmessage = (event) => {
        const blob = new Blob([event.data], { type: "image/jpeg" });
        const url = URL.createObjectURL(blob);

        const img = new Image();
        img.onload = () => {
          URL.revokeObjectURL(url);
          frameQueue.push(img);
          frameTimestamps.push(Date.now());
          calculateFPS();
        };
        img.src = url;
      };

      socket.onclose = () => {
        console.log("WebSocket connection closed");
      };

      socket.onerror = (error) => {
        console.error("WebSocket error:", error);
      };
    }

    toClose = sendFrames(stream, socket);
    renderFrames();
  } catch (error) {
    console.error("Error accessing webcam:", error);
  }
}

function stopCurrentStream() {
  stopFrameCapture = true; // Stop capturing frames
  if (currentStream) {
    currentStream.getTracks().forEach((track) => track.stop());
    currentStream = null;
  }
  frameQueue.length = 0; // Clear the frame queue
}

function sendFrames(stream, socket) {
  const videoTrack = stream.getVideoTracks()[0];
  const imageCapture = new ImageCapture(videoTrack);
  let frameCounter = 0;
  let lastFrameTime = 0;
  const frameDuration = 1000 / 24;
  let open = true;

  const sendFrame = async (currentTime) => {
    if (stopFrameCapture || !open) return; // Exit if frame capture is stopped
    if (currentTime - lastFrameTime < frameDuration) {
      requestAnimationFrame(sendFrame);
      return;
    }

    try {
      if (videoTrack.readyState !== "live") {
        throw new Error("Video track is not live");
      }

      const frame = await imageCapture.grabFrame();
      const cropSize = 512;
      const cropX = Math.max(0, (frame.width - cropSize) / 2);
      const cropY = Math.max(0, (frame.height - cropSize) / 2);

      const targetWidth = 512;
      const targetHeight = 512;

      croppedCanvas.width = targetWidth;
      croppedCanvas.height = targetHeight;

      const scaleWidth = targetWidth / frame.width;
      const scaleHeight = targetHeight / frame.height;
      const scale = Math.min(scaleWidth, scaleHeight);

      const scaledWidth = frame.width * scale;
      const scaledHeight = frame.height * scale;

      const dx = (targetWidth - scaledWidth) / 2;
      const dy = (targetHeight - scaledHeight) / 2;

      croppedCtx.clearRect(0, 0, targetWidth, targetHeight);
      croppedCtx.drawImage(frame, dx, dy, scaledWidth, scaledHeight);

      if (frameCounter === 1) {
        console.log("f1212", frame.width, frame.height, cropSize, cropX, cropY);
      }

      croppedCanvas.toBlob(
        (blob) => {
          if (
            blob &&
            isStreaming &&
            socket.readyState === WebSocket.OPEN &&
            dropFrame[dropEvery](frameCounter)
          ) {
            blob.arrayBuffer().then((buffer) => {
              socket.send(buffer);
            });
          }
          lastFrameTime = currentTime;
          if (open) {
            requestAnimationFrame(sendFrame);
          }

          frameCounter++;
        },
        "image/jpeg",
        0.8
      );
    } catch (error) {
      console.error("Error capturing frame:", error);
    }
  };

  sendFrame();

  return function closeIt() {
    console.log("closing webcam");
    open = false;
  };
}

function renderFrames() {
  if (!isRendering) {
    isRendering = true;
    let lastRenderTime = Date.now();
    const render = () => {
      const now = Date.now();
      const fps = calculateFPS();
      const interval = fps > 0 ? 1000 / fps : 1000 / 24;
      if (
        (frameQueue.length > 0 && now - lastRenderTime >= interval) ||
        frameQueue.length > 8 ||
        (frameQueue.length > 0 && now - lastRenderTime >= 1000)
      ) {
        const img = frameQueue.shift();
        processedCtx.drawImage(
          img,
          0,
          0,
          processedCanvas.width,
          processedCanvas.height
        );
        lastRenderTime = now;
      }
      requestAnimationFrame(render);
    };
    render();
  }
}

document.getElementById("send").addEventListener("click", function () {
  var promptText = document.getElementById("prompt").value;
  var encodedPrompt = encodeURIComponent(promptText);
  var endpoint = "http://localhost:5556/prompt/" + encodedPrompt;

  fetch(endpoint, {
    method: "POST",
  })
    .then((response) => response.text())
    .then((data) => console.log(data))
    .catch((error) => {
      console.error("Error:", error);
    });
});

function calculateFPS() {
  const now = Date.now();
  const cutoff = now - 1000;
  while (frameTimestamps.length > 0 && frameTimestamps[0] < cutoff) {
    frameTimestamps.shift();
  }
  const fps = frameTimestamps.length;
  document.getElementById("fps").innerText = `FPS: ${fps}`;
  document.getElementById(
    "queue"
  ).innerText = `Queue size: ${frameQueue.length}`;
  return fps + 1;
}

document.getElementById("prompt").addEventListener("keydown", function (event) {
  if (event.key === "Enter") {
    document.getElementById("send").click();
  }
});

document.addEventListener("DOMContentLoaded", async () => {
  async function hasWebcamPermissions() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      stream.getTracks().forEach((track) => track.stop());
      return true;
    } catch (error) {
      return false;
    }
  }

  if (await hasWebcamPermissions()) {
    const deviceId = await selectVideoDevice();
    await startVideoStream(deviceId);
  } else {
    try {
      await navigator.mediaDevices.getUserMedia({ video: true });
      const deviceId = await selectVideoDevice();
      await startVideoStream(deviceId);
    } catch (error) {
      console.error("Webcam permissions are required to proceed.");
    }
  }

  const frameDrop = document.getElementById("frameDrop");
  frameDrop.addEventListener("change", function () {
    dropEvery = frameDrop.value;
    console.log("dropEvery set to:", dropEvery);
  });
});
