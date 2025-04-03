import runpod
from runpod import RunPodLogger
import os
import time
import threading
import subprocess
import signal
import socket
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- Health Check Server --- 
def run_health_server():
    class SimpleHealthCheckHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/readyz":
                self.send_response(200)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(b"OK")
            else:
                self.send_response(404)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Not Found")
        def log_message(self, format, *args):
            # Optional: Suppress HTTP server logs if too noisy
            # log_debug(f"HealthCheckServer: {self.address_string()} - {format % args}")
            pass 

    httpd = None
    try:
        port = 8080
        httpd = HTTPServer(("", port), SimpleHealthCheckHandler)
        log_info(f"--- Health check server starting on port {port} ---")
        httpd.serve_forever()
    except OSError as e:
        log_critical(f"--- CRITICAL: Health check server failed to bind to port {port}: {e} ---")
        # If the health server can't start, the worker likely won't become ready.
        # We might want to exit the main script here, depending on Runpod behavior.
        sys.exit(1) # Exit the whole process if health server fails
    except Exception as e:
        log_critical(f"--- CRITICAL: Health check server failed unexpectedly: {e} ---")
        sys.exit(1)
    finally:
        if httpd:
            httpd.server_close()
            log_info("--- Health check server stopped ---")
# --- End Health Check Server ---


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
SERVICE_PORT = 8766  # WebSocket port - MATCH FRONTEND EXPECTATION
HEALTH_CHECK_PORT = 8080 # Internal health check
SETTINGS_API_PORT = 5556 # Internal settings API
# TIMEOUT_SECONDS = 3600 removed, use worker timeout

log_info("--- handler.py: Script started (Direct Execution) ---") # Updated message

# --- Start Health Check Thread ---
log_info("--- handler.py: Starting health check server thread ---")
health_thread = threading.Thread(target=run_health_server, daemon=True)
health_thread.start()
# --- End Health Check Thread ---


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
        except FileNotFoundError:
            log_error(f"--- GenDJService.start: ERROR launching subprocess - FileNotFoundError. Is run_containerized.sh at {gendj_dir}? ---")
            return False
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
        if not self.process or not self.process.stdout:
            log_error("--- GenDJService._monitor_process: ERROR - Process or stdout not available.")
            return
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
        # Check the actual internal port the service runs on (should now be SERVICE_PORT)
        internal_service_port = SERVICE_PORT 
        log_info(f"--- GenDJService._wait_for_service: Checking for internal service on 127.0.0.1:{internal_service_port} ---") # Use new log function
        start_time = time.time()
        wait_timeout = 60 # seconds
        log_interval = 10 # seconds
        last_log_time = start_time
        
        while time.time() - start_time < wait_timeout:
            # Log progress periodically
            current_time = time.time()
            if current_time - last_log_time >= log_interval:
                 log_info(f"--- GenDJService._wait_for_service: Still waiting for internal port {internal_service_port}... ({int(current_time - start_time)}s elapsed) ---")
                 last_log_time = current_time

            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1) # Don't wait too long for connect
                result = sock.connect_ex(('127.0.0.1', internal_service_port)) # Check internal port
                if result == 0:
                    log_info(f"--- GenDJService._wait_for_service: Service is running on internal port {internal_service_port} ---") # Use new log function
                    return True
            except socket.error as e:
                # Optional: use log_debug if needed
                # log_debug(f"--- GenDJService._wait_for_service: Socket error: {e} ---") 
                pass 
            finally:
                 if sock: sock.close()
                 
            time.sleep(1)
            
        log_error(f"--- GenDJService._wait_for_service: Timed out waiting for internal service on port {internal_service_port} after {wait_timeout} seconds ---") # Use new log function
        return False
        
    def stop(self):
        log_info("--- GenDJService.stop: Stopping service ---") # Use new log function
        """Stop the GenDJ service"""
        if self.process:
            log_info("Stopping GenDJ service...") # Use new log function
            try:
                # Try SIGTERM first
                log_info(f"--- GenDJService.stop: Sending SIGTERM to PID {self.process.pid} ---")
                self.process.terminate() # More standard than SIGTERM directly
                try:
                   self.process.wait(timeout=10)
                   log_info(f"--- GenDJService.stop: Process {self.process.pid} terminated gracefully.")
                except subprocess.TimeoutExpired:
                    log_warning(f"--- GenDJService.stop: Process {self.process.pid} did not terminate after SIGTERM, sending SIGKILL... ---") # Use new log function
                    self.process.kill()
                    self.process.wait(timeout=5) # Wait briefly for kill
                    log_info(f"--- GenDJService.stop: Process {self.process.pid} killed.")
            except Exception as e:
                log_error(f"--- GenDJService.stop: Error stopping process {self.process.pid}: {e} ---")
                
            self.process = None
            log_info("--- GenDJService.stop: Service process stopped. ---")
        else:
            log_info("--- GenDJService.stop: No service process was running.")


