#!/bin/bash
set -e # Exit the script if any statement returns a non-true return value

# Paths to the virtual environments
GENDJ_VENV_PATH="/workspace/GenDJ/venv"
JUPYTER_VENV_PATH="/workspace/jupyter_env"

# ---------------------------------------------------------------------------- #
#                          Function Definitions                                #
# ---------------------------------------------------------------------------- #

# Start nginx service
start_nginx() {
  echo "Starting Nginx service..."
  service nginx start
}

# Execute script if exists
execute_script() {
  local script_path=$1
  local script_msg=$2
  if [[ -f ${script_path} ]]; then
    echo "${script_msg}"
    bash ${script_path}
  fi
}

# Setup ssh
setup_ssh() {
  if [[ $PUBLIC_KEY ]]; then
    echo "Setting up SSH..."
    mkdir -p ~/.ssh
    echo "$PUBLIC_KEY" >>~/.ssh/authorized_keys
    chmod 700 -R ~/.ssh

    # ... (rest of the SSH setup remains unchanged)
  fi
}

# Export env vars
export_env_vars() {
  echo "Exporting environment variables..."
  printenv | grep -E '^RUNPOD_|^PATH=|^_=' | awk -F = '{ print "export " $1 "=\"" $2 "\"" }' >>/etc/rp_environment
  echo 'source /etc/rp_environment' >>~/.bashrc
}

# Start jupyter lab
start_jupyter() {
  if [[ $JUPYTER_PASSWORD ]]; then
    echo "Starting Jupyter Lab..."
    mkdir -p /workspace &&
      cd / &&
      source "${JUPYTER_VENV_PATH}/bin/activate"
      nohup jupyter lab --allow-root --no-browser --port=8888 --ip=* --FileContentsManager.delete_to_trash=False --ServerApp.terminado_settings='{"shell_command":["/bin/bash"]}' --ServerApp.token=$JUPYTER_PASSWORD --ServerApp.allow_origin=* --ServerApp.preferred_dir=/workspace &>/jupyter.log &
    echo "Jupyter Lab started with token $JUPYTER_PASSWORD"
    deactivate
  else
    echo "No jupyter lab password, skipping"
  fi
}

run_gendj() {
  echo "Starting GenDJ..."
  cd /workspace/GenDJ
  ls -al
  if [ ! -d ".git" ]; then
    echo "Error: .git directory not found. Is this a valid Git repository?"
  else
    echo "pulling latest updates"
    git pull

    echo "Checking for .env and .env.example files"
    if [ -f .env ]; then
      echo ".env file exists"
    else
      echo ".env file does not exist"
    fi

    if [ -f .env.example ]; then
      echo ".env.example file exists"
      mv .env.example .env
      echo "Moved .env.example to .env"
    else
      echo "Error: .env.example file not found."
    fi

    # need to move settings into runpod env vars so user can set openai api key to use safely
    sed -i 's/SAFETY=TRUE/SAFETY=FALSE/' .env
    sed -i "s|const WEBSOCKET_URL = \"ws://localhost:8765\";|const WEBSOCKET_URL = \"wss://${RUNPOD_POD_ID}-8766.proxy.runpod.net\";|" ./fe/main.js
    sed -i "s|const PROMPT_ENDPOINT_URL_BASE = \"http://localhost:5556/prompt/\";|const PROMPT_ENDPOINT_URL_BASE = \"https://${RUNPOD_POD_ID}-5559.proxy.runpod.net/prompt/\";|" ./fe/main.js

    # Activate GenDJ virtual environment
    source "${GENDJ_VENV_PATH}/bin/activate"
    
    # Run the script to start GenDJ and capture its PID
    nohup ./run_containerized.sh > gendj.log 2>&1 & 
    GENDJ_PID=$!
    echo "GenDJ server started in background with PID: $GENDJ_PID"
    
    # Optionally, you can write the PID to a file for future reference
    # echo $GENDJ_PID > /workspace/GenDJ/gendj.pid
  fi
}

# ---------------------------------------------------------------------------- #
#                               Main Program                                   #
# ---------------------------------------------------------------------------- #

start_nginx

execute_script "/pre_start.sh" "Running pre-start script..."

echo "Pod Started"

setup_ssh
start_jupyter
export_env_vars

if [[ -z "${RUNPOD_PROJECT_ID}" ]]; then
  echo "start1212 RUNPOD_PROJECT_ID environment variable is not set."
else
  echo "start1212 RUNPOD_PROJECT_ID: ${RUNPOD_PROJECT_ID}"
fi

if [[ -z "${RUNPOD_POD_ID}" ]]; then
  echo "start1212 RUNPOD_POD_ID environment variable is not set."
else
  echo "start1212 RUNPOD_POD_ID: ${RUNPOD_POD_ID}"
fi

echo "trying to start gendj1212"


if [ -z "$AUTO_RUN" ] || [ "$AUTO_RUN" != "PREVENT" ]; then
  run_gendj
fi

echo "Start script(s) finished, pod is ready to use."

cd /

sleep infinity