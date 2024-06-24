# Import necessary base images
FROM nvidia/cuda:11.8.0-base-ubuntu22.04 as runtime

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

RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

# Install necessary Python packages
RUN pip install --upgrade --no-cache-dir pip && \
    pip install --upgrade setuptools && \
    pip install --upgrade wheel
RUN pip install --upgrade --no-cache-dir torch==2.0.1+cu118 torchvision==0.15.2+cu118 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cu118
RUN pip install --upgrade --no-cache-dir jupyterlab ipywidgets jupyter-archive jupyter_contrib_nbextensions triton xformers==0.0.22 gdown

# Set up Jupyter Notebook
RUN pip install notebook==6.5.5
RUN jupyter contrib nbextension install --user && \
    jupyter nbextension enable --py widgetsnbextension

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

RUN git clone https://github.com/GenDJ/GenDJ.git /workspace/GenDJ

COPY ./saved_pipeline /workspace/GenDJ/saved_pipeline

# Verify the presence of .git directory
RUN ls -al /workspace/GenDJ && ls -al /workspace/GenDJ/.git

# Set working directory to GenDJ
WORKDIR /workspace/GenDJ

# Install GenDJ requirements
RUN pip install -r requirements.txt

# Extras
# RUN /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
# ENV PATH="/home/linuxbrew/.linuxbrew/bin:${PATH}"
# # RUN brew update && brew install pyenv
# RUN brew tap filebrowser/tap && brew install filebrowser

CMD [ "/start.sh" ]