log_info("--- handler.py: Initializing GenDJService ---") # Use new log function
gendj_service = GenDJService()
# --- Global Service Management (Consideration for later) ---
# SERVICE_STARTED = False 
# SERVICE_LOCK = threading.Lock()

def handler(event):
    # global SERVICE_STARTED
    job_id = event.get("id", "unknown")
    log_info(f"--- handler: Function called for job {job_id} ---") # Use new log function
    log_info(f"--- handler: Event received: {event} ---") # Use new log function
    
    # --- Check/Start Service Logic ---
    # Simplistic approach for now: Start service on first call
    # A more robust approach would use SERVICE_STARTED and SERVICE_LOCK
    # to ensure it only starts once and handles concurrent requests.
    if not gendj_service.process:
        log_info(f"--- handler (Job {job_id}): GenDJ service process not found, attempting to start... ---")
        
        # --- Get Environment Variables --- 
        public_ip = None
        public_port = None
        port_env_var = None # Initialize
        try:
            log_info("--- handler: Attempting to get environment variables... ---")
            public_ip = os.environ.get('RUNPOD_PUBLIC_IP')
            # Use direct string concatenation for port key just to be ultra-safe
            # Fetch the public port mapped to the *actual* service port (now 8766)
            port_env_var = 'RUNPOD_TCP_PORT_' + str(SERVICE_PORT) 
            public_port = os.environ.get(port_env_var)
            
            # Log fetched values immediately
            log_info(f"--- handler: Fetched Public IP = '{public_ip}' (Type: {type(public_ip)}) ---")
            log_info(f"--- handler: Fetched Public Port {SERVICE_PORT} = '{public_port}' (Type: {type(public_port)}) ---")

            if not public_ip or not public_port:
                log_error("--- handler: ERROR - Missing RUNPOD_PUBLIC_IP or specific RUNPOD_TCP_PORT ---")
                # Still return error, but after logging attempt
                return {"error": "Missing required environment variables for exposing the service"}
            
            log_info("--- handler: Environment variables obtained successfully. ---")

        except Exception as e:
            # Catch ANY exception during env var access/check
            log_critical(f"--- handler: CRITICAL ERROR accessing environment variables: {e} ---")
            log_critical(f"--- handler: Env Var Details: IP='{public_ip}', PortVar='{port_env_var}', PortVal='{public_port}' ---")
            # traceback.print_exc() # Consider adding if needed, might be noisy
            return {"error": f"Critical error accessing environment variables: {e}"} 
        # --- End Get Environment Variables ---

        # Start the GenDJ service
        log_info("--- handler: Calling gendj_service.start() ---")
        start_success = gendj_service.start()
        log_info(f"--- handler: gendj_service.start() returned: {start_success} ---") # Use new log function
        if not start_success:
            log_error("--- handler: ERROR - Failed to start GenDJ service ---") # Use new log function
            # Optional: Consider stopping the health check server thread if the main service fails?
            return {"error": "Failed to start GenDJ service"}
    else:
         log_info(f"--- handler (Job {job_id}): GenDJ service process already exists (PID: {gendj_service.process.pid}). ---")
         # Re-fetch IP/Port in case worker restarted or IP changed?
         public_ip = os.environ.get('RUNPOD_PUBLIC_IP')
         public_port = os.environ.get(f'RUNPOD_TCP_PORT_{SERVICE_PORT}')
         if not public_ip or not public_port:
             log_error("--- handler: ERROR - Missing RUNPOD_PUBLIC_IP or RUNPOD_TCP_PORT (on subsequent call) ---")
             return {"error": "Missing required environment variables for exposing the service"}

    # Send the connection info
    connection_info = {
        "status": "running",
        "service_url": f"ws://{public_ip}:{public_port}"
    }
    log_info(f"--- handler: Sending progress update with connection info: {connection_info} ---") # Use new log function
    try:
        # Pass the event object (job) and the dictionary using the 'progress' keyword argument
        runpod.serverless.progress_update(event, progress=connection_info)
        log_info("--- handler: Progress update sent successfully ---") # Use new log function
    except Exception as e:
        log_error(f"--- handler: ERROR sending progress update: {e} ---") # Use new log function
        # Decide if we should exit here? Probably should stop the service.
        gendj_service.stop()
        return {"error": f"Failed to send progress update: {e}"}
    
    # --- Restore Keep Alive Loop ---
    # Keep the job running as long as the worker is alive & health check passes.
    # The main GenDJ service runs in the background subprocess.
    log_info(f"--- handler: Job {job_id} is running, keeping worker alive... ---")
    # Use the stop event associated with the service to allow graceful shutdown if needed.
    # Also check the health thread, although if it dies the worker might get killed anyway.
    while not gendj_service.stop_event.is_set() and health_thread.is_alive():
        # Optional: Add a timeout here if you want the job to self-terminate
        # if time.time() - start_time > TIMEOUT_SECONDS: break 
        time.sleep(5) # Check every 5 seconds

    log_info(f"--- handler: Keep alive loop exited for Job {job_id}. ---")
    # The actual return value when the loop finishes might not matter much,
    # as the worker is likely being terminated by Runpod at this point.
    # The 'finally' block in __main__ will handle cleanup.
    return {"status": "Worker loop finished or stopped"}
    # --- End Restore Keep Alive Loop ---

    # --- Original Immediate Return (Commented out) ---
    # log_info(f"--- handler: Job {job_id} finished processing, returning progress. ---")
    # return connection_info # Return the info directly instead of looping
    # --- End Original Immediate Return ---

# --- RunPod Serverless Start --- 
if __name__ == "__main__":
    if not health_thread.is_alive():
        log_critical("--- CRITICAL: Health check thread failed to stay alive before starting serverless handler. Exiting. ---")
        sys.exit(1)
        
    log_info("--- handler.py: Calling runpod.serverless.start() ---") # Use new log function
    try:
        runpod.serverless.start({"handler": handler})
        # This part might not be reached if start() blocks indefinitely until killed
        log_info("--- handler.py: runpod.serverless.start() finished (normally indicates stop/completion) ---") # Use new log function
    except Exception as e:
        log_critical(f"--- handler.py: CRITICAL ERROR - Exception during runpod.serverless.start(): {e} ---") # Use new log function
        # Consider exiting if this fails, as the handler won't run
        # Optional: Attempt to stop the service? 
        # gendj_service.stop() 
        sys.exit(1)
    finally:
        # Cleanup code that runs when the script exits (e.g., SIGTERM received)
        log_info("--- handler.py: Script is exiting, attempting to stop GenDJ service... ---")
        gendj_service.stop() 
        log_info("--- handler.py: Script finished ---") # Use new log function
# --- End RunPod Serverless Start --- 