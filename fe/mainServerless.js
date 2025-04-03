// Constants
// const WEBSOCKET_URL = "ws://localhost:8765"; // Removed: Will be fetched dynamically
// const PROMPT_ENDPOINT_URL_BASE = "http://localhost:5556/prompt/"; // Removed: Not used in this serverless setup
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
  // socket: null, // Replaced by ws below
  selectedDeviceId: null,
  isStreaming: false,
  isRendering: false,
  isRenderSmooth: false,
  podId: null, // Add podId to state
  websocketUrl: null, // Add websocketUrl to state
  settingsApiUrlBase: null, // Add settingsApiUrlBase to state
};

// Global WebSocket variable
let ws;

// --- URL Helper Functions (copied from example) ---
const IS_WARP_LOCAL = false; // Assume false for serverless deployment test

const buildWebsocketUrlFromPodId = (podId) => {
  if (IS_WARP_LOCAL) {
    return `ws://localhost:8765`;
  } else {
    // Use port 8766 as configured
    return `wss://${podId}-8766.proxy.runpod.net`;
  }
};

const buildSettingsApiUrlFromPodId = (podId, path) => {
   if (IS_WARP_LOCAL) {
    // Assuming settings API runs on 5556 locally if needed
    return `http://localhost:5556${path}`;
  } else {
    // Use port 5556 as configured
    return `https://${podId}-5556.proxy.runpod.net${path}`;
  }
};

// --- End URL Helper Functions ---

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
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Event Listeners
document
  .getElementById("toggleStreaming")
  .addEventListener("click", handleToggleStreamingButton);
document
  .getElementById("toggleRenderSmooth")
  .addEventListener("click", handleToggleRenderSmoothButton);

// Remove or comment out prompt-related listeners as they won't work with current handler
document.getElementById("send").style.display = 'none'; // Hide the send button
// document.getElementById("send").addEventListener("click", sendPrompt);
// document.getElementById("prompt").addEventListener("keydown", function (event) {
//   if (event.key === "Enter") {
//     sendPrompt();
//     event.preventDefault();
//   }
// });
// document.getElementById("postText").addEventListener("keydown", function (event) {
//   if (event.key === "Enter") {
//     sendPrompt();
//     event.preventDefault();
//   }
// });

document.addEventListener("DOMContentLoaded", async () => {
  // --- Hide non-functional elements ---
  document.getElementById("promptLibrary").style.display = 'none';
  document.getElementById("prompt").style.display = 'none';
  document.getElementById("postText").style.display = 'none';
  document.getElementById("send").style.display = 'none';

  // --- Setup Listeners ---
  const deviceList = document.getElementById("deviceList");
  deviceList.addEventListener("change", handleDeviceChange);
  document.getElementById("toggleStreaming").addEventListener("click", handleToggleStreamingButton);
  document.getElementById("toggleRenderSmooth").addEventListener("click", handleToggleRenderSmoothButton);
  const toggleDiagnostics = document.getElementById("toggleDiagnostics");
  const positionBtn = document.getElementById("position");
  const feedContainer = document.getElementById("feedContainer");
  const diagnostics = document.getElementById("diagnostics");
  toggleDiagnostics.addEventListener("click", () => { if (diagnostics.style.display === "none") { diagnostics.style.display = "block"; toggleDiagnostics.textContent = "Hide Options"; } else { diagnostics.style.display = "none"; toggleDiagnostics.textContent = "Show Options"; } });
  positionBtn.addEventListener("click", () => { if (feedContainer.classList.contains("horizontal")) { feedContainer.classList.remove("horizontal"); } else { feedContainer.classList.add("horizontal"); } });
  const frameDrop = document.getElementById("frameDrop");
  frameDrop.addEventListener("change", function () { dropEvery = frameDrop.value; console.log("dropEvery set to:", dropEvery); });


  // --- Fetch Config and Set URLs ---
  try {
      console.log("Fetching config from local server...");
      const response = await fetch('/config');
      if (!response.ok) {
          throw new Error(`HTTP error fetching config! Status: ${response.status}`);
      }
      const config = await response.json();
      const fetchedPodId = config.podId;

      if (!fetchedPodId) {
          throw new Error("Received empty podId from config.");
      }

      stateRofl.podId = fetchedPodId;
      stateRofl.websocketUrl = buildWebsocketUrlFromPodId(fetchedPodId);
      stateRofl.settingsApiUrlBase = `https://${fetchedPodId}-5556.proxy.runpod.net`; // Base URL for settings

      console.log("Config fetched successfully:");
      console.log("  podId:", stateRofl.podId);
      console.log("  websocketUrl:", stateRofl.websocketUrl);
      console.log("  settingsApiUrlBase:", stateRofl.settingsApiUrlBase);
      
      // Now safe to initialize webcam etc. that might depend on URLs
      await requestAndPopulateWebcam();

  } catch (error) {
      console.error('Failed to fetch config or set URLs:', error);
      alert(`Failed to get configuration from test server: ${error.message}. Cannot connect to RunPod.`);
      // Optionally disable start button etc.
      document.getElementById("toggleStreaming").disabled = true; 
  }
  // --- End Fetch Config ---
});

