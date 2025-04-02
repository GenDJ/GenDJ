#!/bin/bash
set -ex # Exit on error, print commands

echo "--- start.sh: Starting script (Restored Version) ---"

echo "--- start.sh: Starting health check server in background... ---"
python /workspace/healthcheck/health_check_server.py &
HEALTH_PID=$!
echo "--- start.sh: Health check server background process started with PID: $HEALTH_PID ---"

# Short delay to allow health check server to potentially start/fail
echo "--- start.sh: Sleeping for 2s before starting handler... ---"
sleep 2 
echo "--- start.sh: Woke up after sleep ---"

echo "--- start.sh: Starting handler script in foreground... ---"
# Execute handler in foreground, redirect stderr to stdout for easier capture
python -u /workspace/handler.py 2>&1 
HANLDER_EXIT_CODE=$?
echo "--- start.sh: Handler script exited with code: $HANLDER_EXIT_CODE ---"

# Optional: kill health check server on exit (might not be reached if handler fails)
echo "--- start.sh: Attempting to kill health check server PID $HEALTH_PID (if handler exited) ---"
kill $HEALTH_PID || echo "--- start.sh: Failed to kill health check server PID $HEALTH_PID (or it already exited) ---" 

echo "--- start.sh: Exiting with code $HANLDER_EXIT_CODE ---"
exit $HANLDER_EXIT_CODE # Exit with the handler's exit code 