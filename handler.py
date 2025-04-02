import runpod
from runpod import RunPodLogger
import os
import time
import threading
import subprocess
import signal
import socket

# --- Dynamic Logging Setup ---
_IS_RUNPOD_ENV = bool(os.environ.get('RUNPOD_POD_ID'))
_rp_logger = RunPodLogger() if _IS_RUNPOD_ENV else None

def log_info(message):
    print(message)
    if _rp_logger: _rp_logger.info(message)

def log_error(message):
    print(f"ERROR: {message}") # Add ERROR prefix for clarity in print
    if _rp_logger: _rp_logger.error(message)

def log_warning(message):
    print(f"WARNING: {message}") # Add WARNING prefix
    if _rp_logger: _rp_logger.warn(message) # Note: RunPodLogger uses warn, not warning

def log_critical(message):
    print(f"CRITICAL: {message}") # Add CRITICAL prefix
    if _rp_logger: _rp_logger.fatal(message) # Note: RunPodLogger uses fatal for critical

def log_debug(message):
    # Optional: Only print debug if not in RunPod or if specifically enabled?
    # For now, print always if called.
    print(f"DEBUG: {message}") # Add DEBUG prefix
    if _rp_logger: _rp_logger.debug(message)
# --- End Dynamic Logging Setup ---

# Constants
SERVICE_PORT = 8888  # WebSocket port to expose
TIMEOUT_SECONDS = 3600  # 1 hour timeout for the service

log_info("--- handler.py: Script started ---") # Use new log function

class GenDJService:
    def __init__(self):
        log_info("--- GenDJService: Initializing instance ---") # Use new log function
        self.process = None
        self.stop_event = threading.Event()
        
    def start(self):
        log_info("--- GenDJService.start: Attempting to start service ---") # Use new log function
        # Start the GenDJ service
        gendj_dir = "/workspace/GenDJ"
        cmd = ["bash", "./run_containerized.sh"]
        log_info(f"--- GenDJService.start: Starting GenDJ service in {gendj_dir} with command: {' '.join(cmd)} ---") # Use new log function
        try:
            self.process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=gendj_dir # Set the working directory
            )
            log_info(f"--- GenDJService.start: Subprocess launched with PID: {self.process.pid if self.process else 'None'} ---") # Use new log function
        except Exception as e:
            log_error(f"--- GenDJService.start: ERROR launching subprocess: {e} ---") # Use new log function
            return False
        
        # Read output in a separate thread
        log_info("--- GenDJService.start: Starting process monitor thread ---") # Use new log function
        threading.Thread(target=self._monitor_process, daemon=True).start()
        
        # Wait for the service to start
        log_info("--- GenDJService.start: Waiting for service port to open... ---") # Use new log function
        if not self._wait_for_service():
            log_error("--- GenDJService.start: Failed waiting for service port ---") # Use new log function
            return False
        
        log_info("--- GenDJService.start: Service started successfully ---") # Use new log function
        return True
        
    def _monitor_process(self):
        log_info("--- GenDJService._monitor_process: Starting to monitor stdout/stderr ---") # Use new log function
        try:
            for line in self.process.stdout:
                log_info(f"[GenDJ Process]: {line.strip()}") # Use new log function
        except Exception as e:
            log_error(f"--- GenDJService._monitor_process: Error reading process output: {e} ---") # Use new log function
            
        if self.process and self.process.poll() is not None:
            log_info(f"--- GenDJService._monitor_process: GenDJ process exited with code {self.process.returncode} ---") # Use new log function
        else:
             log_info("--- GenDJService._monitor_process: Monitor thread finished, process might still be running? ---") # Use new log function
            
    def _wait_for_service(self):
        log_info(f"--- GenDJService._wait_for_service: Checking for service on 127.0.0.1:{SERVICE_PORT} ---") # Use new log function
        start_time = time.time()
        while time.time() - start_time < 60:  # Wait up to 60 seconds
            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1) # Don't wait too long for connect
                result = sock.connect_ex(('127.0.0.1', SERVICE_PORT))
                if result == 0:
                    log_info(f"--- GenDJService._wait_for_service: Service is running on port {SERVICE_PORT} ---") # Use new log function
                    return True
            except socket.error as e:
                # Ignore connection errors like refused, reset, etc.
                # log_debug(f"--- GenDJService._wait_for_service: Socket error: {e} ---") # Optional: use log_debug if needed
                pass 
            finally:
                 if sock: sock.close()
                 
            time.sleep(1)
            
        log_error(f"--- GenDJService._wait_for_service: Timed out waiting for service on port {SERVICE_PORT} ---") # Use new log function
        return False
        
    def stop(self):
        log_info("--- GenDJService.stop: Stopping service ---") # Use new log function
        """Stop the GenDJ service"""
        if self.process:
            log_info("Stopping GenDJ service...") # Use new log function
            try:
                self.process.send_signal(signal.SIGTERM)
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                log_warning("GenDJ service did not terminate gracefully, forcing...") # Use new log function
                self.process.kill()
                
            self.process = None
            

