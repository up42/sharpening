# Processing Block Example: Sharpening
![coverage](coverage.svg)

### Introduction

This repository is an example on how to bring your own algorithm to the [UP42 platform](https://up42.com) 
as a **custom processing block** that can be seamlessly integrated into UP42 workflows.
 
The instructions guide you through setting up, dockerizing and pushing your block to UP42.
The block will appear in the [UP42 custom-blocks menu](https://console.up42.com/custom-blocks). It can then be used like any other data or processing block.

<p align="center">
  <img width="500" src="https://i.ibb.co/XsTsFHv/custom-block-menu-sharpening.png">
</p>

The example code implements an **Image Sharpening** block for GeoTiff files. More details on the block functionality in the 
[Sharpening block documentation](https://docs.up42.com/up42-blocks/processing/sharpening.html).


### Requirements

This example requires the **Mac OS X or Linux bash**, [git](https://git-scm.com/), 
[Docker engine](https://docs.docker.com/engine/) and [GNU make](https://www.gnu.org/software/make/). 

In order to also edit or test the block code locally, 
[Python 3.7](https://python.org/downloads) and a virtual environment manager 
e.g. [virtualenvwrapper](https://virtualenvwrapper.readthedocs.io/en/latest/) are required.


### Download the example block

Clone the example block using git and navigate to the folder that contains the Dockerfile and UP42Manifest:

```bash
git clone https://github.com/up42/sharpening.git
cd sharpening
```

We will skip changing the example code here and directly push the block to the UP42 platform.
See chapter [Custom Blocks Advanced](https://docs.up42.com/going-further/custom-processing-block-dev.html)
in the UP42 Documentation for more advanced instructions on developing, testing, updating and publishing 
a custom block.


### Authenticate with the UP42 Docker registry

First login to the UP42 docker registry. Replace **<USER-NAME>** with the **email address** you login with on the UP42 website.
Make sure Docker is running on your computer. When asked for your password, enter your UP42 account password.

```bash
docker login -u=<USER-NAME> http://registry.up42.com

# Example:
docker login -u=hans.schmidt@up42.com http://registry.up42.com
```


###Build the block container

Then build the block container, replace **<USER-ID>** with your **UP42 User-ID**.

To get your **UP42 User-ID**, go to the the [UP42 custom-blocks menu](https://console.up42.com/custom-blocks) and click on
`PUSH A BLOCK TO THE PLATFORM`. At the bottom of the popup, copy your user ID from the
command `Push the image to the UP42 Docker registry` (e.g. ``6760d08e-54e3-4f1c-b22e-6ba605ec7592``).

```bash
docker build . -t registry.up42.com/<USER-ID>/sharpening:1.0 --build-arg manifest="$(cat UP42Manifest.json)"

# Example:
docker build . -t registry.up42.com/6760d08e-54e3-4f1c-b22e-6ba605ec7592/sharpening:1.0 --build-arg manifest="$(cat UP42Manifest.json)"
```


### Push the custom block to UP42

Now you can push the image to the UP42 docker registry. Again replace **<USER-ID>** with your **UP42 User-ID**.

```bash
docker push registry.up42.com/<USER-ID>/sharpening:1.0

# Example:
docker push registry.up42.com/6760d08e-54e3-4f1c-b22e-6ba605ec7592/sharpening:1.0
```

**Success!** The Sharpening Filter example block will now appear in the [UP42 custom-blocks menu](https://console.up42.com/custom-blocks>).
When building a workflow it can be selected under the *Custom blocks* tab.

<p align="center">
  <img width="500" src="https://i.ibb.co/S6zQRHy/custom-block-workflow.png">
</p>


### Support, questions and suggestions

Open a **github issue** in this repository or reach out via [Email](mailto:support@up42.com), 
we are happy to answer your questions!