// Function Definitions

// Function to populate device list and select default
async function populateAndSelectDevice() {
    console.log("Populating device list after permission grant...");
    const devices = await getVideoDevices();
    const deviceList = document.getElementById("deviceList");
    deviceList.innerHTML = ""; // Clear previous options

    if (devices.length === 0) {
        console.error("No video input devices found even after permission grant!");
        alert("No webcams found. Please ensure a camera is connected and enabled.");
        stateRofl.selectedDeviceId = null;
        return false; // Indicate failure
    }

    devices.forEach((device, index) => {
        const option = document.createElement("option");
        option.value = device.deviceId; 
        option.textContent = device.label || `Camera ${index + 1}`;
        if (!device.deviceId) {
             console.warn("Device found but has empty deviceId:", device);
        }
        deviceList.appendChild(option);
    });

    // Try setting the state if it wasn't already captured from the track
    if (!stateRofl.selectedDeviceId && devices.length > 0) {
        stateRofl.selectedDeviceId = devices[0].deviceId;
        console.log("Set selectedDeviceId during populateAndSelectDevice (was previously null):", stateRofl.selectedDeviceId);
    } 
    // Ensure dropdown reflects the currently stored selectedDeviceId
    if(stateRofl.selectedDeviceId) {
         deviceList.value = stateRofl.selectedDeviceId;
    }

    console.log("Available devices (in populateAndSelectDevice):", devices);
    console.log("Selected device ID (in populateAndSelectDevice):", stateRofl.selectedDeviceId);
    
    return true; // Indicate success
}

// --- Modify the handleDeviceChange logic slightly ---
// It might be better to handle this within DOMContentLoaded or ensure only one listener exists
async function handleDeviceChange() {
    stateRofl.selectedDeviceId = this.value; 
    console.log("User selected device ID:", stateRofl.selectedDeviceId);
    if (stateRofl.isStreaming || stateRofl.stream) { 
        console.log("Device changed, restarting video stream...");
        await startVideoStream(stateRofl.selectedDeviceId); 
    }
}

