# brother-scan

Push-scan daemon for network Brother scanners: listens for the scanner's
Scan-to-PC button over UDP/SNMP and writes a PDF straight to a shared
folder. No brscan-skey client needed on any PC. Alternative to brscan-skey
with ADF support, flatbed multi-page scanning, and compressed PDF output.

Fork of [esben/brother-scan](https://github.com/esben/brother-scan) with:
dependency updates, a Debian bookworm base image, a Makefile, a fix for a
bug that crashed the whole daemon on an interrupted scan, multi-page
flatbed scanning, arbitrarily nested config files, and a published Docker
image.

## Requirements

* Brother's `brscan4` driver, installed into the image at build time
  (see "Building the image yourself"). The latest one at
  http://support.brother.com/g/s/id/linux/en/download_scn.html is often
  older than what newer scanners need - some models (e.g. MFC-L2700DW)
  need 0.4.3-1 or newer. Brother only ships it for amd64 and i386, so the
  image is amd64-only (no ARM / Raspberry Pi).

## Local development (Makefile)

```sh
make init          # create .venv, install pinned deps, install brscan -e
make test           # run the self-check (no scanner/driver needed)
make run SCANNER_IP=192.168.0.10 SCANNER_MODEL=MFC-L2700DW
make build           # produce dist/brscan-*.tar.gz (attached to GitHub releases)
make docker-build BRSCAN_VERSION=0.4.11-1   # build the image locally
make docker-run SCANNER_IP=... SCANNER_MODEL=...
make clean
```

**Python version note:** needs Python 3.15.2+. The Docker image
uses 3.15. Point init at another interpreter with e.g.
`make init PY_BIN=python3.15`.

## Docker

Released images are published to
`ghcr.io/ribeiro-tiago/brother-scan` (`latest` or a version tag), with
Brother's driver already installed. GHCR packages start out private even
for a public repo, so after the first release set the package to public
(package page → Package settings → Change visibility).

What the container needs:

* `/output` - where scans are written. Point every menu entry's `dir` at
  a path inside it (e.g. `/output/user1`), not a path like `/tmp/scan1`,
  which would stay inside the container.
* `/config.yaml` - the config file with the scan menu (or mount it
  elsewhere and set `CONFIG_PATH`). It must exist on the host: if it
  doesn't, Docker mounts an empty directory there instead and `brscand`
  exits with an error saying so.
* UDP port `54925` published, and `ADVERTISE_IP` set to the **host's** IP
  as seen by the scanner - the scanner sends its button presses there.
* `SCANNER_MODEL`, `SCANNER_IP` and `ADVERTISE_IP` - see the env var
  table under Configuration for everything else.
* Optionally `PUID`/`PGID`, so scans are owned by that user/group instead
  of root. The `/output` folders must be writable by them.

With a config file:

```sh
docker run -d --name brother-scan --restart unless-stopped \
  -v /data/scans:/output \
  -v $(pwd)/config.yaml:/config.yaml:ro \
  -e SCANNER_MODEL=MFC-L2700DW -e SCANNER_IP=192.168.0.10 \
  -e ADVERTISE_IP=192.168.0.100 -p 54925:54925/udp \
  ghcr.io/ribeiro-tiago/brother-scan
```

### Docker compose / Dockhand

[compose.yaml](compose.yaml) is a ready-to-use stack. In Dockhand, create
a stack from it and set the values from [.env.example](.env.example) in
the stack's env (or copy it to `.env` next to `compose.yaml` for plain
`docker compose up -d`). Put your `config.yaml` (see Configuration) at
the host path `CONFIG_PATH` points to. Missing required values stop
`docker compose up` with a message naming them.

Check the container logs for `Advertising to scanner`, then the users
should show up under Scan → File on the scanner. The image's healthcheck
marks the container unhealthy if advertising to the scanner stops, and
`brscand` exits (so `restart: unless-stopped` restarts it) if one of its
worker threads dies.

### Building the image yourself

```sh
make docker-build BRSCAN_VERSION=0.4.11-1    # download the driver from Brother
make docker-build BRSCAN_DEB_PATH=brscan4-0.4.11-1.amd64.deb  # use a local .deb
```

