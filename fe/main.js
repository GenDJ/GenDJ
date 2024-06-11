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

async function startVideoStream() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });

    const socket = new WebSocket("ws://localhost:8765");

    socket.binaryType = "arraybuffer";

    socket.onopen = () => {
      console.log("WebSocket connection opened");
      sendFrames(stream, socket);
    };

    console.log("doop1212");
    socket.onmessage = (event) => {
      console.log("socketmessage1212", event);
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
      const frame = await imageCapture.grabFrame();

      const cropSize = Math.min(frame.width, frame.height);
      const cropX = Math.max(0, (frame.width - cropSize) / 2);
      const cropY = Math.max(0, (frame.height - cropSize) / 2);

      croppedCanvas.width = cropSize;
      croppedCanvas.height = cropSize;

      croppedCtx.clearRect(0, 0, cropSize, cropSize);
      croppedCtx.drawImage(
        frame,
        cropX,
        cropY,
        cropSize,
        cropSize,
        0,
        0,
        cropSize,
        cropSize
      );

      croppedCanvas.toBlob(
        (blob) => {
          if (blob && isStreaming && socket.readyState === WebSocket.OPEN) {
            blob.arrayBuffer().then((buffer) => {
              socket.send(buffer);
            });
          }
          lastFrameTime = currentTime;
          requestAnimationFrame(sendFrame);
          frameCounter++;
        },
        "image/jpeg", .8
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

startVideoStream();
