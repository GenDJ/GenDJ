#!/bin/bash
set -ex # Exit on error, print commands

echo "Starting health check server in background..."
python /workspace/healthcheck/health_check_server.py &
HEALTH_PID=$!
echo "Health check server PID: $HEALTH_PID"

echo "Starting handler script..."
# Execute handler in foreground, redirect stderr to stdout for easier capture
python -u /workspace/handler.py 2>&1 
HANDLER_EXIT_CODE=$?
echo "Handler script exited with code: $HANDLER_EXIT_CODE"

# Optional: kill health check server on exit (might not be reached if handler fails)
# kill $HEALTH_PID || echo "Failed to kill health check server PID $HEALTH_PID" 

exit $HANDLER_EXIT_CODE # Exit with the handler's exit code 