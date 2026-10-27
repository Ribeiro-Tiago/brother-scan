#!/usr/bin/env python3

# (C) 2013 Francois Cauwe
# (C) 2015-2018 Esben Haabendal
# (C) 2026 Tiago Ribeiro
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version. See the LICENSE file for details.

#Global libs
import time
import threading
import argparse
import os
import signal
import socket
import sys

#Private libs
from . import listen
from . import snmp
from .config import load_config

def main():
    # Every option falls back to an env var (named in its help text)
    env = os.environ.get
    parser = argparse.ArgumentParser(
        description='Brother network scanner server')
    parser.add_argument('bind_addr', metavar='BIND_ADDR',
                        type=str, nargs='?', default=env('BIND_IP', '0.0.0.0'),
                        help='IP/host to bind UDP socket to [BIND_IP]')
    parser.add_argument('-p', '--bind-port', metavar='PORT',
                        type=int, default=env('BIND_PORT', 54925),
                        help='UDP port number to bind UDP socket to [BIND_PORT]')
    parser.add_argument('-A', '--advertise-addr', metavar='ADDR',
                        type=str, default=env('ADVERTISE_IP'),
                        help='IP/host to advertise to scanner [ADVERTISE_IP]')
    parser.add_argument('-P', '--advertise-port', metavar='PORT',
                        type=int, default=env('ADVERTISE_PORT'),
                        help='UDP port number to advertise to scanner [ADVERTISE_PORT]')
    parser.add_argument('scanner_addr', metavar='SCANNER_ADDR',
                        type=str, nargs='?', default=env('SCANNER_IP'),
                        help='IP address of scanner [SCANNER_IP]')
    parser.add_argument('-c', '--config', metavar='DIR',
                        type=str, default=env('CONFIG_PATH', '/config'),
                        help='Configuration directory containing brother.yaml '
                             '[CONFIG_PATH]')
    args = parser.parse_args()
    if args.scanner_addr is None:
        parser.error('SCANNER_ADDR (or SCANNER_IP env var) is required')
    # No fallback to BIND_ADDR: that's usually 0.0.0.0, which the scanner
    # can't send anything to, so it would silently never scan
    if args.advertise_addr is None:
        parser.error('-A/--advertise-addr (or ADVERTISE_IP env var) is '
                     'required: the IP the scanner should send scans to')
    if args.advertise_port is None:
        args.advertise_port = args.bind_port

    # Resolv hosts
    args.bind_addr = socket.gethostbyname(args.bind_addr)
    args.advertise_addr = socket.gethostbyname(args.advertise_addr)
    args.scanner_addr = socket.gethostbyname(args.scanner_addr)

    # Loading global configuration
    config = load_config(os.path.join(args.config, 'brother.yaml'))

    # As PID 1 in a container SIGTERM is ignored unless handled, so
    # docker stop would wait for its timeout and then SIGKILL us
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    # Start listener
    listenThread = threading.Thread(target=listen.launch, args=(args, config),
                                    daemon=True)
    listenThread.start()
    time.sleep(1)

    # Start Snmp
    snmpThread = threading.Thread(target=snmp.launch, args=(args, config),
                                  daemon=True)
    snmpThread.start()

    # If either thread dies, exit so the container restart policy kicks in
    # instead of leaving a process that looks alive but does nothing
    while listenThread.is_alive() and snmpThread.is_alive():
        time.sleep(5)
    print('Error: a worker thread died, exiting')
    sys.exit(1)

if __name__ == '__main__':
    main()
