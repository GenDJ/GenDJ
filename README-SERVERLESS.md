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

- A RunPod account with API access.
- An AWS account with credentials configured locally (e.g., via `aws configure`).
- AWS CLI installed locally.
- Docker Hub account and an Access Token.
- Python 3 and pip installed locally.
- Git repository hosting your GenDJ code (e.g., GitHub).

### Building the Docker Image (AWS CodeBuild)

This project uses AWS CodeBuild with GPU support to build the necessary Docker image, as building directly within standard RunPod pods is currently restricted.

1.  **Clone the Repository (if you haven't already):**
    ```bash
    git clone https://github.com/GenDJ/GenDJ.git # Or your fork
    cd GenDJ
    ```

2.  **Install AWS Setup Script Dependencies:**
    ```bash
    pip install -r requirements-aws.txt
    ```

3.  **Configure AWS Build Environment:**
    *   Copy the example environment file:
        ```bash
        cp .env.aws-setup.example .env.aws-setup
        ```
    *   **Edit `.env.aws-setup`** and fill in all required values:
        *   `AWS_REGION`: Your desired AWS region.
        *   `AWS_PROFILE` (Optional): Your AWS CLI profile name.
        *   `DOCKERHUB_USERNAME`: Your Docker Hub username.
        *   `DOCKERHUB_PASSWORD`: Your Docker Hub **Access Token** (recommended).
        *   `DOCKERHUB_SECRET_NAME`: A name for the secret in AWS Secrets Manager.
        *   `CODEBUILD_PROJECT_NAME`: A name for the CodeBuild project.
        *   `CODEBUILD_SERVICE_ROLE_NAME`: A name for the IAM role.
        *   `SOURCE_REPO_URL`: The HTTPS or SSH URL of your Git repository.
        *   `SOURCE_REPO_TYPE`: `GITHUB`, `CODECOMMIT`, `BITBUCKET`, etc.
        *   `GPU_COMPUTE_TYPE`: AWS CodeBuild GPU instance type (e.g., `BUILD_GENERAL1_SMALL`). Verify availability in your region via AWS docs or console.
        *   `CODEBUILD_IMAGE`: An appropriate GPU-enabled CodeBuild image (e.g., `aws/codebuild/standard:7.0-gpu`). Verify availability.
        *   `IMAGE_REPO_NAME`: Your full Docker image name (e.g., `yourusername/gendj-serverless`).
        *   `IMAGE_TAG`: The tag for your Docker image (e.g., `latest` or `0.4.0`).

4.  **Run the AWS Setup Script:**
    *   This script creates the necessary AWS resources (Secrets Manager secret, IAM role, CodeBuild project).
    ```bash
    python setup_codebuild.py
    # Or: python setup_codebuild.py --env-file .env.aws-setup
    ```
    *   Follow any manual steps printed by the script (e.g., authorizing GitHub connection in the AWS console).

5.  **Trigger the First Build:**
    *   Go to the AWS Console -> CodeBuild -> Select your project.
    *   Click "Start build".
    *   CodeBuild will now execute the steps in `buildspec.yml`.
    *   Monitor the build logs.

6.  **(Build Triggering)** Builds for this project must be started manually via the AWS Console or AWS CLI. Automatic triggers (e.g., webhooks on code push) have not been configured by the setup script.

### Creating a RunPod Serverless Endpoint

1.  Log in to your RunPod account at https://runpod.io.
2.  Go to the Serverless section -> My Endpoints.
3.  Click "New Endpoint".
4.  Select "Custom" template.
5.  Enter the **Docker image URL** built and pushed by CodeBuild (e.g., `yourusername/gendj-serverless:latest`, using the name and tag from your `.env.aws-setup`).
6.  Set the following configuration:
    *   Worker Memory: 24 GB (Adjust based on testing)
    *   GPU: NVIDIA RTX A5000 (or similar, depending on model needs)
    *   Idle Timeout: 5 minutes (or as desired)
    *   Max Workers: As needed for your scale
    *   Min Workers: 0 for on-demand, or 1 for always ready
    *   Advanced Configuration:
        *   **Port mapping: `8888:8888/tcp` (Crucial for WebSocket access)**
7.  Create the endpoint.

## Using the Serverless Endpoint

### Client Examples

Two Python client examples are provided:

*   **`client-example.py`:** A basic example showing how to start a job, get the WebSocket URL, connect, send a test image, and receive the result.
*   **`test_frontend_serverless.py`:** Starts a job, gets the WebSocket URL, and then serves the local `fe/` directory via HTTP. It provides the dynamic WebSocket URL to the frontend JavaScript via a `/config` endpoint. This allows testing your local web frontend against the live serverless backend.

**To use `test_frontend_serverless.py`:**

1.  Create an environment file (e.g., `.env.frontend-test`):
    ```dotenv
    RUNPOD_API_KEY=your_runpod_api_key_here
    RUNPOD_ENDPOINT_ID=your_runpod_endpoint_id_here
    LOCAL_SERVER_PORT=8000
    ```
2.  Install dependencies: `pip install requests python-dotenv`
3.  Modify `fe/main.js` to fetch the WebSocket URL from `/config` (see example code within `test_frontend_serverless.py` comments or previous conversation history).
4.  Run the script: `python test_frontend_serverless.py`
5.  Open `http://localhost:8000` in your browser.

### Integration with Your Applications

To integrate GenDJ serverless with your own applications:

1.  Use the RunPod API (e.g., via `requests` in Python) to start a job on your endpoint ID.
2.  Poll the job status endpoint (`/status/{job_id}`) until the status is `IN_PROGRESS` and the `progress` field contains the `service_url`.
3.  Connect to the provided WebSocket `service_url`.
4.  Send frames (JPEG image data) to process.
5.  Receive processed frames (JPEG image data) in real-time.

## Important Notes

- Serverless jobs have a default timeout defined in `runpod.yaml` (e.g., 3600 seconds / 1 hour).
- You are billed by RunPod for the time the serverless worker is active.
- The WebSocket URL obtained via the RunPod API is specific to each job instance. 