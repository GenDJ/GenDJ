#!/usr/bin/env python3
"""
RunPod Serverless Frontend Test Runner

Starts a RunPod serverless job, waits for the WebSocket URL,
and serves the local 'fe/' directory, providing the URL to the frontend.
"""

import os
import sys
import time
import requests
import argparse
import dotenv
import threading
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from functools import partial
from pathlib import Path

# Global variables to store connection info and job details
WORKER_ID = None
JOB_ID = None 
CONFIG = {}

class FrontendTestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Serve files from the 'fe' subdirectory
        fe_dir = Path(__file__).parent / 'fe'
        super().__init__(*args, directory=str(fe_dir), **kwargs)

    def do_GET(self):
        # Explicitly handle the root path to serve index-serverless.html
        if self.path == '/':
            file_path = Path(__file__).parent / 'fe' / 'index-serverless.html'
            if file_path.is_file():
                try:
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    with open(file_path, 'rb') as f:
                        self.wfile.write(f.read())
                except Exception as e:
                    print(f"Error serving index-serverless.html: {e}")
                    self.send_error(500, "Error reading serverless index file")
            else:
                self.send_error(404, "index-serverless.html not found")
            return # Explicitly return after handling
        elif self.path == '/config':
            if WORKER_ID:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                # Revert to providing just the podId (WORKER_ID)
                print(f"--- Providing config: {{'podId': WORKER_ID}} ---")
                response = json.dumps({'podId': WORKER_ID}).encode('utf-8')
                self.wfile.write(response)
            else:
                self.send_error(503, "Worker ID not available yet")
            return # Explicitly return after handling
        else:
            # Serve other files (like mainServerless.js) using the default handler
            super().do_GET()
            
    def do_POST(self):
        # Match the path format: /v1/warps/{job_id}/end
        path_parts = self.path.strip('/').split('/')
        
        if len(path_parts) == 4 and path_parts[0] == 'v1' and path_parts[1] == 'warps' and path_parts[3] == 'end':
            requested_job_id = path_parts[2]
            
            if not JOB_ID or not WORKER_ID or not CONFIG:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": "Job/Worker ID or Config not set server-side"}).encode('utf-8'))
                return

            # Compare requested job ID with the one this server manages
            if requested_job_id != JOB_ID:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": f"Requested job ID {requested_job_id} does not match current job {JOB_ID}"}).encode('utf-8'))
                return

            print(f"--- Received request to end job {JOB_ID} via {self.path} ---")
            cancel_url = f"https://api.runpod.ai/v2/{CONFIG['RUNPOD_ENDPOINT_ID']}/cancel/{JOB_ID}"
            headers = {"Authorization": f"Bearer {CONFIG['RUNPOD_API_KEY']}"}

            try:
                response = requests.post(cancel_url, headers=headers, timeout=15)
                response.raise_for_status()
                cancel_result = response.json() # Assuming Runpod returns JSON
                print(f"--- Job cancellation response: {cancel_result} ---")
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "message": f"Cancel request sent for job {JOB_ID}", "result": cancel_result}).encode('utf-8'))
            except requests.exceptions.RequestException as e:
                print(f"Error cancelling RunPod job: {e}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": f"Failed to send cancel request: {e}"}).encode('utf-8'))
        else:
            self.send_error(404, f"POST endpoint {self.path} not found")

def load_env(env_file):
    """Load environment variables from the specified file"""
    env_path = Path(env_file)
    if not env_path.exists():
        print(f"Error: Environment file '{env_path}' not found.")
        sys.exit(1)
    
    dotenv.load_dotenv(env_path)
    
    required_vars = ['RUNPOD_API_KEY', 'RUNPOD_ENDPOINT_ID', 'LOCAL_SERVER_PORT']
    config = {}
    missing_vars = []
    for var in required_vars:
        value = os.environ.get(var)
        if not value:
            missing_vars.append(var)
        else:
            config[var] = value
            
    if missing_vars:
        print(f"Error: Missing required environment variables in {env_path}: {', '.join(missing_vars)}")
        sys.exit(1)
        
    return config

def start_runpod_job(config):
    """Start a job on the RunPod serverless endpoint"""
    api_url = f"https://api.runpod.ai/v2/{config['RUNPOD_ENDPOINT_ID']}/run"
    headers = {
        "Authorization": f"Bearer {config['RUNPOD_API_KEY']}",
        "Content-Type": "application/json"
    }
    # Send a minimal non-empty input object to potentially satisfy Runpod validation
    payload = {"input": {"message": "Starting GenDJ Job via Test Runner"}} 
    
    print("Starting RunPod serverless job...")
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status() # Raise an exception for bad status codes
    except requests.exceptions.RequestException as e:
        print(f"Error starting RunPod job: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response body: {e.response.text}")
        return None
        
    result = response.json()
    job_id = result.get("id")
    
    if not job_id:
        print(f"Error: No job ID returned from RunPod API. Response: {result}")
        return None
        
    print(f"RunPod job started with ID: {job_id}")
    return job_id

