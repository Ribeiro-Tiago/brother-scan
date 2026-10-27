from pysnmp.hlapi.v3arch.asyncio import (
    CommunityData, ContextData, ObjectIdentity, ObjectType, SnmpEngine,
    UdpTransportTarget, set_cmd)
from pysnmp.proto import rfc1902
import asyncio
import pathlib

from .config import flatten_menu

HEARTBEAT_PATH = '/tmp/brscand.heartbeat'

async def add_menu_entry(snmpEngine, authData, transportTarget,
                         button, func, user, host, appnum,
                         duration=360, brid=''):
    cmd = 'TYPE=BR;BUTTON=%s;USER="%s";FUNC=%s;HOST=%s;APPNUM=%s;DURATION=%s;BRID=%s;'%(button, user, func, host, appnum, duration, brid)
    #print('Registering:', cmd)
    errorIndication, errorStatus, errorIndex, varBinds = await set_cmd(
        snmpEngine, authData, transportTarget, ContextData(),
        ObjectType(ObjectIdentity('1.3.6.1.4.1.2435.2.3.9.2.11.1.1.0'),
                   rfc1902.OctetString(cmd))
    )
    # See http://www.oidview.com/mibs/2435/BROTHER-MIB.html

    # Check for errors and print out results
    if errorIndication:
        print(errorIndication)
    else:
        if errorStatus:
            print('%s at %s' % (
                errorStatus.prettyPrint(),
                errorIndex and varBinds[int(errorIndex)-1] or '?'))

async def advertise(args, config):
    snmpEngine = SnmpEngine()
    authData = CommunityData('internal', mpModel=0)
    transportTarget = await UdpTransportTarget.create((args.scanner_addr, 161))
    addr = (args.advertise_addr, args.advertise_port)
    print('Advertising %s:%d to %s' % (addr + (args.scanner_addr,)))
    for func, user, entry in flatten_menu(config['menu']):
        print('Entry:', func, user, entry)
    while(1):
        print('Advertising to scanner')
        appnum = 1
        for func, user, entry in flatten_menu(config['menu']):
            await add_menu_entry(snmpEngine, authData, transportTarget,
                                 'SCAN', func, user, '%s:%d' % addr, appnum)
            appnum += 1
        # Docker HEALTHCHECK looks at this file's age
        pathlib.Path(HEARTBEAT_PATH).touch()
        await asyncio.sleep(60)

def launch(args, config):
    asyncio.run(advertise(args, config))
