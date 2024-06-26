# Import necessary base images
FROM nvidia/cuda:12.1.0-devel-ubuntu22.04 as runtime

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Set working directory and environment variables
ENV SHELL=/bin/bash
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /

# Set up system
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    make build-essential libssl-dev zlib1g-dev \
    libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
    libncurses5-dev libncursesw5-dev xz-utils tk-dev libffi-dev \
    liblzma-dev python3-openssl git libturbojpeg \
    libgl1 software-properties-common openssh-server nginx rsync && \
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get install -y --no-install-recommends python3.10-dev python3.10-venv && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    echo "en_US.UTF-8 UTF-8" > /etc/locale.gen

# Set up Python and pip
RUN ln -s /usr/bin/python3.10 /usr/bin/python && \
    rm /usr/bin/python3 && \
    ln -s /usr/bin/python3.10 /usr/bin/python3 && \
    curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py && \
    python get-pip.py

RUN git clone https://github.com/GenDJ/GenDJ.git /workspace/GenDJ

COPY ./saved_pipeline /workspace/GenDJ/saved_pipeline

# Set up GenDJ environment
WORKDIR /workspace/GenDJ
RUN python -m venv /workspace/GenDJ/venv
ENV GENDJ_VIRTUAL_ENV=/workspace/GenDJ/venv
RUN . $GENDJ_VIRTUAL_ENV/bin/activate && \
    pip install --upgrade --no-cache-dir pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt && \
    deactivate

RUN chmod +x ./run_containerized.sh

# Set up Jupyter environment
WORKDIR /workspace
RUN python -m venv /workspace/jupyter_env
ENV JUPYTER_VIRTUAL_ENV=/workspace/jupyter_env
RUN . $JUPYTER_VIRTUAL_ENV/bin/activate && \
    pip install --upgrade --no-cache-dir pip setuptools wheel && \
    pip install --no-cache-dir jupyterlab ipywidgets jupyter-archive jupyter_contrib_nbextensions triton notebook==6.5.5 && \
    jupyter contrib nbextension install --user && \
    jupyter nbextension enable --py widgetsnbextension && \
    deactivate

WORKDIR /

# NGINX Proxy
COPY --from=proxy nginx.conf /etc/nginx/nginx.conf
COPY --from=proxy readme.html /usr/share/nginx/html/readme.html

# Copy the README.md
COPY ./official-templates/stable-diffusion-comfyui/README.md /usr/share/nginx/html/README.md

# Start Scripts
COPY ./official-templates/stable-diffusion-comfyui/pre_start.sh /pre_start.sh
COPY --from=scripts start.sh /
COPY --from=scripts post_start.sh /

RUN chmod +x /pre_start.sh
RUN chmod +x /start.sh
RUN chmod +x /post_start.sh

CMD [ "/start.sh" ]