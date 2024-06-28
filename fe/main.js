// Constants
const WEBSOCKET_URL = "ws://localhost:8765";
const PROMPT_ENDPOINT_URL_BASE = "http://localhost:5556/prompt/";
const croppedCanvas = document.getElementById("croppedCanvas");
const processedCanvas = document.getElementById("processedCanvas");
const croppedCtx = croppedCanvas.getContext("2d");
const processedCtx = processedCanvas.getContext("2d");
const FRAME_WIDTH = 512;
const FRAME_HEIGHT = 512;
const FRAME_RATE = 24;
let fps = 16;
// State
const stateRofl = {
  stream: null,
  socket: null,
  selectedDeviceId: null,
  isStreaming: false,
  isRendering: false,
  isRenderSmooth: false,
};

const renderFlash = () => {
  const now = Date.now();
  const fps = calculateFPS();
  const interval = fps > 0 ? 1000 / fps : 1000 / FRAME_RATE;
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
  requestAnimationFrame(stateRofl.selectedRender);
};

let lastRenderTime = Date.now();
let fadeDuration = 500; // duration of fade in milliseconds
let fadeStartTime = null;
let currentImg = null;
let nextImg = null;

const renderSmooth = () => {
  stateRofl.isRendering = true;

  const now = Date.now();
  const safeFps = Math.max(fps, 1);
  const interval = 1000 / safeFps; // interval

  if (
    frameQueue.length > 0 &&
    (now - lastRenderTime >= interval ||
      frameQueue.length > 8 ||
      (frameQueue.length > 0 && now - lastRenderTime >= 1000))
  ) {
    fadeStartTime = now;
    currentImg = nextImg;
    nextImg = frameQueue.shift();
    lastRenderTime = now;
  }

  if (currentImg && nextImg && fadeStartTime !== null) {
    let fadeElapsed = now - fadeStartTime;
    let fadeProgress = Math.min(fadeElapsed / fadeDuration, 1);

    // Clear the canvas
    processedCtx.clearRect(0, 0, processedCanvas.width, processedCanvas.height);

    // Draw the current image with fading out
    processedCtx.globalAlpha = 1;
    processedCtx.drawImage(
      currentImg,
      0,
      0,
      processedCanvas.width,
      processedCanvas.height
    );

    // Draw the next image with fading in
    processedCtx.globalAlpha = fadeProgress;
    processedCtx.drawImage(
      nextImg,
      0,
      0,
      processedCanvas.width,
      processedCanvas.height
    );

    // Reset globalAlpha to 1 for other drawing operations
    processedCtx.globalAlpha = 1;

    // Once the fade is complete, reset currentImg
    if (fadeProgress === 1) {
      currentImg = nextImg;
      nextImg = null;
      fadeStartTime = null;
    }
  } else if (currentImg && !nextImg) {
    // If there is no next image, continue displaying the current image
    processedCtx.globalAlpha = 1;
    processedCtx.drawImage(
      currentImg,
      0,
      0,
      processedCanvas.width,
      processedCanvas.height
    );
  }

  requestAnimationFrame(stateRofl.selectedRender);
};

stateRofl.selectedRender = renderFlash;
// Frame control variables
const frameQueue = [];
const frameTimestamps = [];
let dropEvery = "none";

const dropFrame = (n) => (frameCounter) => {
  return frameCounter === 0 || frameCounter === 1 || frameCounter % n !== 0;
};

const dropFrameStrategies = {
  none: () => true,
  2: dropFrame(2),
  3: dropFrame(3),
  4: dropFrame(4),
  5: dropFrame(5),
};

function sleep(ms) {
  new Promise((resolve) => setTimeout(resolve, ms));
}

// Event Listeners
document
  .getElementById("toggleStreaming")
  .addEventListener("click", handleToggleStreamingButton);
document
  .getElementById("toggleRenderSmooth")
  .addEventListener("click", handleToggleRenderSmoothButton);

