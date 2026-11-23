FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 MAVLINK20=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl gnupg lsb-release git cmake build-essential pkg-config \
      python3 python3-pip rapidjson-dev libopencv-dev \
      libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev \
      gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav \
      gstreamer1.0-gl \
 && curl -fsSL https://packages.osrfoundation.org/gazebo.gpg \
      -o /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] https://packages.osrfoundation.org/gazebo/ubuntu-stable jammy main" \
      > /etc/apt/sources.list.d/gazebo-stable.list \
 && apt-get update && apt-get install -y --no-install-recommends gz-harmonic libgz-sim8-dev \
 && rm -rf /var/lib/apt/lists/*

# Public, official ArduPilot Gazebo plugin. This pinned revision is LGPL-3.0.
RUN mkdir -p /opt/ardupilot_gazebo \
 && cd /opt/ardupilot_gazebo \
 && git init \
 && git remote add origin https://github.com/ArduPilot/ardupilot_gazebo.git \
 && git fetch --depth 1 origin f116b03552d05c8d0b0bed5ed67033a1183121d1 \
 && git checkout --detach FETCH_HEAD \
 && cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
 && cmake --build build -j2

RUN python3 -m pip install --no-cache-dir pymavlink==2.4.50

# Download the version-pinned official ArduPilot Copter SITL executable during
# each local build. The course repository does not redistribute its binary.
RUN curl -fsSL --retry 3 \
      https://firmware.ardupilot.org/Copter/stable-4.7.3/SITL_x86_64_linux_gnu/arducopter \
      -o /usr/local/bin/arducopter \
 && echo '0cab7ddc9e9f1ef7f7c88138fcf925824fb952eb15e4f69cd6c8ef9210e25bf0  /usr/local/bin/arducopter' | sha256sum -c - \
 && chmod 755 /usr/local/bin/arducopter

ENV GZ_SIM_SYSTEM_PLUGIN_PATH=/opt/ardupilot_gazebo/build
ENV GZ_SIM_RESOURCE_PATH=/opt/ardupilot_gazebo/models:/opt/ardupilot_gazebo/worlds

WORKDIR /lab
COPY gazebo-iris.parm start.sh runner.py render_trace.py attack.py starter_watchdog.py student_watchdog.py test_logic.py /lab/
RUN chmod 755 /lab/start.sh && mkdir -p /runs
CMD ["/lab/start.sh"]
