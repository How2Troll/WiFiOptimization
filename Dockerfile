# Use an official CUDA base image
FROM nvidia/cuda:12.4.1-base-ubuntu22.04

# Avoid prompts from apt during build
ARG DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    pkg-config \
    libgirepository1.0-dev \
    libcairo2-dev \
    libsystemd-dev \
    libdbus-1-dev \
    build-essential \
    cmake \
    git \
    wget \
    python3-pip && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the entire ns-3-dev directory including subdirectories like contrib
COPY . /usr/src/app

# Ensure the ns3 script and training scripts are executable
RUN chmod +x /usr/src/app/ns3

# Enable Docker BuildKit for efficient caching during the build
# Install Python dependencies using cache mounts to speed up builds
RUN --mount=type=cache,target=/root/.cache \
    pip install --no-cache-dir -r requirements.txt

# Run the ns3 script to configure and build ns-3
RUN ./ns3 configure --build-profile=optimized --enable-examples --enable-tests
RUN ./ns3 build

# Make the training script executable
RUN chmod +x /usr/src/app/contrib/reinforced-lib/examples/ns-3-ccod/tools/scripts/train.sh

# Set environment variables
ENV YOUR_NS3_PATH="/usr/src/app"
ENV REINFORCED_LIB="/usr/src/app/contrib/reinforced-lib"


WORKDIR $REINFORCED_LIB
RUN pip install ".[full]"

WORKDIR $YOUR_NS3_PATH
# Install ns3 Python bindings
RUN pip install "$YOUR_NS3_PATH/contrib/ns3-ai/py_interface"

# Default command that runs when the container starts. Adjust accordingly.
#CMD ["./contrib/reinforced-lib/examples/ns-3-ccod/tools/scripts/train.sh", "DDQN", "highDensity", "3", "200"]

#docker run --gpus all -it --name ns-3-sim ns-3-sim <- RUN IT WITH
#nvidia-smi <- TEST

#RUN ON HOST
# Add the package repositories
#distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
#curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
#curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

# Install the nvidia-docker2 package (and dependencies) after updating the package listing
#sudo apt-get update
#sudo apt-get install -y nvidia-docker2

# Restart the Docker daemon to complete the installation
#sudo systemctl restart docker