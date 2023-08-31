#!/usr/bin/env python3

'''
Basic IPv4 router (static routing) in Python.
'''

import time
import switchyard
from switchyard.lib.userlib import *


class Router(object):
    def __init__(self, net: switchyard.llnetbase.LLNetBase):
        self.net = net
        self.arp_table = {}

    def handle_packet(self, recv: switchyard.llnetbase.ReceivedPacket):
        _, ifaceName, packet = recv
        arp = packet.get_header(Arp)
        if arp is None:
            return
        if self.arp_table.get(arp.senderprotoaddr) != arp.senderhwaddr:
            self.arp_table[arp.senderprotoaddr] = arp.senderhwaddr
            log_info(f'Update ARP Table: {self.arp_table}')
        if arp.operation == ArpOperation.Request:
            try:
                intf = self.net.interface_by_ipaddr(arp.targetprotoaddr)
                self.net.send_packet(self.net.port_by_name(ifaceName), 
                                     create_ip_arp_reply(intf.ethaddr, arp.senderhwaddr, intf.ipaddr, arp.senderprotoaddr))
            except KeyError:
                pass    

    def start(self):
        '''A running daemon of the router.
        Receive packets until the end of time.
        '''
        while True:
            try:
                recv = self.net.recv_packet(timeout=1.0)
            except NoPackets:
                continue
            except Shutdown:
                break

            self.handle_packet(recv)

        self.stop()

    def stop(self):
        self.net.shutdown()


def main(net):
    '''
    Main entry point for router.  Just create Router
    object and get it going.
    '''
    router = Router(net)
    router.start()