document.getElementById("send").addEventListener("click", sendPrompt);
document.getElementById("prompt").addEventListener("keydown", function (event) {
  if (event.key === "Enter") {
    sendPrompt();
    event.preventDefault();
  }
});
document
  .getElementById("postText")
  .addEventListener("keydown", function (event) {
    if (event.key === "Enter") {
      sendPrompt();
      event.preventDefault();
    }
  });

document.addEventListener("DOMContentLoaded", async () => {
  document.getElementById("prompt").innerText =
    "a dj sunglasses disco colors vibrant digital illustration HDR talking";
  if (await hasWebcamPermissions()) {
    await initializeWebcam();
  } else {
    try {
      await requestWebcamPermissions();
      await initializeWebcam();
    } catch (error) {
      console.error("Webcam permissions are required to proceed.", error);
    }
  }

  const frameDrop = document.getElementById("frameDrop");
  frameDrop.addEventListener("change", function () {
    dropEvery = frameDrop.value;
    console.log("dropEvery set to:", dropEvery);
  });

  // New JavaScript for the added features
  const toggleDiagnostics = document.getElementById("toggleDiagnostics");
  const positionBtn = document.getElementById("position");
  const feedContainer = document.getElementById("feedContainer");
  const diagnostics = document.getElementById("diagnostics");
  const promptLibrary = document.getElementById("promptLibrary");
  const promptInput = document.getElementById("prompt");

  toggleDiagnostics.addEventListener("click", () => {
    if (diagnostics.style.display === "none") {
      diagnostics.style.display = "block";
      toggleDiagnostics.textContent = "Hide Options";
    } else {
      diagnostics.style.display = "none";
      toggleDiagnostics.textContent = "Show Options";
    }
  });

  positionBtn.addEventListener("click", () => {
    if (feedContainer.classList.contains("horizontal")) {
      feedContainer.classList.remove("horizontal");
    } else {
      feedContainer.classList.add("horizontal");
    }
  });

  promptLibrary.addEventListener("change", (event) => {
    promptInput.value = event.target.value;
  });
});

// Function Definitions

function handleToggleStreamingButton() {
  stateRofl.isStreaming = !stateRofl.isStreaming;
  this.textContent = stateRofl.isStreaming ? "Stop" : "Start";
}

function handleToggleRenderSmoothButton() {
  if (!stateRofl.isRenderSmooth) {
    stateRofl.isRenderSmooth = true;
    stateRofl.selectedRender = renderSmooth;
    this.textContent = "Turn Smooth Rendering Off";
  } else {
    stateRofl.isRenderSmooth = false;
    stateRofl.selectedRender = renderFlash;
    this.textContent = "Turn Smooth Rendering On";
  }
}

async function initializeWebcam() {
  await selectVideoDevice();
  await startVideoStream(stateRofl.selectedDeviceId);
}

async function hasWebcamPermissions() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
    stream.getTracks().forEach((track) => track.stop());
    return true;
  } catch (error) {
    return false;
  }
}

async function requestWebcamPermissions() {
  await navigator.mediaDevices.getUserMedia({ video: true });
}

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

  stateRofl.selectedDeviceId = devices.length > 0 ? devices[0].deviceId : null;

  if (stateRofl.selectedDeviceId) {
    console.log("Initial selected device ID:", stateRofl.selectedDeviceId);
  }

  deviceList.addEventListener("change", async () => {
    stateRofl.selectedDeviceId = deviceList.value;
    console.log("User selected device ID:", stateRofl.selectedDeviceId);
    if (stateRofl.stream) {
      stopCurrentStream(); // Stop the current stream
    }
    await startVideoStream(stateRofl.selectedDeviceId); // Start a new stream with the selected device ID
  });
}

async function startVideoStream(deviceId) {
  console.log("startVideoStream");
  await sleep(100);
  try {
    stateRofl.stream = await navigator.mediaDevices.getUserMedia({
      video: {
        deviceId: { exact: deviceId },
        width: { ideal: FRAME_WIDTH },
        height: { ideal: FRAME_HEIGHT },
      },
    });

    if (!stateRofl.socket) {
      connectWebSocket();
    }

    renderFrames();
    sendFrames();
  } catch (error) {
    console.error("Error accessing webcam:", error);
  }
}

