const croppedCanvas = document.getElementById("croppedCanvas");
const processedCanvas = document.getElementById("processedCanvas");
const croppedCtx = croppedCanvas.getContext("2d");
const processedCtx = processedCanvas.getContext("2d");

let isStreaming = false;
const toggleButton = document.getElementById("toggle");

toggleButton.addEventListener("click", function () {
  isStreaming = !isStreaming;
  this.textContent = isStreaming ? "Stop" : "Start";
});

const frameQueue = [];
const frameTimestamps = [];
let isRendering = false;
console.log("womp1212");

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

  const selectedDeviceId = await new Promise((resolve) => {
    deviceList.addEventListener("change", () => {
      resolve(deviceList.value);
    });
  });

  return selectedDeviceId;
}

async function startVideoStream(deviceId) {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: {
        deviceId: { exact: deviceId },
        width: { ideal: 512 }, // Specify your desired width
        height: { ideal: 512 }, // Specify your desired height
      },
    });

    const socket = new WebSocket("ws://localhost:8765");

    socket.binaryType = "arraybuffer";

    socket.onopen = () => {
      console.log("WebSocket connection opened");
      sendFrames(stream, socket);
    };

    console.log("doop1212");
    socket.onmessage = (event) => {
      // console.log("socketmessage1212", event);
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

    renderFrames();
  } catch (error) {
    console.error("Error accessing webcam:", error);
  }
}

function sendFrames(stream, socket) {
  const videoTrack = stream.getVideoTracks()[0];
  const imageCapture = new ImageCapture(videoTrack);
  let frameCounter = 0;
  let lastFrameTime = 0;
  const frameDuration = 1000 / 24; // Duration of a frame in ms for 30 FPS

  const sendFrame = async (currentTime) => {
    if (currentTime - lastFrameTime < frameDuration) {
      requestAnimationFrame(sendFrame);
      return;
    }

    try {
      // uncomment this to switch to cropping the camera instead of scaling
      // const frame = await imageCapture.grabFrame();

      // const cropSize = 512;
      // const cropX = Math.max(0, (frame.width - cropSize) / 2);
      // const cropY = Math.max(0, (frame.height - cropSize) / 2);

      // croppedCanvas.width = cropSize;
      // croppedCanvas.height = cropSize;

      // croppedCtx.clearRect(0, 0, cropSize, cropSize);
      // croppedCtx.drawImage(
      //   frame,
      //   cropX,
      //   cropY,
      //   cropSize,
      //   cropSize,
      //   0,
      //   0,
      //   cropSize,
      //   cropSize
      // );

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
            (frameCounter % 2 === 0 ||
              frameCounter % 3 === 0 ||
              frameCounter & (5 === 0))
          ) {
            blob.arrayBuffer().then((buffer) => {
              socket.send(buffer);
            });
          }
          lastFrameTime = currentTime;
          requestAnimationFrame(sendFrame);
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
}

function renderFrames() {
  if (!isRendering) {
    isRendering = true;
    let lastRenderTime = Date.now();
    const render = () => {
      const now = Date.now();
      const fps = calculateFPS();
      const interval = fps > 0 ? 1000 / fps : 1000 / 24; // Default to 24 FPS if no frames received
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
  const cutoff = now - 1000; // 1 second ago
  while (frameTimestamps.length > 0 && frameTimestamps[0] < cutoff) {
    frameTimestamps.shift();
  }
  const fps = frameTimestamps.length;
  // console.log(`FPS: ${fps}`);
  document.getElementById("fps").innerText = `FPS: ${fps}`;
  document.getElementById(
    "queue"
  ).innerText = `Queue size: ${frameQueue.length}`;
  // I arbitrarily added 1 because otherwise the queue kept growing
  return fps + 1;
}

document.getElementById("prompt").addEventListener("keydown", function (event) {
  if (event.key === "Enter") {
    document.getElementById("send").click();
  }
});

document.addEventListener("DOMContentLoaded", async () => {
  const deviceId = await selectVideoDevice();
  startVideoStream(deviceId);
});
