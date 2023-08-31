#!/usr/bin/env python3

import time
import threading
from random import *

import switchyard
from switchyard.lib.address import *
from switchyard.lib.packet import *
from switchyard.lib.userlib import *


class Middlebox:
    def __init__(
            self,
            net: switchyard.llnetbase.LLNetBase,
            dropRate="0.19"
    ):
        self.net = net
        self.dropRate = float(dropRate)
        self.intf1 = net.interface_by_name("middlebox-eth0")
        self.intf2 = net.interface_by_name("middlebox-eth1")
        self.blaster_mac = EthAddr('10:00:00:00:00:01')
        self.blastee_mac = EthAddr('20:00:00:00:00:01')

    def handle_packet(self, recv: switchyard.llnetbase.ReceivedPacket):
        _, fromIface, packet = recv
        if fromIface == self.intf1.name:
            log_debug("Received from blaster")
            '''
            Received data packet
            Should I drop it?
            If not, modify headers & send to blastee
            '''
            if random() < self.dropRate:
                log_info(f'Drop {packet}')
            else:
                packet[Ethernet].src = self.intf2.ethaddr
                packet[Ethernet].dst = self.blastee_mac
                packet[IPv4].ttl -= 1
                log_info(f"Send er -> ee: {packet}")
                self.net.send_packet(self.intf2, packet)
        elif fromIface == self.intf2.name:
            log_debug("Received from blastee")
            '''
            Received ACK
            Modify headers & send to blaster. Not dropping ACK packets!
            '''
            packet[Ethernet].src = self.intf1.ethaddr
            packet[Ethernet].dst = self.blaster_mac
            packet[IPv4].ttl -= 1
            log_info(f"Send ee -> er: {packet}")
            self.net.send_packet(self.intf1, packet)
        else:
            log_debug("Oops :))")

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

        self.shutdown()

    def shutdown(self):
        self.net.shutdown()


def main(net, **kwargs):
    middlebox = Middlebox(net, **kwargs)
    middlebox.start()