// Function to initialize WebSocket connection dynamically
async function initializeWebSocket() {
    // Close existing connection if open
    if (ws && ws.readyState === WebSocket.OPEN) {
        console.log("Closing existing WebSocket connection before reconnecting.");
        ws.close();
    }
    
    if (!stateRofl.websocketUrl) {
        console.error("WebSocket URL not set in state. Cannot initialize.");
        alert("Cannot connect: WebSocket URL not configured.");
        setStreamingStatus(false);
        return; 
    }

    console.log('Connecting WebSocket to RunPod Serverless:', stateRofl.websocketUrl);
    ws = new WebSocket(stateRofl.websocketUrl); // Use URL from state

    ws.onopen = () => {
        console.log('WebSocket connection opened to RunPod service.');
        if(stateRofl.stream && stateRofl.isStreaming) sendFrames(); // Start sending if stream exists and flag is set
    };

    ws.onmessage = (event) => {
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

     ws.onerror = (error) => {
         console.error('WebSocket Error:', error);
         alert('WebSocket connection error. Check console.');
         setStreamingStatus(false);
     };

     ws.onclose = (event) => {
         console.log('WebSocket connection closed.', event.code, event.reason);
         setStreamingStatus(false);
         ws = null;
     };
}

function handleToggleStreamingButton() {
  const button = document.getElementById('toggleStreaming');
  if (!stateRofl.isStreaming) {
    if (!stateRofl.selectedDeviceId) {
        alert("No camera selected or available. Cannot start streaming.");
        return; 
    }
    console.log("Attempting to start streaming with device:", stateRofl.selectedDeviceId);
    // Set state BEFORE async calls
    setStreamingStatus(true);
    // Start video, which includes WebSocket init if needed
    startVideoStream(stateRofl.selectedDeviceId); 
  } else {
    console.log("Stopping streaming...");
    // Set state BEFORE async calls
    setStreamingStatus(false); 
    if (ws) {
      ws.close(); 
      ws = null;
    }
    stopCurrentStream();
  }
}

function handleToggleRenderSmoothButton() {
  const button = document.getElementById('toggleRenderSmooth');
  if (!stateRofl.isRenderSmooth) {
    stateRofl.isRenderSmooth = true;
    stateRofl.selectedRender = renderSmooth;
    button.textContent = "Turn Smooth Rendering Off";
  } else {
    stateRofl.isRenderSmooth = false;
    stateRofl.selectedRender = renderFlash;
    button.textContent = "Turn Smooth Rendering On";
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
  deviceList.innerHTML = ""; // Clear previous options

  if (devices.length === 0) {
      console.error("No video input devices found!");
      // Optionally display a message to the user in the UI
      alert("No webcams found. Please ensure a camera is connected and enabled.");
      stateRofl.selectedDeviceId = null; // Explicitly set to null
      return; // Exit if no devices
  }

  devices.forEach((device, index) => {
    const option = document.createElement("option");
    option.value = device.deviceId;
    option.textContent = device.label || `Camera ${index + 1}`;
    deviceList.appendChild(option);
  });

  // Set the default selected device ID to the first one found
  stateRofl.selectedDeviceId = devices[0].deviceId; 
  deviceList.value = stateRofl.selectedDeviceId; // Ensure dropdown reflects selection

  console.log("Available devices:", devices);
  console.log("Initial selected device ID:", stateRofl.selectedDeviceId);

  deviceList.addEventListener("change", async () => {
    stateRofl.selectedDeviceId = deviceList.value;
    console.log("User selected device ID:", stateRofl.selectedDeviceId);
    // No need to stop/start stream here anymore, handleToggleStreamingButton will do it
    // Or, if you want live switching without stop/start button:
    if (stateRofl.isStreaming || stateRofl.stream) { // If currently streaming or stream exists
        console.log("Device changed, restarting video stream...");
        await startVideoStream(stateRofl.selectedDeviceId); 
    }
  });
}

async function startVideoStream(deviceId) {
  console.log("startVideoStream called for device:", deviceId);
  if (!deviceId) {
      console.error("startVideoStream called with no deviceId. Aborting.");
      alert("No camera selected or found. Cannot start video stream.");
      setStreamingStatus(false); 
      return; 
  }

  stopCurrentStream();
  await sleep(100);
  try {
    console.log(`Attempting getUserMedia with constraints:`, { video: { deviceId: { exact: deviceId }, width: { ideal: FRAME_WIDTH }, height: { ideal: FRAME_HEIGHT } } });
    stateRofl.stream = await navigator.mediaDevices.getUserMedia({
      video: {
        deviceId: { exact: deviceId },
        width: { ideal: FRAME_WIDTH },
        height: { ideal: FRAME_HEIGHT },
      },
    });
    console.log("getUserMedia successful, stream acquired.");

    if (stateRofl.isStreaming) {
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            console.log("WebSocket not ready, initializing...");
            await initializeWebSocket(); // Connect if not already connected
        } else if (ws && ws.readyState === WebSocket.OPEN) {
             console.log("WebSocket ready, starting frame sending...");
             sendFrames(); // Start sending frames immediately if WS is already open
        }
    }
    
    if (!stateRofl.isRendering) { 
        renderFrames(); 
    }

  } catch (error) {
    console.error("Error accessing webcam:", error);
    if (error.name === "OverconstrainedError") {
         alert(`Could not access camera: The requested settings (Device ID: ${deviceId}, Resolution: ${FRAME_WIDTH}x${FRAME_HEIGHT}) are not supported by the selected camera. Try different settings or camera. Error: ${error.message}`);
    } else if (error.name === "NotAllowedError") {
         alert(`Could not access camera: Permission denied. Please grant camera access in your browser settings.`);
    } else if (error.name === "NotFoundError") {
         alert(`Could not access camera: No camera found matching ID ${deviceId}. It might be disconnected or unavailable.`);
    } else {
        alert(`Error accessing webcam: ${error.name} - ${error.message}`);
    }
    setStreamingStatus(false);
  }
}

function stopCurrentStream() {
  if (stateRofl.stream) {
    console.log("Stopping existing video stream tracks.");
    stateRofl.stream.getTracks().forEach((track) => track.stop());
    stateRofl.stream = null;
  }
}

function sendFrames() {
  if (stateRofl.sendingFrames) return;
  stateRofl.sendingFrames = true;
  console.log("sendFrames initiated");

  const videoTrack = stateRofl.stream?.getVideoTracks()[0];
  if (!videoTrack) {
      console.error("No video track available to capture frames.");
      stateRofl.sendingFrames = false;
      setStreamingStatus(false);
      return;
  }
  
  if (typeof ImageCapture === 'undefined') {
      console.error("ImageCapture API is not supported in this browser.");
      alert("ImageCapture API not supported. Webcam feed cannot be processed.");
      stateRofl.sendingFrames = false;
      setStreamingStatus(false);
      return;
  }
  const imageCapture = new ImageCapture(videoTrack);
  let frameCounter = 0;
  let lastFrameTime = performance.now(); 
  const frameDuration = 1000 / FRAME_RATE;

  const sendFrameLoop = async () => {
    if (!stateRofl.isStreaming || !ws || ws.readyState !== WebSocket.OPEN) {
      console.log("Stopping sendFrameLoop (streaming off or WS closed).");
      stateRofl.sendingFrames = false; 
      return; 
    }

    const currentTime = performance.now();
    if (currentTime - lastFrameTime < frameDuration) {
      requestAnimationFrame(sendFrameLoop);
      return;
    }
    lastFrameTime = currentTime; 

    try {
      if (videoTrack.readyState !== "live") {
        // Attempt to stop gracefully if track ends
        console.warn("Video track is not live, stopping send loop.");
        stateRofl.sendingFrames = false;
        setStreamingStatus(false); 
        return; 
      }

      const frame = await imageCapture.grabFrame();

      const tempCanvas = document.createElement('canvas');
      const tempCtx = tempCanvas.getContext('2d');
      tempCanvas.width = FRAME_WIDTH;
      tempCanvas.height = FRAME_HEIGHT;

      const scaleWidth = FRAME_WIDTH / frame.width;
      const scaleHeight = FRAME_HEIGHT / frame.height;
      const scale = Math.min(scaleWidth, scaleHeight);
      const scaledWidth = frame.width * scale;
      const scaledHeight = frame.height * scale;
      const dx = (FRAME_WIDTH - scaledWidth) / 2;
      const dy = (FRAME_HEIGHT - scaledHeight) / 2;

      croppedCtx.clearRect(0, 0, croppedCanvas.width, croppedCanvas.height);
      croppedCtx.drawImage(frame, dx, dy, scaledWidth, scaledHeight);

      tempCtx.clearRect(0, 0, tempCanvas.width, tempCanvas.height);
      tempCtx.drawImage(frame, dx, dy, scaledWidth, scaledHeight);

      tempCanvas.toBlob(
        (blob) => {
          if (blob && ws && ws.readyState === WebSocket.OPEN && dropFrameStrategies[dropEvery](frameCounter)) {
             ws.send(blob); 
          }
          frame.close(); 
          frameCounter++;
          requestAnimationFrame(sendFrameLoop); 
        },
        "image/jpeg",
        0.8 
      );
    } catch (error) {
      console.error("Error capturing/sending frame:", error);
      // Consider if certain errors should stop the loop
      if (error.name === 'DOMException' && error.message.includes('The ImageCapture is busy')) {
         console.warn('ImageCapture busy, skipping frame.'); // Just skip frame if busy
      } else if (error.message.includes('Video track is not live')) {
         console.warn('Video track ended, stopping send loop.');
         stateRofl.sendingFrames = false;
         setStreamingStatus(false);
         return; // Stop the loop
      }
      // Continue loop for potentially transient errors
      requestAnimationFrame(sendFrameLoop); 
    }
  };

  console.log("Kicking off sendFrameLoop");
  sendFrameLoop();
}

function renderFrames() {
  if (!stateRofl.isRendering) {
    stateRofl.isRendering = true;
    lastRenderTime = Date.now();
    stateRofl.selectedRender();
  }
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

// Helper function to update button text (example)
function setStreamingStatus(isStreaming) {
    const button = document.getElementById('toggleStreaming');
    if (button) {
        button.textContent = isStreaming ? "Stop" : "Start";
    }
    stateRofl.isStreaming = isStreaming;
    // Maybe reset frame sending flag if stopping
    if (!isStreaming) {
       stateRofl.sendingFrames = false;
    }
}

// Combined function for permission request and device population
async function requestAndPopulateWebcam() {
    console.log("Requesting initial webcam permissions...");
    try {
        // Get stream to trigger permission prompt
        const permissionStream = await navigator.mediaDevices.getUserMedia({ video: true });
        console.log("Initial permission granted or already present.");

        const videoTracks = permissionStream.getVideoTracks();
        if (videoTracks.length > 0) {
            const firstTrack = videoTracks[0];
            const settings = firstTrack.getSettings();
            stateRofl.selectedDeviceId = settings.deviceId;
            console.log(`Captured deviceId directly from initial stream track settings: '${stateRofl.selectedDeviceId}'`);
        } else {
            console.error("Permission granted, but no video tracks found on the initial stream.");
        }
        permissionStream.getTracks().forEach(track => track.stop());

        await populateAndSelectDevice(); // Populate dropdown
        // Ensure dropdown reflects the captured ID
        const deviceList = document.getElementById("deviceList");
        if (stateRofl.selectedDeviceId) {
             deviceList.value = stateRofl.selectedDeviceId;
        } else {
             console.warn("Could not re-select the captured device ID in the dropdown.");
        }

        if (stateRofl.selectedDeviceId) {
            console.log("Ready for user to start streaming with selected device.");
        } else {
             console.error("Failed to obtain a valid device ID after populate.");
             alert("Failed to obtain a valid camera ID. Try refreshing or checking browser settings.");
        }

    } catch (error) {
        console.error("Error requesting webcam permission or populating list:", error.name, error.message);
        if (error.name === "NotAllowedError") {
            alert("Webcam permission was denied. Please grant permission in browser settings and refresh the page.");
        } else {
            alert(`Could not initialize webcam: ${error.name} - ${error.message}`);
        }
    }
}

// Modify sendPrompt to use the dynamic settings API URL
function sendPrompt() {
  if (!stateRofl.settingsApiUrlBase) {
    console.error("Settings API URL base not set.");
    alert("Cannot send prompt: API URL not configured.");
    return;
  }
  const promptText = document.getElementById("prompt").value;
  const postText = document.getElementById("postText").value;
  const fullPrompt = `${promptText} ${postText}`.trim();
  const encodedPrompt = encodeURIComponent(fullPrompt);
  
  // Assuming primary prompt uses /prompt/ endpoint
  const endpoint = buildSettingsApiUrlFromPodId(stateRofl.podId, `/prompt/${encodedPrompt}`);
  console.log("Sending prompt to:", endpoint);

  fetch(endpoint, {
    method: 'POST'
  })
    .then(response => response.text()) // Use text() first to see raw response
    .then(data => {
      console.log('Prompt Response:', data);
      try {
        if (data) {
          const parsedData = JSON.parse(data); // Try parsing later
          if (parsedData?.safety === 'unsafe') {
             // Handle unsafe prompt if needed
             console.warn("Prompt flagged as unsafe by server.");
             alert("Prompt may contain unsafe content.");
          }
        }
      } catch (error) {
         console.error('Error parsing prompt response:', error, "Raw data:", data);
      }
    })
    .catch(error => {
      console.error('Error sending prompt:', error);
      alert(`Error sending prompt: ${error.message}`);
    });
}

// Update event listeners to call the modified sendPrompt
document.getElementById("send").addEventListener("click", sendPrompt);
document.getElementById("prompt").addEventListener("keydown", function (event) {
  if (event.key === "Enter" && !event.shiftKey) { // Allow shift+enter for newline
    sendPrompt();
    event.preventDefault();
  }
});
document.getElementById("postText").addEventListener("keydown", function (event) {
  if (event.key === "Enter") {
    sendPrompt();
    event.preventDefault();
  }
});
// Also update library selection to call sendPrompt
document.getElementById("promptLibrary").addEventListener("change", function(){
    const selectedValue = this.value;
    if (selectedValue) { // Don't send if they select the placeholder
        document.getElementById("prompt").value = selectedValue;
        sendPrompt();
    }
});
