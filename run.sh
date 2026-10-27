#!/bin/sh
set -e

# Environment variables that must be configured:
#SCANNER_MODEL
#SCANNER_IP
#ADVERTISE_IP

# Environment variables that can be configured if needed (brscand reads the
# rest itself: BIND_IP, BIND_PORT, ADVERTISE_PORT, CONFIG_PATH, see README):
SCANNER_NAME="${SCANNER_NAME:-Brother}"
# PUID/PGID: run brscand (and so own the scanned files) as this user/group
# instead of root. PGID defaults to PUID.
PGID="${PGID:-${PUID}}"

for var in SCANNER_MODEL SCANNER_IP ADVERTISE_IP; do
	if [ -z "$(printenv "$var")" ]; then
		echo "Error: $var must be set" >&2
		exit 1
	fi
done

# Setup network scanner (needs root, writes the driver's config)
brsaneconfig4 -a \
	name="${SCANNER_NAME}" model="${SCANNER_MODEL}" ip="${SCANNER_IP}"

# Exec into service
if [ -n "$PUID" ]; then
	exec setpriv --reuid="$PUID" --regid="$PGID" --clear-groups brscand
fi
exec brscand
