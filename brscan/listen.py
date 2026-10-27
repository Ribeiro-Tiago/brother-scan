import socket
import traceback

from .scanto import scanto, ScanError
from .config import flatten_menu


def launch(args, config):
    addr = (args.bind_addr, args.bind_port)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(addr)
    print("Listening on %s:%d" % addr)

    while True:
        data, addr = server_socket.recvfrom(2048)
        print("Got UDP packet: %d bytes from %s:%s" % (
            len(data), addr[0], addr[1]))
        if len(data) < 4 or data[0] != 2 or data[1] != 0 or data[3] != 0x30:
            print('Error: dropping unknown UDP data: %d bytes' % (len(data)))
            continue
        msg = data[4:].decode('utf-8')
        print('Received:', msg)
        msgd = {}
        for item in msg.split(';'):
            if not item:
                continue
            name, value = item.split('=')
            if name == 'USER':
                value = value[1:-1]
            msgd[name] = value

        if 'FUNC' not in msgd or 'USER' not in msgd:
            print('Error: malformed button message, missing FUNC/USER:', msgd)
            continue

        for menu_func, menu_user, menu_entry in flatten_menu(config['menu']):
            if msgd['FUNC'] == menu_func and msgd['USER'] == menu_user:
                # ponytail: this try/except IS the fix for the "scan
                # interrupted -> whole container dies" bug. scanto() used to
                # be called bare; any exception from it (paper jam, missing
                # ADF pages, a subprocess crash) propagated out of this
                # non-daemon thread, which killed it silently, which made
                # both thread.join() calls in brscand.main() return
                # immediately, which exited the process. One try/except at
                # the single call site fixes every caller - there's only
                # one.
                try:
                    scanto(msgd['FUNC'], menu_entry)
                except ScanError as e:
                    print('Scan failed, daemon staying up:', e)
                except Exception:
                    print('Unexpected error handling scan job, daemon staying up:')
                    traceback.print_exc()
                break
