FROM nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04
ARG DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

# Install required dependencies
RUN apt-get update && apt-get install -y \
  make build-essential libssl-dev zlib1g-dev \
  libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
  libncurses5-dev libncursesw5-dev xz-utils tk-dev libffi-dev \
  liblzma-dev python3-openssl git libturbojpeg \
  && rm -rf /var/lib/apt/lists/*

# Install pyenv
RUN curl https://pyenv.run | bash

# Add pyenv to shell startup script
ENV PATH /root/.pyenv/bin:/root/.pyenv/shims:$PATH
RUN echo 'export PATH="$HOME/.pyenv/bin:$PATH"' >> ~/.bashrc \
  && echo 'eval "$(pyenv init --path)"' >> ~/.bashrc \
  && echo 'eval "$(pyenv init -)"' >> ~/.bashrc \
  && echo 'eval "$(pyenv virtualenv-init -)"' >> ~/.bashrc

# Apply the changes to the current shell session
SHELL ["/bin/bash", "-c"]
RUN source ~/.bashrc

# Install Python 3.10 using pyenv
RUN pyenv install 3.10.0 && pyenv global 3.10.0

# Install virtualenv
RUN pip install virtualenv

# Create the workspace directory
RUN mkdir -p /workspace

# Clone the repository
RUN git clone https://github.com/GenDJ/GenDJ.git /workspace/GenDJ

# Set the working directory
WORKDIR /workspace/GenDJ

# Create a virtual environment and activate it
RUN python -m venv venv && source venv/bin/activate

# Install the requirements
RUN pip install -r requirements.txt

COPY ./saved_pipeline /workspace/GenDJ/

# Set the entrypoint to activate the virtual environment and run gendj.py
ENTRYPOINT ["/bin/bash", "-c", "source venv/bin/activate && python gendj.py"]