def wait_for_worker(config, job_id):
    """Poll the job status until a worker ID is assigned."""
    global WORKER_ID, JOB_ID # Allow modifying globals
    JOB_ID = job_id # Store the job ID globally
    status_url = f"https://api.runpod.ai/v2/{config['RUNPOD_ENDPOINT_ID']}/status/{job_id}"
    headers = {"Authorization": f"Bearer {config['RUNPOD_API_KEY']}"}
    
    print(f"Waiting for worker assignment for job {job_id}...")
    max_attempts = 60 # Wait for up to 5 minutes (60 attempts * 5 seconds)
    attempt = 0
    
    while attempt < max_attempts:
        try:
            response = requests.get(status_url, headers=headers, timeout=10)
            response.raise_for_status()
            result = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error checking RunPod job status: {e}")
            time.sleep(5)
            attempt += 1
            continue
            
        status = result.get("status")
        worker_id_from_api = result.get("workerId")
        
        # Print the debug status line we added before
        print(f"--- DEBUG: Received Status Response (Attempt {attempt + 1}): {json.dumps(result)} ---")

        if status == "COMPLETED":
            print(f"Error: RunPod job {job_id} completed before a worker was assigned or fully started.")
            return False
        elif status == "FAILED":
            print(f"Error: RunPod job {job_id} failed: {result.get('error', 'Unknown error')}")
            return False
        elif worker_id_from_api:
            # Found the worker ID!
            print(f"\nWorker assigned: {worker_id_from_api}")
            WORKER_ID = worker_id_from_api
            return True # Success!
        else:
             print(f"Job {job_id} status: {status}. Waiting for worker assignment... (Attempt {attempt + 1}/{max_attempts})")
            
        time.sleep(5)
        attempt += 1
        
    print(f"Error: Timed out waiting for worker assignment for job {job_id}.")
    return False

def run_local_server(port):
    """Run the local HTTP server"""
    try:
        # Use partial to pass the directory to the handler if needed (older Python versions)
        # handler = partial(FrontendTestHandler, directory='fe') # Not needed with Python 3.7+ directory kwarg
        handler = FrontendTestHandler
        httpd = HTTPServer(("localhost", port), handler)
        print(f"\nServing frontend locally on http://localhost:{port}")
        print("Open this URL in your browser.")
        print("Press Ctrl+C to stop the server and the RunPod job.")
        httpd.serve_forever()
    except OSError as e:
        if e.errno == 98: # Address already in use
             print(f"\nError: Port {port} is already in use. Please choose a different port.")
        else:
             print(f"\nError starting local server: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nStopping local server...")
        httpd.server_close()

def main():
    global CONFIG, JOB_ID
    parser = argparse.ArgumentParser(description="RunPod Serverless Frontend Test Runner")
    parser.add_argument("--env-file", default=".env.frontend-test", help="Path to environment file")
    args = parser.parse_args()
    
    CONFIG = load_env(args.env_file)
    
    # Store the job_id returned by start_runpod_job
    current_job_id = start_runpod_job(CONFIG)
    if not current_job_id:
        sys.exit(1)
        
    print(f"You can monitor the job status here: https://www.runpod.io/console/serverless/jobs?jobId={current_job_id}")
    
    # Wait for the worker to be assigned, which also sets the global JOB_ID
    if not wait_for_worker(CONFIG, current_job_id):
        print("Failed to get worker assignment. Exiting.")
        # Optionally try to cancel the job here
        # cancel_url = f"https://api.runpod.ai/v2/{CONFIG['RUNPOD_ENDPOINT_ID']}/cancel/{current_job_id}"
        # headers = {"Authorization": f"Bearer {CONFIG['RUNPOD_API_KEY']}"}
        # requests.post(cancel_url, headers=headers)
        sys.exit(1)
        
    # Now WORKER_ID and JOB_ID should be set globally
    print(f"Worker ID: {WORKER_ID}")
    print(f"Job ID for cancellation: {JOB_ID}")

    # Start local server in a separate thread
    server_port = int(CONFIG['LOCAL_SERVER_PORT'])
    server_thread = threading.Thread(target=run_local_server, args=(server_port,), daemon=True)
    server_thread.start()

    # Keep the main thread alive until interrupted
    try:
        while server_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received in main thread.")
    finally:
        print("Exiting test runner.")
        # Note: This doesn't automatically stop the RunPod job.
        # You might want to add an API call here to cancel the job if desired.
        # cancel_url = f"https://api.runpod.ai/v2/{CONFIG['RUNPOD_ENDPOINT_ID']}/cancel/{current_job_id}"
        # requests.post(cancel_url, headers=headers)

if __name__ == "__main__":
    main() 