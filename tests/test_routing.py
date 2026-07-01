"""Tests for routing strategies."""

import pytest
from src.core.switch import CXLSwitch
from src.core.packet import CXLPacket, CXLTransactionType
from src.routing.strategy import StaticRouting, ECMPRouting, WeightedRouting, OccupancyWeightedECMPRouting

def test_ecmp_routing():
    switch = CXLSwitch(switch_id=0, num_ports=4)
    strategy = ECMPRouting()
    
    packet1 = CXLPacket(1, CXLTransactionType.MEM_READ, src_host=0, dst_device=0, address=0x1000)
    packet2 = CXLPacket(2, CXLTransactionType.MEM_READ, src_host=0, dst_device=0, address=0x1000)
    packet3 = CXLPacket(3, CXLTransactionType.MEM_READ, src_host=1, dst_device=0, address=0x2000)
    
    # Packets in same flow should hash to same port
    port1 = strategy.get_output_port(switch, packet1, [0, 1])
    port2 = strategy.get_output_port(switch, packet2, [0, 1])
    assert port1 == port2

def test_weighted_routing():
    switch = CXLSwitch(switch_id=0, num_ports=4)
    strategy = WeightedRouting()

    packet = CXLPacket(1, CXLTransactionType.MEM_READ, src_host=0, dst_device=0, address=0x1000)

    # Enqueue packets on port 0 to make it congested
    switch.ports[0].enqueue_egress(packet)
    switch.ports[0].enqueue_egress(packet)

    # Port 1 is empty, so it should be chosen
    port = strategy.get_output_port(switch, packet, [0, 1])
    assert port == 1


def _ecmp_candidate(packet, available_ports):
    """Return the port that pure ECMP would pick for this packet."""
    flow_hash = hash((packet.src_host, packet.dst_device, packet.address))
    return available_ports[flow_hash % len(available_ports)]


def test_occupancy_weighted_ecmp_flow_consistency():
    """Same-flow packets use the ECMP hash port when occupancies are equal."""
    switch = CXLSwitch(switch_id=0, num_ports=4)
    strategy = OccupancyWeightedECMPRouting(occupancy_threshold=2)
    available = [0, 1]

    packet1 = CXLPacket(1, CXLTransactionType.MEM_READ, src_host=0, dst_device=0, address=0x1000)
    packet2 = CXLPacket(2, CXLTransactionType.MEM_READ, src_host=0, dst_device=0, address=0x1000)

    port1 = strategy.get_output_port(switch, packet1, available)
    port2 = strategy.get_output_port(switch, packet2, available)

    # Same flow key → same port every time
    assert port1 == port2
    # With equal (zero) occupancy, must agree with pure ECMP
    assert port1 == _ecmp_candidate(packet1, available)


def test_occupancy_weighted_ecmp_deviates_under_congestion():
    """When ECMP candidate is overloaded beyond threshold, pick the lighter port."""
    switch = CXLSwitch(switch_id=0, num_ports=4)
    strategy = OccupancyWeightedECMPRouting(occupancy_threshold=2)
    available = [0, 1]

    packet = CXLPacket(1, CXLTransactionType.MEM_READ, src_host=0, dst_device=0, address=0x1000)
    candidate = _ecmp_candidate(packet, available)
    other = 1 - candidate  # the non-candidate port

    # Load the candidate port beyond the threshold
    for _ in range(5):
        switch.ports[candidate].enqueue_egress(packet)

    port = strategy.get_output_port(switch, packet, available)
    assert port == other, "should deviate to the less-loaded port"


def test_occupancy_weighted_ecmp_hysteresis():
    """Small occupancy delta (within threshold) does not override the hash."""
    switch = CXLSwitch(switch_id=0, num_ports=4)
    strategy = OccupancyWeightedECMPRouting(occupancy_threshold=2)
    available = [0, 1]

    packet = CXLPacket(1, CXLTransactionType.MEM_READ, src_host=0, dst_device=0, address=0x1000)
    candidate = _ecmp_candidate(packet, available)

    # Load the candidate port by exactly the threshold (delta == threshold, not >)
    for _ in range(2):
        switch.ports[candidate].enqueue_egress(packet)

    port = strategy.get_output_port(switch, packet, available)
    assert port == candidate, "delta equal to threshold should not trigger deviation"