One of the two is required; `BRSCAN_VERSION` wins if both are set.
`BRSCAN_DEB_PATH` is relative to the repo root (the build context).
The Dockerfile is multi-stage: one stage fetches the driver, one builds
the brscan wheel, and only their results land in the final image, so
plain `docker build --build-arg BRSCAN_VERSION=0.4.11-1 .` works too.

These build args set the defaults baked into the image (the matching env
vars can still be overridden at `docker run` time, but `VOLUME`/`EXPOSE`
only change with a rebuild):

| Build arg | Default |
|---|---|
| `BIND_PORT` | `54925` |
| `OUTPUT_DIR` | `/output` |
| `CONFIG_PATH` | `/config.yaml` |

## Releasing

Run the **Release** workflow from the GitHub Actions tab, on `master`
(other branches only run the tests). It bumps the
version from the commit messages since the last `vX.Y.Z` tag
([Conventional Commits](https://www.conventionalcommits.org)):
`feat!:` or `BREAKING CHANGE` → major, `feat:` → minor, anything else →
patch. Pick `major`/`minor`/`patch` in the form to override. It then
commits the new version to `pyproject.toml`, tags it, pushes the image
(with the driver version picked in the form, default `0.4.11-1`) to GHCR
and creates a GitHub release with the sdist attached. It needs an
existing `vX.Y.Z` tag on `master` to bump from (`v1.0.0` was the first).

## Configuration

The scan menu (the users and destinations shown on the scanner) lives
only in `config.yaml`, or the file `CONFIG_PATH` points at. It can be
nested arbitrarily deep for organization. Everything else is set with env
vars:

| Env var | Default | Meaning |
|---|---|---|
| `SCANNER_IP` | (required) | Scanner IP/host |
| `SCANNER_MODEL` | (required, Docker only) | Model passed to `brsaneconfig4` |
| `SCANNER_NAME` | `Brother` | Name passed to `brsaneconfig4` (Docker only) |
| `BIND_IP` / `BIND_PORT` | `0.0.0.0` / `54925` | Where to listen for the scanner |
| `ADVERTISE_IP` | (required) | This host's IP as the scanner sees it - scans are sent here |
| `ADVERTISE_PORT` | `BIND_PORT` | Port advertised to the scanner |
| `PUID` / `PGID` | root | Run as this user/group, so scans are owned by it (Docker only, `PGID` defaults to `PUID`) |
| `CONFIG_PATH` | `config.yaml` (`/config.yaml` in Docker) | YAML config file with the scan menu. In `compose.yaml` it's the host path that gets mounted there |

Two extra flatbed-scan options beyond upstream:

* `pages: N` - take N shots off the flatbed (pausing `pages_delay` seconds
  between each so you can swap the page) and merge into one PDF. Ignored
  when `adf: true` (ADF already produces multi-page output).
* `pages_delay: seconds` - delay between flatbed shots, default 3.

## Running on host OS

Needs Debian/Ubuntu-like with `sane`/`sane-utils` (scanimage, scanadf),
`poppler-utils` (pdfunite), `imagemagick` (Wand - the upstream
Dockerfile never installed it, which made Wand fail on
first scan), and the brscan4 driver installed. `make init && make run` as
above.

## Uselinks

* https://www.mcbsys.com/blog/2014/11/register-pc-on-brother-scanner/
* https://github.com/jmesmon/brother2/blob/master/PROTO

## License

GPL-3.0-or-later, see [LICENSE](LICENSE).

This is a modified version of
[esben/brother-scan](https://github.com/esben/brother-scan), changed by
Tiago Ribeiro in 2026 (see the fork notes at the top and the git history
for details).

* (C) 2013 Francois Cauwe
* (C) 2015-2018 Esben Haabendal, with contributions from Romuald Conty
* (C) 2026 Tiago Ribeiro

The Brother `brscan4` driver is proprietary (Copyright Brother Industries,
Ltd., all rights reserved) and isn't covered by this license. It isn't
part of this repository; the published Docker image includes it, installed
unmodified from Brother's download server.