function stopCurrentStream() {
  if (stateRofl.stream) {
    stateRofl.stream.getTracks().forEach((track) => track.stop());
  }
}

function connectWebSocket() {
  stateRofl.socket = new WebSocket(WEBSOCKET_URL);

  stateRofl.socket.binaryType = "arraybuffer";

  stateRofl.socket.onopen = () => {
    console.log("WebSocket connection opened");
  };

  stateRofl.socket.onmessage = (event) => {
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

  stateRofl.socket.onclose = reconnectWebSocket;

  stateRofl.socket.onerror = (error) => {
    console.error("WebSocket error:", error);
  };
}

async function reconnectWebSocket() {
  console.log("WebSocket connection closed. Attempting to reconnect...");
  await sleep(100); // Wait before attempting to reconnect
  connectWebSocket();
}

function sendFrames() {
  console.log("sendFrames");

  const videoTrack = stateRofl.stream.getVideoTracks()[0];
  const imageCapture = new ImageCapture(videoTrack);
  let frameCounter = 0;
  let lastFrameTime = 0;
  const frameDuration = 1000 / FRAME_RATE;

  const sendFrame = async (currentTime) => {
    if (currentTime - lastFrameTime < frameDuration) {
      requestAnimationFrame(sendFrame);
      return;
    }

    try {
      if (videoTrack.readyState !== "live") {
        throw new Error("Video track is not live");
      }

      const frame = await imageCapture.grabFrame();

      croppedCanvas.width = FRAME_WIDTH;
      croppedCanvas.height = FRAME_HEIGHT;

      const scaleWidth = FRAME_WIDTH / frame.width;
      const scaleHeight = FRAME_HEIGHT / frame.height;
      const scale = Math.min(scaleWidth, scaleHeight);

      const scaledWidth = frame.width * scale;
      const scaledHeight = frame.height * scale;

      const dx = (FRAME_WIDTH - scaledWidth) / 2;
      const dy = (FRAME_HEIGHT - scaledHeight) / 2;

      croppedCtx.clearRect(0, 0, FRAME_WIDTH, FRAME_HEIGHT);
      croppedCtx.drawImage(frame, dx, dy, scaledWidth, scaledHeight);

      croppedCanvas.toBlob(
        (blob) => {
          if (
            blob &&
            stateRofl.isStreaming &&
            stateRofl.socket &&
            stateRofl.socket.readyState === WebSocket.OPEN &&
            dropFrameStrategies[dropEvery](frameCounter)
          ) {
            blob.arrayBuffer().then((buffer) => {
              if (
                stateRofl.socket &&
                stateRofl.socket.readyState === WebSocket.OPEN
              ) {
                stateRofl.socket.send(buffer);
              }
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

  console.log("kicking off");
  sendFrame();
}

function renderFrames() {
  if (!stateRofl.isRendering) {
    stateRofl.isRendering = true;
    lastRenderTime = Date.now();

    stateRofl.selectedRender();
  }
}

function sendPrompt() {
  const promptText = document.getElementById("prompt").value;
  const postText = document.getElementById("postText").value;
  const encodedPrompt = encodeURIComponent(`${promptText + " " + postText}`);
  const endpoint = `${PROMPT_ENDPOINT_URL_BASE}${encodedPrompt}`;

  fetch(endpoint, {
    method: "POST",
  })
    .then((response) => response.text())
    .then((data) => console.log(data))
    .catch((error) => {
      console.error("Error:", error);
    });
}

function calculateFPS() {
  const now = Date.now();
  const cutoff = now - 1000;
  while (frameTimestamps.length > 0 && frameTimestamps[0] < cutoff) {
    frameTimestamps.shift();
  }
  fps = frameTimestamps.length;
  document.getElementById("fps").innerText = `FPS: ${fps}`;
  document.getElementById(
    "queue"
  ).innerText = `Queue size: ${frameQueue.length}`;
  return fps + 1;
}
