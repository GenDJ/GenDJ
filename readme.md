# GenDJ
A TON OF THIS CODE IS LIFTED FROM [https://github.com/kylemcdonald/i2i-realtime](https://github.com/kylemcdonald/i2i-realtime)
THAT PIONEERING WORK DONE BY KYLE MCDONALD, DAITO MANABE, AND RHIZOMATIKS IS INCREDIBLE AND ALL OF YOU SHOULD GO READ THROUGH THE CODE BASE WHICH AT ITS TIME OF CREATION LIKE 6 MONTHS AGO WAS SO FAR AHEAD OF WHERE ME AND ALL OF YOU WERE AT IT'S BONKERS

AS SUCH THEIR LICENSE AND COPYRIGHT REMAIN IN THIS REPO AS WELL AND TO BE HONEST I DON'T REALLY KNOW HOW THAT STUFF WORKS ANYWAYS

I actually thought I might remake this as a fork/PR to that repo, but as this drives closer towards my vision of what I want GenDJ to be, the architectures are probably going to continue to diverge so I'm keeping this broken out as a separate project

As-is, this is a hacked together version of that, stripped down to only run on one machine and only work via a websockets connection from a new very minimal javascript/html frontend. So most of the changes were removing stuff, not adding stuff (with the exception of the websocket stuff and frontend).

That said, after the next section describing the differences between the two projects is the readme from that project, which is in many ways WAY superior and written by someone who I would assume actually knows python (I haven't touched python in like 10 yrs so a lot of the unique pieces of GenDJ code were chatgpt).

## Differences in how to run GenDJ vs the original realtime-i2i repo


Follow the readme of i2i realtime to get the project set up, but then just do `python gendj.py`

Then in your browser go to http://localhost:5556/fe/index.html, click the start button, and wait like 20 seconds for the round trip to kick in.

I'm running it with venv locally on a pop_os linux box with an RTX 3090 and 8700k, which gets me about 20fps with how it's made right now. Looks like it uses less than 16 gigs vram when running so I think you can get away with a weaker video card.

The [original realtime-i2i repo](https://github.com/kylemcdonald/i2i-realtime) I think was designed to work between multiple locally networked machines. There is a video source like a networked camera, a webcam, or a video, a server machine which accepts a stream of video and puts it in a zmq queue, one or many worker machines which pull frames from the queue in batches and warp them with sdxl then put the frames back into an output queue, then back to the server machine which pulls the batches of rendered frames, reorders them, and displays them. There is an alternate solo machine way to run the original project as well, which a lot of this is based on. The original repo also had real time opacity manipulation built in but I couldn't get it working.

This project is stripped down to be only that solo way of running it, and only to accept frames from a webcam connected to a new web browser interface unique to this project.


ORIGINAL README BELOW
# Realtime i2i for Rhizomatiks

This system takes input from an image stream (`ThreadedSequence`) or from a live camera stream (`ThreadedCamera`).

The final output is a msgpack-encoded list served as ZMQ publisher on port 5557 in the format [timestamp, index, jpg].

* timestamp (int) is the time in milliseconds since Unix epoch. Useful for estimating overall latency.
* index (int) is the frame index.
* jpg (byte buffer) is a libturbo-jpeg encoded JPG of the image.

By default, the results are also displayed fullscreen.

## Machine Setup

This software runs on multiple computers that are networked together.

First, install Ubuntu 20.04 on a computer with an NVIDIA GPU. When rebooting, disable secure boot so that you can install the NVIDIA drivers.

Open a Terminal and enable ssh access:

```
sudo apt install -y openssh-server
mkdir -m700 ~/.ssh
wget -qO- https://github.com/<username>.keys | head -n1 > ~/.ssh/authorized_keys
```

Replace `<username>` with your GitHub username. Then ssh into the server and continue.

```
# install curl
sudo apt-get update
sudo apt install -y curl

# install git
sudo apt install -y git

# install NVIDIA drivers
wget https://developer.download.nvidia.com/compute/cuda/12.3.1/local_installers/cuda_12.3.1_545.23.08_linux.run
sudo apt remove -y --purge "*nvidia*"
sudo apt install -y build-essential
sudo sh cuda_12.3.1_545.23.08_linux.run # select the option to use the NVIDIA drivers with X
rm cuda_12.3.1_545.23.08_linux.run

# install CuDNN
# download from https://developer.nvidia.com/rdp/cudnn-download
sudo dpkg -i cudnn-local-repo-ubuntu2004-8.9.7.29_1.0-1_amd64.deb
sudo cp /var/cudnn-local-repo-ubuntu2004-8.9.7.29/cudnn-local-30472A84-keyring.gpg /usr/share/keyrings/
sudo apt-get update
sudo apt-get install libcudnn8

# grab source
git clone https://github.com/kylemcdonald/i2i-realtime.git
cd i2i-realtime
```

If you are running natively:

```
sudo apt install python3.10 python3.10-dev python3.10-venv libturbojpeg
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If you are using Anaconda:

```
sudo apt install libturbojpeg
conda create -y -n i2i python=3.10
conda activate i2i
pip install -r requirements.txt
```

If you are using Docker:

```
# install docker
sudo apt-get update
sudo apt-get install ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# install NVIDIA container toolkit
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
  && curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list \
  && \
    sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
sudo nvidia-ctk runtime configure --runtime=containerd
sudo systemctl restart containerd

# disable updates and notifications
gsettings set org.gnome.desktop.notifications show-banners false
sudo systemctl disable --now apt-daily{{,-upgrade}.service,{,-upgrade}.timer}
sudo systemctl disable --now unattended-upgrades
sudo systemctl daemon-reload
sudo systemctl stop unattended-upgrades
sudo systemctl mask unattended-upgrades
```

Finally, download the models once (we disable all internet connectivity later so that there are no problems running offline):

```
python download-models.py
```

## Useful commands

Remove the cursor after 1 second (applied on reboot):

```
sudo apt-get install unclutter
```

Generate frames of images from a video:

```
sudo apt install -y ffmpeg
mkdir -p data/frames && ffmpeg -i video.mp4 -vf fps=30 data/frames/%06d.jpg
```

## Running manually

The code has two parts: the server and the worker.

To run the worker, enable the virtual env and run the worker:

```
source .venv/bin/activate
python transform.py
```

To run the server, do the same:

```
source .venv/bin/activate
python app.py
```

Both the worker and server have flags that can be configured at the command line. There are also some flags that can be controlled using the .env file, with examples shown in .env.example. For example, when running the worker on a different computer from the server, you should specify the `--primary_hostname` of the server, or set that hostname in the .env so that the worker can communicate with the server.

If you have enabled prompt translation or safety checking, you will need to provide an OpenAI API key and a Google Service Account JSON file.

## Running automatically

To run the app automatically on boot, and to recover automatically from crashes, install systemd services.

Before doing this, make sure that the user has access to controlling systemctl, and for controlling shutdown:

```
bash install-polkit.sh
sudo usermod -aG sudo <username>
```

### Setting Keyboard shortcuts

Add a keyboard shortcut pointing to "/home/rzm/Documents/i2i-realtime/./shutdown.sh"

Add another keyboard shortcut pointing to "/home/rzm/Documents/i2i-realtime/./reload.sh"

Copy ssh keys from your server to all the workers so that they can be shutdown automatically over ssh (use the script in `automation/ssh-copy-ids.sh`).

```
bash install-worker-service.sh # install on all workers
bash install-server-service.sh # install on server only
```

To make it easy to adminster the installation, add a [custom keyboard shortcut](https://help.ubuntu.com/stable/ubuntu-help/keyboard-shortcuts-set.html.en).

* Add a shortcut for `Alt+Q` pointing to the absolute path of `shutdown.sh`. This will stop the app and all worker services and shutdown the server and all workers.
* Add a shortcut for `Alt+R` pointing to the absolute path of `reload.sh`. This will reload the app and all worker services.

## Controlling the parameters in realtime

The server exposes some parameters over FastAPI on port 5556.

A text-based controller example is available by running `input-publisher.py`. This streams keyboard input to the server.

Use chat-style commands: plain text or `/prompt` to update the prompt, and `/seed 123` to set the seed, etc.

Other useful commands include `/passthrough True` or `/passthrough False`.
