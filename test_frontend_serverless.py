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

# Global variable to store the WebSocket URL
WEBSOCKET_URL = None
CONFIG = {}

class FrontendTestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Serve files from the 'fe' subdirectory
        fe_dir = Path(__file__).parent / 'fe'
        super().__init__(*args, directory=str(fe_dir), **kwargs)

    def do_GET(self):
        if self.path == '/config':
            if WEBSOCKET_URL:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = json.dumps({'service_url': WEBSOCKET_URL}).encode('utf-8')
                self.wfile.write(response)
            else:
                self.send_error(503, "WebSocket URL not available yet")
        else:
            # Serve files from the 'fe' directory
            super().do_GET()

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
    payload = {"input": {}} # No specific input needed for GenDJ handler
    
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

def wait_for_service_url(config, job_id):
    """Poll the job status until the service URL is available"""
    global WEBSOCKET_URL
    status_url = f"https://api.runpod.ai/v2/{config['RUNPOD_ENDPOINT_ID']}/status/{job_id}"
    headers = {"Authorization": f"Bearer {config['RUNPOD_API_KEY']}"}
    
    print("Waiting for WebSocket URL from RunPod worker...")
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
        
        if status == "COMPLETED":
            print(f"Error: RunPod job {job_id} completed unexpectedly.")
            return None
        elif status == "FAILED":
            print(f"Error: RunPod job {job_id} failed: {result.get('error', 'Unknown error')}")
            return None
        elif status == "IN_PROGRESS":
            progress = result.get("progress")
            if isinstance(progress, dict) and "service_url" in progress:
                service_url = progress.get("service_url")
                print(f"\nWebSocket URL received: {service_url}")
                WEBSOCKET_URL = service_url
                return service_url
            else:
                print(f"Job {job_id} in progress, waiting for service_url... (Attempt {attempt + 1}/{max_attempts})")
        else:
             print(f"Job {job_id} status: {status}. Waiting... (Attempt {attempt + 1}/{max_attempts})")
            
        time.sleep(5)
        attempt += 1
        
    print(f"Error: Timed out waiting for WebSocket URL for job {job_id}.")
    return None

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
    global CONFIG
    parser = argparse.ArgumentParser(description="RunPod Serverless Frontend Test Runner")
    parser.add_argument("--env-file", default=".env.frontend-test", help="Path to environment file")
    args = parser.parse_args()
    
    CONFIG = load_env(args.env_file)
    
    job_id = start_runpod_job(CONFIG)
    if not job_id:
        sys.exit(1)
        
    print(f"You can monitor the job status here: https://www.runpod.io/console/serverless/jobs?jobId={job_id}")
    
    service_url = wait_for_service_url(CONFIG, job_id)
    if not service_url:
        # Optionally try to cancel the job here if needed
        print("Failed to get service URL. Exiting.")
        sys.exit(1)
        
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
        # cancel_url = f"https://api.runpod.ai/v2/{CONFIG['RUNPOD_ENDPOINT_ID']}/cancel/{job_id}"
        # requests.post(cancel_url, headers=headers)

if __name__ == "__main__":
    main() 