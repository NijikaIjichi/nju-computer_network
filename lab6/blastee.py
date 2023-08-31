#!/usr/bin/env python3

import time
import threading
from struct import pack, unpack
import switchyard
from switchyard.lib.address import *
from switchyard.lib.packet import *
from switchyard.lib.userlib import *


class Blastee:
    def __init__(
            self,
            net: switchyard.llnetbase.LLNetBase,
            blasterIp,
            num,
            output=None
    ):
        self.net = net
        self.blaster_ip = IPv4Address(blasterIp)
        self.num = int(num)
        self.acked = 0
        self.rev_data = [None] * self.num
        self.output = open(output, "wb") if output else None

    def handle_packet(self, recv: switchyard.llnetbase.ReceivedPacket):
        _, fromIface, packet = recv
        log_debug(f"I got a packet from {fromIface}")
        log_debug(f"Pkt: {packet}")
        intf = self.net.interface_by_name(fromIface)
        ctx = packet[RawPacketContents].to_bytes()
        ackno, length = unpack('!IH', ctx[:6])
        pkt_data = ctx[6:]
        assert length == len(pkt_data)
        ack = ctx[:4] + pack('!8s', pkt_data)
        pkt = Ethernet(dst=packet[Ethernet].src, src=intf.ethaddr, ethertype=EtherType.IPv4) + \
                IPv4(dst=packet[IPv4].src, src=intf.ipaddr, protocol=IPProtocol.UDP, ttl=64) + \
                UDP() + ack
        log_info(f"ack seqno = {ackno}")
        self.net.send_packet(intf, pkt)
        if self.rev_data[ackno - 1] is None:
            self.acked += 1
            self.rev_data[ackno - 1] = pkt_data
            if self.acked == self.num:
                log_info("receive finish")
                if self.output:
                    total_data = b''.join(self.rev_data)
                    total_sz = unpack('!I', total_data[:4])[0]
                    self.output.write(total_data[4:total_sz+4])
                    self.output.close()
                    while True: pass

    def start(self):
        '''A running daemon of the blastee.
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
    blastee = Blastee(net, **kwargs)
    blastee.start()
