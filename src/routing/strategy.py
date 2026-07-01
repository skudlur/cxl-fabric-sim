"""
Routing strategies for CXL fabric switches.
"""
import random
from typing import List
from src.core.packet import CXLPacket

class RoutingStrategy:
    """Base class for routing strategies."""
    def get_output_port(self, switch, packet: CXLPacket, available_ports: List[int]) -> int:
        """
        Determine which output port to use for the given packet.
        
        Args:
            switch: The CXLSwitch making the routing decision
            packet: The packet to route
            available_ports: List of valid output ports for the packet's destination
            
        Returns:
            Selected output port index
        """
        raise NotImplementedError

class StaticRouting(RoutingStrategy):
    """Always picks the first available port (e.g., spine 0)."""
    def get_output_port(self, switch, packet: CXLPacket, available_ports: List[int]) -> int:
        if not available_ports:
            raise ValueError(f"No available ports to route packet {packet.packet_id}")
        return available_ports[0]

class ECMPRouting(RoutingStrategy):
    """
    Equal-Cost Multi-Path routing.
    Hashes flow parameters to consistently route same flow on same path.
    """
    def get_output_port(self, switch, packet: CXLPacket, available_ports: List[int]) -> int:
        if not available_ports:
            raise ValueError(f"No available ports to route packet {packet.packet_id}")
        
        # Flow is defined by source, destination, and address
        flow_hash = hash((packet.src_host, packet.dst_device, packet.address))
        
        # Pick port based on hash
        idx = flow_hash % len(available_ports)
        return available_ports[idx]

class WeightedRouting(RoutingStrategy):
    """
    Load-aware routing.
    Picks the port with the lowest current queue occupancy.
    """
    def get_output_port(self, switch, packet: CXLPacket, available_ports: List[int]) -> int:
        if not available_ports:
            raise ValueError(f"No available ports to route packet {packet.packet_id}")

        # Find port with minimum occupancy
        best_port = available_ports[0]
        min_occupancy = float('inf')

        for port_idx in available_ports:
            port = switch.ports[port_idx]
            if port.egress_occupancy < min_occupancy:
                min_occupancy = port.egress_occupancy
                best_port = port_idx

        return best_port


class OccupancyWeightedECMPRouting(RoutingStrategy):
    """
    Occupancy-weighted ECMP routing.

    Uses the ECMP flow hash to pick a candidate port, preserving per-flow
    path affinity under light load. Deviates to the least-loaded port only
    when the hash-selected port's egress occupancy exceeds the minimum by
    more than `occupancy_threshold` flits, providing hysteresis that prevents
    per-packet route flapping.

    Hysteresis parameter must be fixed before the sweep and not tuned per
    data point — see experiment spec Section 4.

    Args:
        occupancy_threshold: Flit-count delta above the minimum occupancy
            required before overriding the hash selection (default 2).
    """

    def __init__(self, occupancy_threshold: int = 2):
        self.occupancy_threshold = occupancy_threshold

    def get_output_port(self, switch, packet: CXLPacket, available_ports: List[int]) -> int:
        if not available_ports:
            raise ValueError(f"No available ports to route packet {packet.packet_id}")

        if len(available_ports) == 1:
            return available_ports[0]

        # ECMP hash: same (src, dst, address) always maps to the same candidate
        flow_hash = hash((packet.src_host, packet.dst_device, packet.address))
        candidate_port = available_ports[flow_hash % len(available_ports)]

        # Find the minimum-occupancy port
        min_port = min(available_ports, key=lambda p: switch.ports[p].egress_occupancy)
        min_occupancy = switch.ports[min_port].egress_occupancy
        candidate_occupancy = switch.ports[candidate_port].egress_occupancy

        # Only deviate from hash if candidate is meaningfully more congested
        if candidate_occupancy - min_occupancy > self.occupancy_threshold:
            return min_port
        return candidate_port
