'''
Ethernet learning switch in Python.

Note that this file currently has the code to implement a "hub"
in it, not a learning switch.  (I.e., it's currently a switch
that doesn't learn.)
'''
import switchyard
from switchyard.lib.userlib import *

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

class LRUCache:
    def __init__(self, cap):
        self.cap = cap
        self.size = 0
        self.node = Node(None, None)
        self.map = {}

    def remove_lru(self):
        assert self.size > 0
        node = self.node.prev
        node.remove()
        self.map.pop(node.key)
        self.size -= 1

    def flush_mru(self, key):
        p = self.map[key]
        p.remove()
        self.node.add_next(p)

    def put(self, key, value):
        if key in self.map:
            self.map[key].value = value
        else:
            if self.size == self.cap:
                self.remove_lru()
            self.node.add_next(Node(key, value))
            self.map[key] = self.node.next
            self.size += 1

    def get(self, key):
        if key in self.map:
            self.flush_mru(key)
            return self.map[key].value
        return None

def main(net: switchyard.llnetbase.LLNetBase):
    my_interfaces = net.interfaces()
    mymacs = [intf.ethaddr for intf in my_interfaces]
    intf_table = {intf.name: intf for intf in my_interfaces}
    mac_table = LRUCache(5)

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
        mac_table.put(eth.src, intf_table[fromIface])

        if eth.dst in mymacs:
            log_info("Received a packet intended for me")
        elif eth.dst == EthAddr("ff:ff:ff:ff:ff:ff"):
            flood(fromIface, packet)
        else:
            p = mac_table.get(eth.dst)
            if p is not None:
                log_info(f"Sending packet {packet} to {p.name}")
                net.send_packet(p, packet)
            else:
                flood(fromIface, packet)

    net.shutdown()
