"""Optional Python audit guard for reproducible no-network worker tests.

This is not proof of physical disconnection or native-library isolation.
"""
import sys
import os


def deny_network(event, args):
    if event in {'socket.connect', 'socket.connect_ex', 'socket.getaddrinfo', 'socket.sendto', 'socket.sendmsg'}:
        raise PermissionError('C04 test forbids Python network access')


sys.addaudithook(deny_network)
sys._voicec_network_guard = True
if os.environ.get('VOICE_C_NETWORK_GUARD_DIAGNOSTIC') == '1':
    print('C04_PYTHON_NETWORK_GUARD_ACTIVE', file=sys.stderr, flush=True)
