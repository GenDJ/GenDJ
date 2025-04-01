#!/usr/bin/env python3
import requests
import json
import time
import websocket
import os
import sys
import argparse
from PIL import Image
import io
import base64

# Configuration
RUNPOD_API_KEY = os.environ.get("RUNPOD_API_KEY", "")
RUNPOD_ENDPOINT_ID = os.environ.get("RUNPOD_ENDPOINT_ID", "")
RUNPOD_API_URL = f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/run"

def start_gendj_service():
    """Start a GenDJ service via RunPod serverless API"""
    if not RUNPOD_API_KEY or not RUNPOD_ENDPOINT_ID:
        print("Error: RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID must be set")
        sys.exit(1)
        
    headers = {
        "Authorization": f"Bearer {RUNPOD_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Empty payload - no specific inputs needed for starting the service
    payload = {
        "input": {}
    }
    
    print("Starting GenDJ service...")
    response = requests.post(RUNPOD_API_URL, headers=headers, json=payload)
    
    if response.status_code != 200:
        print(f"Error starting service: {response.text}")
        sys.exit(1)
        
    result = response.json()
    job_id = result.get("id")
    
    if not job_id:
        print("Error: No job ID returned")
        sys.exit(1)
        
    print(f"Service starting with job ID: {job_id}")
    return job_id

def wait_for_service_url(job_id):
    """Poll for service URL from job status updates"""
    status_url = f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/status/{job_id}"
    headers = {
        "Authorization": f"Bearer {RUNPOD_API_KEY}"
    }
    
    print("Waiting for service to start...")
    max_attempts = 30
    attempt = 0
    
    while attempt < max_attempts:
        response = requests.get(status_url, headers=headers)
        if response.status_code != 200:
            print(f"Error checking status: {response.text}")
            time.sleep(5)
            attempt += 1
            continue
            
        result = response.json()
        status = result.get("status")
        
        if status == "COMPLETED":
            print("Service job completed unexpectedly")
            sys.exit(1)
        elif status == "FAILED":
            print(f"Service job failed: {result.get('error')}")
            sys.exit(1)
        elif status == "IN_PROGRESS":
            # Check progress updates for service URL
            progress = result.get("progress")
            if progress and "service_url" in progress:
                service_url = progress.get("service_url")
                print(f"GenDJ service is ready at: {service_url}")
                return service_url
                
        print("Waiting for service to start...")
        time.sleep(5)
        attempt += 1
        
    print("Timed out waiting for service to start")
    sys.exit(1)

def connect_to_gendj_websocket(service_url):
    """Connect to GenDJ service via WebSocket"""
    print(f"Connecting to GenDJ service at {service_url}")
    
    # Create WebSocket connection
    ws = websocket.WebSocketApp(service_url,
                              on_open=on_open,
                              on_message=on_message,
                              on_error=on_error,
                              on_close=on_close)
    
    # Start WebSocket connection
    ws.run_forever()

def on_open(ws):
    """Called when WebSocket connection is opened"""
    print("WebSocket connection opened")
    
    # Here you would typically send your first frame to process
    # For demonstration purposes, we'll just send a simple test image
    try:
        # Load a test image and send it
        if os.path.exists("test_image.jpg"):
            with open("test_image.jpg", "rb") as f:
                image_data = f.read()
                ws.send(image_data)
                print("Sent test image for processing")
        else:
            print("No test image found. Create a test_image.jpg file to test.")
    except Exception as e:
        print(f"Error sending image: {str(e)}")

def on_message(ws, message):
    """Called when a message is received from the WebSocket"""
    try:
        # The response is a JPEG image
        image_data = message
        
        # Save the result
        output_filename = f"gendj_result_{int(time.time())}.jpg"
        with open(output_filename, "wb") as f:
            f.write(image_data)
            
        print(f"Received and saved processed image to {output_filename}")
        
        # You can continue sending more frames here if needed
    except Exception as e:
        print(f"Error processing message: {str(e)}")

def on_error(ws, error):
    """Called when a WebSocket error occurs"""
    print(f"WebSocket error: {str(error)}")

def on_close(ws, close_status_code, close_msg):
    """Called when WebSocket connection is closed"""
    print(f"WebSocket connection closed: {close_status_code} - {close_msg}")

def main():
    parser = argparse.ArgumentParser(description="GenDJ RunPod Serverless Client")
    parser.add_argument("--image", help="Path to image file to process")
    args = parser.parse_args()
    
    # Start the GenDJ service
    job_id = start_gendj_service()
    
    # Wait for the service URL
    service_url = wait_for_service_url(job_id)
    
    # Connect to the service
    connect_to_gendj_websocket(service_url)

if __name__ == "__main__":
    main() 