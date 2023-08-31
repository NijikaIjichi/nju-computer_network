#!/usr/bin/env python3

'''
Basic IPv4 router (static routing) in Python.
'''

import time
import switchyard
from switchyard.lib.userlib import *
from collections import *
from ipaddress import *

ForwardItem = namedtuple('ForwardItem', ['ip', 'next_hop', 'intf'])
ARPSendInfo = namedtuple('ARPSendInfo', ['send_time', 'remain_times', 'wait_packs', 'intf'])

class Node:
    def __init__(self, key, value):
        self.key, self.value = key, value
        self.prev = self.next = self

    def add_next(self, node):
        node.next = self.next
        node.prev = self
        self.next.prev = node
        self.next = node

    def remove(self):
        self.next.prev = self.prev
        self.prev.next = self.next

class DictQueue:
    def __init__(self):
        self.node = Node(None, None)
        self.map = {}
        self.size = 0

    def push(self, key, value):
        self.node.add_next(Node(key, value))
        self.map[key] = self.node.next
        self.size += 1

    def peek(self):
        if self.size == 0:
            return None
        return self.node.prev

    def pop(self):
        if self.size == 0:
            return None
        p = self.node.prev
        p.remove()
        self.map.pop(p.key)
        self.size -= 1
        return p

    def remove(self, key):
        if self.size == 0 or key not in self.map:
            return None
        p = self.map[key]
        p.remove()
        self.map.pop(p.key)
        self.size -= 1
        return p.value

    def get(self, key):
        if self.size == 0 or key not in self.map:
            return None
        return self.map[key].value

class ForwardTable:
    def __init__(self):
        self.table = []
    
    def add(self, ip, next_hop, intf):
        self.table.append(ForwardItem(ip, next_hop, intf))
    
    def search(self, ip):
        try:
            return max(filter(lambda item: ip in item.ip, self.table), key=lambda item: item.ip.prefixlen)
        except ValueError:
            return None

class Router(object):
    def __init__(self, net: switchyard.llnetbase.LLNetBase):
        self.net = net
        self.arp_table = {}
        self.forward_table = ForwardTable()
        self.arp_send = DictQueue()
        self.build_forward_table()

    def build_forward_table(self):
        for intf in self.net.interfaces():
            ipintf = intf.ipinterface.network
            self.forward_table.add(ipintf, IPv4Address('0.0.0.0'), intf)
        fp = open('forwarding_table.txt', 'r')
        for line in fp:
            ip, mask, next_hop, intf = line.split()
            self.forward_table.add(IPv4Network(f'{ip}/{mask}'), IPv4Address(next_hop), self.net.port_by_name(intf))
        fp.close()
        log_info(f"forward table: {self.forward_table.table}")

    def is_ip_in_router(self, ip):
        return ip in [intf.ipaddr for intf in self.net.interfaces()]

    def handle_arp(self, arp, iface):
        if self.arp_table.get(arp.senderprotoaddr) != arp.senderhwaddr:
            self.arp_table[arp.senderprotoaddr] = arp.senderhwaddr
            log_info(f'Update ARP Table: {self.arp_table}')
        if self.is_ip_in_router(arp.targetprotoaddr):
            if arp.operation == ArpOperation.Request:
                intf = self.net.interface_by_ipaddr(arp.targetprotoaddr)
                pkt = create_ip_arp_reply(intf.ethaddr, arp.senderhwaddr, intf.ipaddr, arp.senderprotoaddr)
                log_info(f"get request, reply arp {pkt} to {iface}")
                self.net.send_packet(iface, pkt)
            else:
                wait_packs = self.arp_send.remove(arp.senderprotoaddr)
                if wait_packs is not None:
                    for wait_pack in wait_packs.wait_packs:
                        wait_pack[Ethernet].dst = arp.senderhwaddr
                        log_info(f"get reply, send pend ip {wait_pack} to {wait_packs.intf}")
                        self.net.send_packet(wait_packs.intf, wait_pack)

    def handle_ip(self, ip, packet):
        packet[IPv4].ttl -= 1
        forward =  None if self.is_ip_in_router(ip.dst) else self.forward_table.search(ip.dst)
        if forward is not None:
            log_info(f"forward table hit {forward}")
            next_hop_ip = ip.dst if forward.next_hop == IPv4Address('0.0.0.0') else forward.next_hop
            next_hop = self.arp_table.get(next_hop_ip)
            packet[Ethernet].src = forward.intf.ethaddr
            if next_hop is not None:
                packet[Ethernet].dst = next_hop
                log_info(f"arp cache hit: {next_hop}, send ip {packet} to {forward.intf}")
                self.net.send_packet(forward.intf, packet)
            else:
                log_info(f"arp cache miss, pend ip {packet}")
                wait_packs = self.arp_send.get(next_hop_ip)
                if wait_packs is None:
                    self.arp_send.push(next_hop_ip, ARPSendInfo(0, 5, [packet], forward.intf))
                else:
                    wait_packs.wait_packs.append(packet)

    def handle_packet(self, recv: switchyard.llnetbase.ReceivedPacket):
        _, ifaceName, packet = recv
        arp = packet.get_header(Arp)
        if arp is not None:
            log_info(f"receive a arp packet {ifaceName} {arp}")
            self.handle_arp(arp, self.net.port_by_name(ifaceName))
        else:
            ip = packet.get_header(IPv4)
            if ip is not None:
                log_info(f"receive a ip packet {ifaceName} {ip}")
                self.handle_ip(ip, packet)

    def resend_arp(self):
        while self.arp_send.peek() and time.time() - self.arp_send.peek().value.send_time >= 1:
            node = self.arp_send.pop()
            key, value = node.key, node.value
            if value.remain_times > 0:
                arp = create_ip_arp_request(value.intf.ethaddr, value.intf.ipaddr, key)
                log_info(f"resend {key}, {value} {arp}")
                self.net.send_packet(value.intf, arp)
                self.arp_send.push(key, ARPSendInfo(time.time(), value.remain_times - 1, value.wait_packs, value.intf))

    def start(self):
        '''A running daemon of the router.
        Receive packets until the end of time.
        '''
        while True:
            self.resend_arp()

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
    type(net.interfaces()[0]).__repr__ = lambda self: self.name
    router = Router(net)
    router.start()
