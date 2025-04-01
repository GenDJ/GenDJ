import runpod
import os
import time
import threading
import subprocess
import signal
import socket

# Constants
SERVICE_PORT = 8888  # WebSocket port to expose
TIMEOUT_SECONDS = 3600  # 1 hour timeout for the service

class GenDJService:
    def __init__(self):
        self.process = None
        self.stop_event = threading.Event()
        
    def start(self):
        # Start the GenDJ service
        cmd = ["bash", "/workspace/GenDJ/run_containerized.sh"]
        self.process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Read output in a separate thread
        threading.Thread(target=self._monitor_process, daemon=True).start()
        
        # Wait for the service to start
        self._wait_for_service()
        
        return True
        
    def _monitor_process(self):
        """Monitor the GenDJ process and log its output"""
        for line in self.process.stdout:
            print(line.strip())
            
        if self.process.poll() is not None:
            print(f"GenDJ process exited with code {self.process.returncode}")
            
    def _wait_for_service(self):
        """Wait until the service port is open"""
        start_time = time.time()
        while time.time() - start_time < 60:  # Wait up to 60 seconds
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', SERVICE_PORT))
            sock.close()
            
            if result == 0:
                print(f"GenDJ service is running on port {SERVICE_PORT}")
                return True
                
            time.sleep(1)
            
        print(f"Timed out waiting for GenDJ service to start on port {SERVICE_PORT}")
        return False
        
    def stop(self):
        """Stop the GenDJ service"""
        if self.process:
            print("Stopping GenDJ service...")
            try:
                self.process.send_signal(signal.SIGTERM)
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                print("GenDJ service did not terminate gracefully, forcing...")
                self.process.kill()
                
            self.process = None
            

# Initialize the service
gendj_service = GenDJService()

def handler(event):
    """
    RunPod serverless handler
    """
    job_id = event.get("id", "unknown")
    print(f"Starting job {job_id}")
    
    # Get public IP and port mapping from environment variables
    public_ip = os.environ.get('RUNPOD_PUBLIC_IP')
    public_port = os.environ.get(f'RUNPOD_TCP_PORT_{SERVICE_PORT}')
    
    if not public_ip or not public_port:
        return {
            "error": "Missing required environment variables for exposing the service"
        }
    
    # Start the GenDJ service
    if not gendj_service.start():
        return {
            "error": "Failed to start GenDJ service"
        }
    
    # Send the connection info via progress update
    connection_info = {
        "status": "running",
        "service_url": f"ws://{public_ip}:{public_port}"
    }
    runpod.serverless.progress_update(connection_info)
    
    # Keep the job running until timeout or stop signal
    start_time = time.time()
    try:
        while not gendj_service.stop_event.is_set() and (time.time() - start_time) < TIMEOUT_SECONDS:
            time.sleep(5)
            # Send periodic heartbeat updates
            runpod.serverless.progress_update({"status": "running", "uptime": time.time() - start_time})
    except Exception as e:
        print(f"Error while running service: {str(e)}")
    finally:
        # Stop the service
        gendj_service.stop()
    
    return {"status": "completed"}

# Define the RunPod serverless handler
runpod.serverless.start({"handler": handler}) 