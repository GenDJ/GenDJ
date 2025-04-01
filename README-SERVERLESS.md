# GenDJ - RunPod Serverless Implementation

This guide explains how to deploy and use GenDJ as a RunPod serverless service.

## Overview

The GenDJ serverless implementation allows you to run the GenDJ service as a RunPod serverless endpoint. This provides:

- On-demand scaling
- Pay-per-use billing
- Persistent connections via WebSockets
- Simple integration with the RunPod API

## Deployment

### Prerequisites

- A RunPod account with API access
- Docker installed on your local machine
- RunPod API key

### Building the Docker Image

1. Clone this repository:
```bash
git clone https://github.com/GenDJ/GenDJ.git
cd GenDJ
```

2. Build the Docker image using docker-bake:
```bash
docker buildx bake serverless
```

3. Push the Docker image to your container registry:
```bash
docker push mrassisted/gendj-serverless:0.3.4
```

### Creating a RunPod Serverless Endpoint

1. Log in to your RunPod account at https://runpod.io
2. Go to the Serverless section
3. Click "New Endpoint"
4. Select "Custom" template
5. Enter the Docker image URL: `mrassisted/gendj-serverless:0.3.4`
6. Set the following configuration:
   - Worker Memory: 24 GB
   - GPU: NVIDIA RTX A5000 (or better)
   - Idle Timeout: 5 minutes
   - Max Workers: As needed for your scale
   - Min Workers: 0 for on-demand, or 1 for always ready
   - Advanced Configuration:
     - Port mapping: 8888:8888/tcp (crucial for WebSocket access)
7. Create the endpoint

## Using the Serverless Endpoint

### Client Example

A Python client example is provided in `client-example.py`. To use it:

1. Set your RunPod API key and endpoint ID as environment variables:
```bash
export RUNPOD_API_KEY="your-api-key"
export RUNPOD_ENDPOINT_ID="your-endpoint-id"
```

2. Install the required Python packages:
```bash
pip install requests websocket-client pillow
```

3. Run the client:
```bash
python client-example.py
```

This will:
- Start a GenDJ serverless instance
- Wait for the service to be ready
- Connect to the service via WebSocket
- Send a test image (if test_image.jpg exists)
- Receive and save the processed image

### Integration with Your Applications

To integrate GenDJ serverless with your own applications:

1. Start a job through the RunPod API
2. Monitor the job status for progress updates
3. Once the service is ready, connect to the provided WebSocket URL
4. Send frames to process and receive the processed results in real-time

The WebSocket protocol is the same as the standard GenDJ service:
- Send: JPEG image data
- Receive: JPEG processed image data

## Important Notes

- The service has a default timeout of 1 hour (3600 seconds)
- You will be billed for the entire time the service is running
- To stop the service, simply stop the job through the RunPod API
- The WebSocket URL is provided in the job progress updates 