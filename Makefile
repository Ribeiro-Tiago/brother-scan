VENV := .venv
PY := $(VENV)/bin/python3
PIP := $(VENV)/bin/pip
IMAGE := brscan
BIND_IP ?= 0.0.0.0
SCANNER_IP ?=
SCANNER_MODEL ?=
ADVERTISE_IP ?=
BRSCAN_VERSION ?=
BRSCAN_DEB_PATH ?=

.PHONY: init run test build docker-build docker-run clean

## Create venv and install dependencies + package in editable mode.
## Needs Python 3.15.2+. Override with e.g. make init PY_BIN=python3.15
PY_BIN ?= python3
init:
	$(PY_BIN) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install build -e .

## Run the assert-based self-check (no scanner/hardware needed)
test:
	$(PY) -m brscan.test_scanto
	$(PY) -m brscan.test_config

## Run brscand locally against a real scanner (needs sane/scanimage on PATH)
## Usage: make run SCANNER_IP=192.168.0.10 SCANNER_MODEL=MFC-L2700DW ADVERTISE_IP=<this host>
run:
	@test -n "$(SCANNER_IP)" || (echo "SCANNER_IP is required, e.g. make run SCANNER_IP=192.168.0.10 SCANNER_MODEL=MFC-L2700DW" && exit 1)
	@test -n "$(SCANNER_MODEL)" || (echo "SCANNER_MODEL is required" && exit 1)
	@test -n "$(ADVERTISE_IP)" || (echo "ADVERTISE_IP is required (this host's IP)" && exit 1)
	$(VENV)/bin/brscand -A $(ADVERTISE_IP) $(BIND_IP) $(SCANNER_IP)

## Build the sdist tarball (dist/brscan-*.tar.gz, attached to GitHub releases)
build:
	$(PY) -m build --sdist

## Build the Docker image. Needs the Brother driver: BRSCAN_VERSION=0.4.11-1
## downloads it, or BRSCAN_DEB_PATH=brscan4-<ver>.amd64.deb (path in the repo)
docker-build:
	docker build --build-arg BRSCAN_VERSION=$(BRSCAN_VERSION) \
		--build-arg BRSCAN_DEB_PATH=$(BRSCAN_DEB_PATH) -t $(IMAGE) .

## Run the built image.
## Usage: make docker-run SCANNER_IP=... SCANNER_MODEL=... ADVERTISE_IP=...
docker-run:
	@test -n "$(SCANNER_IP)" || (echo "SCANNER_IP is required" && exit 1)
	@test -n "$(SCANNER_MODEL)" || (echo "SCANNER_MODEL is required" && exit 1)
	docker run --rm \
		-v $$(pwd)/output:/output \
		-v $$(pwd)/config.yaml:/config.yaml \
		-e SCANNER_MODEL=$(SCANNER_MODEL) -e SCANNER_IP=$(SCANNER_IP) \
		-e ADVERTISE_IP=$(ADVERTISE_IP) \
		-p 54925:54925/udp \
		$(IMAGE)

clean:
	rm -rf $(VENV) build dist *.egg-info
	find . -name '__pycache__' -exec rm -rf {} +
