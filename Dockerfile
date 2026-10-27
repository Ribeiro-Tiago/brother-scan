# syntax=docker/dockerfile:1
ARG PYTHON_IMAGE=python:3.15.2-slim-bookworm

# --- Stage: fetch the Brother scanner driver --------------------------------
# BRSCAN_VERSION (e.g. 0.4.11-1) downloads it from Brother, otherwise
# BRSCAN_DEB_PATH points at the .deb inside the build context. One of them
# is required.
FROM ${PYTHON_IMAGE} AS driver
ARG BRSCAN_VERSION
ARG BRSCAN_DEB_PATH
RUN --mount=type=bind,target=/ctx \
    if [ -n "$BRSCAN_VERSION" ]; then \
      apt-get update -q \
      && apt-get install -q -y --no-install-recommends curl \
      && curl -fsSL -o /brscan4.deb \
        "https://download.brother.com/pub/com/linux/linux/packages/brscan4-${BRSCAN_VERSION}.amd64.deb"; \
    elif [ -n "$BRSCAN_DEB_PATH" ]; then \
      cp "/ctx/${BRSCAN_DEB_PATH}" /brscan4.deb; \
    else \
      echo "Error: set --build-arg BRSCAN_VERSION or BRSCAN_DEB_PATH" >&2; exit 1; \
    fi

# --- Stage: build the brscan wheel ------------------------------------------
FROM ${PYTHON_IMAGE} AS wheel
WORKDIR /src
COPY pyproject.toml requirements.txt README.md LICENSE ./
COPY brscan/ brscan/
RUN pip wheel --no-cache-dir --no-deps -w /dist .

# --- Final image ------------------------------------------------------------
FROM ${PYTHON_IMAGE}
LABEL maintainer="Tiago Ribeiro, 11082362+Ribeiro-Tiago@users.noreply.github.com"
LABEL org.opencontainers.image.source="https://github.com/Ribeiro-Tiago/brother-scan"

# Defaults for the runtime env vars brscand reads. VOLUME/EXPOSE are fixed
# at build time, so change them with --build-arg, not docker run -e.
ARG BIND_PORT=54925
ARG OUTPUT_DIR=/output
ARG CONFIG_PATH=/config
ENV BIND_PORT=${BIND_PORT} \
    OUTPUT_DIR=${OUTPUT_DIR} \
    CONFIG_PATH=${CONFIG_PATH} \
    PYTHONUNBUFFERED=1

# This is where the scan output will be written to
VOLUME ${OUTPUT_DIR}

# This must be mapped to ${ADVERTISE_IP}:${BIND_PORT}
EXPOSE ${BIND_PORT}/udp

# Install required Debian packages
# imagemagick: required by Wand (python-imagemagick binding), never actually
#   installed in the upstream image - Wand silently failed without it.
#   Its PDF policy blocks writing PDFs, which is all we do with it.
RUN apt-get update -q \
 && apt-get install -q -y --no-install-recommends \
      sane sane-utils poppler-utils libusb-0.1-4 imagemagick \
 && sed -i '/pattern="PDF"/d' /etc/ImageMagick-6/policy.xml \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Install Brother scanner driver and fix up its symbolic links
RUN --mount=type=bind,from=driver,source=/brscan4.deb,target=/tmp/brscan4.deb \
    dpkg --install /tmp/brscan4.deb \
 && mkdir -p /usr/lib/sane \
 && for f in /usr/lib64/sane/libsane-brother*; do ln -s "$f" /usr/lib/sane/; done

# Install required python modules, then brscan itself
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt
RUN --mount=type=bind,from=wheel,source=/dist,target=/dist \
    pip install --no-cache-dir --no-deps /dist/*.whl

# Add run script and set it as default command
COPY run.sh /run.sh
RUN chmod +x /run.sh
CMD ["/run.sh"]

# brscand touches this file after every advertising round (each 60s); stale
# means the SNMP loop is stuck
HEALTHCHECK --interval=60s --timeout=5s --start-period=30s --retries=3 \
  CMD find /tmp/brscand.heartbeat -mmin -3 | grep -q .
