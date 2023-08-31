#!/usr/bin/env python3

from struct import pack, unpack
from time import time
from random import randint
import switchyard
from switchyard.lib.address import *
from switchyard.lib.packet import *
from switchyard.lib.userlib import *


class Blaster:
    def __init__(
            self,
            net: switchyard.llnetbase.LLNetBase,
            blasteeIp,
            num,
            length="100",
            senderWindow="5",
            timeout="300",
            recvTimeout="100",
            input=None
    ):
        self.net = net
        self.blastee_ip = IPv4Address(blasteeIp)
        self.num = int(num)
        self.length = int(length)
        self.sender_window = int(senderWindow)
        self.timeout = int(timeout) / 1000
        self.recv_timeout = int(recvTimeout) / 1000
        self.intf = net.interfaces()[0]
        self.dst_mac = EthAddr('40:00:00:00:00:01')
        self.lhs, self.rhs = 1, 1
        self.start_time = 0
        self.timer = 0
        self.acked = set()
        self.resend_idx = -1
        self.resend_num = 0
        self.timeout_times = 0
        self.input = open(input, "rb") if input else None

    def get_data(self, seqno):
        data = b''
        if self.input:
            if seqno == 1:
                self.input.seek(0, 2)
                sz = min(self.input.tell(), self.num * self.length - 4)
                self.input.seek(0, 0)
                data = pack('!I', sz) + self.input.read(self.length - 4)
            else:
                self.input.seek((seqno - 1) * self.length - 4, 0)
                data = self.input.read(self.length)
        data += b'\0' * (self.length - len(data))
        return data

    def send_pack(self, seqno):
        data = pack('!IH', seqno, self.length) + self.get_data(seqno)
        self.net.send_packet(self.intf,
            Ethernet(dst=self.dst_mac, src=self.intf.ethaddr, ethertype=EtherType.IPv4) +
            IPv4(dst=self.blastee_ip, src=self.intf.ipaddr, protocol=IPProtocol.UDP, ttl=64) +
            UDP() + data)

    def try_to_send(self):
        if self.start_time == 0:
            self.start_time = self.timer = time()
        if self.resend_idx == -1:
            if time() - self.timer < self.timeout:
                if self.rhs - self.lhs <= self.sender_window - 1 and self.rhs <= self.num:
                    log_info(f"send pack seqno = {self.rhs}")
                    self.send_pack(self.rhs)
                    self.rhs += 1
            else:
                self.resend_idx = self.lhs
                self.timer = time()
                self.timeout_times += 1
        while self.resend_idx in self.acked:
            self.resend_idx += 1
        if self.lhs <= self.resend_idx < self.rhs:
            log_info(f"resend pack seqno = {self.resend_idx}")
            self.send_pack(self.resend_idx)
            self.resend_idx += 1
            self.resend_num += 1
        if self.resend_idx >= self.rhs:
            self.resend_idx = -1

    def handle_ack(self, seqno):
        log_info(f"get ack seqno = {seqno}")
        self.acked.add(seqno)
        while self.lhs in self.acked:
            self.lhs += 1
            self.timer = time()
        if self.lhs == self.num + 1:
            total_time = time() - self.start_time
            if self.input:
                self.input.close()
            log_info(f"Total TX time: {total_time}s")
            log_info(f"Number of reTX: {self.resend_num}")
            log_info(f"Number of coarse TOs: {self.timeout_times}")
            log_info(f"Throughput: {(self.num + self.resend_num) * self.length / total_time}Bps")
            log_info(f"Goodput: {self.num * self.length / total_time}Bps")
            while True: pass

    def handle_packet(self, recv: switchyard.llnetbase.ReceivedPacket):
        _, fromIface, packet = recv
        log_debug("I got a packet")
        ctx = packet[RawPacketContents].to_bytes()
        seqno = unpack('!I', ctx[:4])[0]
        self.handle_ack(seqno)
        self.try_to_send()

    def handle_no_packet(self):
        log_debug("Didn't receive anything")
        self.try_to_send()

    def start(self):
        '''A running daemon of the blaster.
        Receive packets until the end of time.
        '''
        self.try_to_send()
        while True:
            try:
                recv = self.net.recv_packet(timeout=self.recv_timeout)
            except NoPackets:
                self.handle_no_packet()
                continue
            except Shutdown:
                break

            self.handle_packet(recv)

        self.shutdown()

    def shutdown(self):
        self.net.shutdown()


def main(net, **kwargs):
    blaster = Blaster(net, **kwargs)
    blaster.start()
