Join the [discord](https://discord.gg/EtE9HFs2) to meet others interested in real-time AI

# GenDJ
A TON OF THIS CODE IS LIFTED FROM [https://github.com/kylemcdonald/i2i-realtime](https://github.com/kylemcdonald/i2i-realtime)
THAT PIONEERING WORK DONE BY KYLE MCDONALD, DAITO MANABE, AND RHIZOMATIKS IS INCREDIBLE AND ALL OF YOU SHOULD GO READ THROUGH THE CODE BASE WHICH AT ITS TIME OF CREATION LIKE 6 MONTHS AGO WAS SO FAR AHEAD OF WHERE ME AND ALL OF YOU WERE AT IT'S BONKERS

AS SUCH THEIR LICENSE AND COPYRIGHT REMAIN IN THIS REPO AS WELL AND TO BE HONEST I DON'T REALLY KNOW HOW THAT STUFF WORKS ANYWAYS

I actually thought I might remake this as a fork/PR to that repo, but as this drives closer towards my vision of what I want GenDJ to be, the architectures are probably going to continue to diverge so I'm keeping this broken out as a separate project

As-is, this is a hacked together version of that, stripped down to only run on one machine and only work via a websockets connection from a new very minimal javascript/html frontend. So most of the changes were removing stuff, not adding stuff (with the exception of the websocket stuff and frontend).

The original i2i-realtime is in many ways WAY superior and written by someone who I would assume actually knows python (I haven't touched python in like 10 yrs so a lot of the unique pieces of GenDJ code were chatgpt).

## Differences in how to run GenDJ vs the original realtime-i2i repo


Follow the readme of i2i-realtime to get the project set up, and copy the contents of .env.example into a new file .env and adjust the values. 

You might have to do `python download-models.py` or I think running it the first time might just do that automatically?

Then just do `python gendj.py`

Then in your browser go to http://localhost:5556/fe/index.html, click the start button, and wait like 20 seconds for the round trip to kick in.

I'm running it with venv locally on a pop_os linux box with an RTX 3090 and 8700k, which gets me about 20fps with how it's made right now. Looks like it uses less than 16 gigs vram when running so I think you can get away with a weaker video card.

The [original realtime-i2i repo](https://github.com/kylemcdonald/i2i-realtime) I think was designed to work between multiple locally networked machines. There is a video source like a networked camera, a webcam, or a video, a server machine which accepts a stream of video and puts it in a zmq queue, one or many worker machines which pull frames from the queue in batches and warp them with sdxl then put the frames back into an output queue, then back to the server machine which pulls the batches of rendered frames, reorders them, and displays them. There is an alternate solo machine way to run the original project as well, which a lot of this is based on. The original repo also had real time opacity manipulation built in but I couldn't get it working.

This project is stripped down to be only that solo way of running it, and only to accept frames from a webcam connected to a new web browser interface unique to this project.

## env setup

To install and set up pyenv and virtualenv on Ubuntu to install Python 3.10 and create and source a Python 3.10 environment in the current directory, you can follow these steps:

1. Install Required Dependencies

```
sudo apt update
sudo apt install -y make build-essential libssl-dev zlib1g-dev \
libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
libncurses5-dev libncursesw5-dev xz-utils tk-dev libffi-dev \
liblzma-dev python3-openssl git
```
2. Install pyenv
```
curl https://pyenv.run | bash
```
3. Add pyenv to Shell Startup Script
Add the following lines to your shell startup script (~/.bashrc, ~/.zshrc, or ~/.profile):
```
export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"
```
Then, apply the changes:

```
source ~/.bashrc
```
4. Install Python 3.10 Using pyenv
```
pyenv install 3.10.0
```
5. Set Up pyenv to Use Python 3.10
```
pyenv global 3.10.0
```
6. Install virtualenv (if not already installed via pyenv)
```
pip install virtualenv
```
7. Create a Virtual Environment in the Current Directory
Navigate to your desired directory:
```
cd /path/to/your/project
```
Then, create the virtual environment:

```
python -m venv venv
```

8. Activate the Virtual Environment
```
source venv/bin/activate
```
After running these commands, you will have pyenv and virtualenv set up, Python 3.10 installed, and a Python 3.10 environment created and sourced in your current directory.

9. Install the requirements
```
pip install -r requirements.txt
```

10. ensure libturbojpeg is installed on your system
`sudo apt install libturbojpeg`

11. download the models
`python download-models.py`

# ETC

Some version of this may someday live at https://gendj.com

[ORIGINAL README HERE](https://github.com/kylemcdonald/i2i-realtime)