log_info("--- handler.py: Initializing GenDJService ---") # Use new log function
gendj_service = GenDJService()

def handler(event):
    job_id = event.get("id", "unknown")
    log_info(f"--- handler: Function called for job {job_id} ---") # Use new log function
    log_info(f"--- handler: Event received: {event} ---") # Use new log function
    
    # Get public IP and port mapping
    log_info("--- handler: Getting public IP and port ---") # Use new log function
    public_ip = os.environ.get('RUNPOD_PUBLIC_IP')
    public_port = os.environ.get(f'RUNPOD_TCP_PORT_{SERVICE_PORT}')
    log_info(f"--- handler: Public IP = {public_ip}, Public Port = {public_port} ---") # Use new log function
    
    if not public_ip or not public_port:
        log_error("--- handler: ERROR - Missing RUNPOD_PUBLIC_IP or RUNPOD_TCP_PORT ---") # Use new log function
        return {"error": "Missing required environment variables for exposing the service"}
    
    # Start the GenDJ service
    log_info("--- handler: Calling gendj_service.start() ---") # Use new log function
    start_success = gendj_service.start()
    log_info(f"--- handler: gendj_service.start() returned: {start_success} ---") # Use new log function
    if not start_success:
        log_error("--- handler: ERROR - Failed to start GenDJ service ---") # Use new log function
        return {"error": "Failed to start GenDJ service"}
    
    # Send the connection info
    connection_info = {
        "status": "running",
        "service_url": f"ws://{public_ip}:{public_port}"
    }
    log_info(f"--- handler: Sending progress update with connection info: {connection_info} ---") # Use new log function
    try:
        runpod.serverless.progress_update(connection_info)
        log_info("--- handler: Progress update sent successfully ---") # Use new log function
    except Exception as e:
        log_error(f"--- handler: ERROR sending progress update: {e} ---") # Use new log function
        # Decide if we should exit here? Probably should stop the service.
        gendj_service.stop()
        return {"error": f"Failed to send progress update: {e}"}
    
    # Keep the job running
    start_time = time.time()
    log_info("--- handler: Entering main loop to keep job alive ---") # Use new log function
    try:
        while not gendj_service.stop_event.is_set() and (time.time() - start_time) < TIMEOUT_SECONDS:
            time.sleep(5)
            # Optional: Periodic heartbeat (can be noisy)
            # log_debug(f"--- handler: Sending heartbeat update (Uptime: {time.time() - start_time:.0f}s) ---") # Use new log function
            # runpod.serverless.progress_update({"status": "running", "uptime": time.time() - start_time})
    except Exception as e:
        log_error(f"--- handler: ERROR in main loop: {str(e)} ---") # Use new log function
    finally:
        # Stop the service
        log_info("--- handler: Exiting main loop, calling gendj_service.stop() ---") # Use new log function
        gendj_service.stop()
        log_info("--- handler: Service stopped ---") # Use new log function
    
    log_info(f"--- handler: Job {job_id} finishing ---") # Use new log function
    return {"status": "completed"}

log_info("--- handler.py: Calling runpod.serverless.start() ---") # Use new log function
try:
    runpod.serverless.start({"handler": handler})
    log_info("--- handler.py: runpod.serverless.start() finished (normally indicates stop/completion) ---") # Use new log function
except Exception as e:
    log_critical(f"--- handler.py: CRITICAL ERROR - Exception during runpod.serverless.start(): {e} ---") # Use new log function
    # Consider exiting if this fails, as the handler won't run
    exit(1)

log_info("--- handler.py: Script finished ---") # Use new log function 