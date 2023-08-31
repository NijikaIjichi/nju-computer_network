'''
Ethernet learning switch in Python.

Note that this file currently has the code to implement a "hub"
in it, not a learning switch.  (I.e., it's currently a switch
that doesn't learn.)
'''
import switchyard
from switchyard.lib.userlib import *


def main(net: switchyard.llnetbase.LLNetBase):
    my_interfaces = net.interfaces()
    mymacs = [intf.ethaddr for intf in my_interfaces]
    intf_table = {intf.name: intf for intf in my_interfaces}
    mac_table = {}

    def flood(fromIface, packet):
        log_info(f"Flooding packet {packet}")
        [net.send_packet(intf, packet) for intf in my_interfaces if intf.name != fromIface]

    while True:
        try:
            _, fromIface, packet = net.recv_packet()
        except NoPackets:
            continue
        except Shutdown:
            break

        log_debug (f"In {net.name} received packet {packet} on {fromIface}")
        eth = packet.get_header(Ethernet)
        if eth is None:
            log_info("Received a non-Ethernet packet?!")
            return

        log_info(f"Learn {eth.src} is from {fromIface}")
        p = mac_table.get(eth.src)
        if p is not None:
            mac_table[eth.src] = [intf_table[fromIface], p[1]]
        else:
            if len(mac_table) == 5:
                mac_table.pop(min(mac_table.items(), key=lambda x: x[1][1])[0])
            mac_table[eth.src] = [intf_table[fromIface], 0]

        if eth.dst in mymacs:
            log_info("Received a packet intended for me")
        elif eth.dst == EthAddr("ff:ff:ff:ff:ff:ff"):
            flood(fromIface, packet)
        elif eth.dst in mac_table:
            p = mac_table[eth.dst]
            p[1] += 1
            log_info(f"Sending packet {packet} to {p[0].name}")
            net.send_packet(p[0], packet)
        else:
            flood(fromIface, packet)

    net.shutdown()
