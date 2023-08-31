from switchyard.lib.userlib import *
from random import *

def new_packet(hwsrc, hwdst, ipsrc, ipdst, reply=False):
    ether = Ethernet(src=hwsrc, dst=hwdst, ethertype=EtherType.IP)
    ippkt = IPv4(src=ipsrc, dst=ipdst, protocol=IPProtocol.ICMP, ttl=32)
    icmppkt = ICMP()
    if reply:
        icmppkt.icmptype = ICMPType.EchoReply
    else:
        icmppkt.icmptype = ICMPType.EchoRequest
    return ether + ippkt + icmppkt

ETH_RANGE = range(50)
MAC_RANGE = range(100)

def get_eth_name(i):
    assert i >= 0
    return f'eth{i}'

def get_eth_mac(i):
    assert i >= 0
    return '10:00:00:00:00:{:02x}'.format(i)

def get_mac(i):
    assert 0 <= i < 65536
    return '20:00:00:00:{:02x}:{:02x}'.format(i // 256, i % 256)

def send_packet(test, src, dst, eth):
    pkt = new_packet(get_mac(src), get_mac(dst), "0.0.0.0", "0.0.0.0")
    test.expect(PacketInputEvent(get_eth_name(eth), pkt, display=Ethernet), "send")
    return pkt

def recv_packet(test, pkt, eth):
    test.expect(PacketOutputEvent(get_eth_name(eth), pkt, display=Ethernet), "recv")

def flood_packet(test, pkt, in_eth):
    test.expect(PacketOutputEvent(
        *[x for y in zip([get_eth_name(eth) for eth in ETH_RANGE if eth != in_eth], [pkt] * (len(ETH_RANGE) - 1)) 
            for x in y],
        display=Ethernet), "flood")

def test_switch():
    s = TestScenario("switch tests")
    [s.add_interface(get_eth_name(i), get_eth_mac(i)) for i in ETH_RANGE]
    mac = {}

    for _ in range(500):
        src, dst = sample(MAC_RANGE, 2)
        mac[src] = choice(ETH_RANGE)
        pkt = send_packet(s, src, dst, mac[src])
        if dst in mac:
            recv_packet(s, pkt, mac[dst])
        else:
            flood_packet(s, pkt, mac[src])

    return s


scenario = test_switch()
