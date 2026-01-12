"""
CXL Switch model with queuing and congestion control.

Models a CXL fabric switch with:
- Per-port input/output queues
- Backpressure handling
- Configurable queue depths
- Basic congestion metrics
"""

from collections import deque
from dataclasses import dataclass
from typing import Optional

from .packet import CXLPacket, SimulationEvent, CXL_SWITCH_LATENCY


@dataclass
class SwitchPort:
    """Single port on a CXL switch"""
    port_id: int
    max_queue_depth: int = 32  # Max packets in queue
    bandwidth_gbps: float = 64.0  # PCIe Gen5 x16
    
    def __post_init__(self):
        self.queue = deque()
        self.packets_sent = 0
        self.packets_dropped = 0
        self.total_queue_time = 0.0
    
    def enqueue(self, packet: CXLPacket) -> bool:
        """
        Attempt to enqueue packet.
        Returns True if successful, False if dropped due to full queue.
        """
        if len(self.queue) >= self.max_queue_depth:
            self.packets_dropped += 1
            return False
        
        self.queue.append(packet)
        return True
    
    def dequeue(self) -> Optional[CXLPacket]:
        """Remove and return head packet"""
        if self.queue:
            self.packets_sent += 1
            return self.queue.popleft()
        return None
    
    @property
    def is_full(self) -> bool:
        return len(self.queue) >= self.max_queue_depth
    
    @property
    def occupancy(self) -> float:
        """Queue occupancy as fraction of max depth"""
        return len(self.queue) / self.max_queue_depth


class CXLSwitch:
    """
    Models a CXL fabric switch.
    
    Handles packet routing, queuing, and congestion.
    """
    
    def __init__(self, switch_id: int, num_ports: int, queue_depth: int = 32):
        self.switch_id = switch_id
        self.num_ports = num_ports
        self.ports = [SwitchPort(i, queue_depth) for i in range(num_ports)]
        
        # Routing table: dst_device -> output_port
        self.routing_table = {}
        
        # Congestion tracking
        self.total_packets_processed = 0
        self.total_packets_dropped = 0
        
    def set_route(self, dst_device: int, output_port: int):
        """Configure routing table entry"""
        if output_port >= self.num_ports:
            raise ValueError(f"Invalid port {output_port} for switch with {self.num_ports} ports")
        self.routing_table[dst_device] = output_port
    
    def route_packet(self, packet: CXLPacket, arrival_port: int, sim_engine) -> bool:
        """
        Route incoming packet to appropriate output port.
        
        Returns True if enqueued successfully, False if dropped.
        """
        self.total_packets_processed += 1
        
        # Look up output port
        if packet.dst_device not in self.routing_table:
            print(f"WARNING: No route for device {packet.dst_device} in switch {self.switch_id}")
            self.total_packets_dropped += 1
            return False
        
        output_port = self.routing_table[packet.dst_device]
        port = self.ports[output_port]
        
        # Try to enqueue
        if not port.enqueue(packet):
            self.total_packets_dropped += 1
            return False
        
        # Schedule transmission from this port
        # Transmission time = switch latency + serialization delay
        tx_time = sim_engine.current_time + CXL_SWITCH_LATENCY
        
        event = SimulationEvent(
            timestamp=tx_time,
            event_type="switch_transmit",
            packet=packet,
            switch_id=self.switch_id,
            metadata={"output_port": output_port}
        )
        sim_engine.schedule_event(event)
        
        return True
    
    def transmit_packet(self, output_port: int, sim_engine) -> Optional[CXLPacket]:
        """
        Transmit packet from output queue.
        
        Returns the transmitted packet or None if queue empty.
        """
        port = self.ports[output_port]
        packet = port.dequeue()
        
        if packet:
            # Add this switch to the packet's route history
            packet.route.append(self.switch_id)
        
        return packet
    
    def get_congestion_metrics(self) -> dict:
        """Return current congestion state"""
        return {
            "switch_id": self.switch_id,
            "total_processed": self.total_packets_processed,
            "total_dropped": self.total_packets_dropped,
            "drop_rate": self.total_packets_dropped / max(1, self.total_packets_processed),
            "port_occupancies": [p.occupancy for p in self.ports],
            "avg_occupancy": sum(p.occupancy for p in self.ports) / len(self.ports),
        }
    
    def print_status(self):
        """Print current switch state"""
        print(f"\nSwitch {self.switch_id}:")
        print(f"  Processed: {self.total_packets_processed}, Dropped: {self.total_packets_dropped}")
        for i, port in enumerate(self.ports):
            print(f"  Port {i}: queue={len(port.queue)}/{port.max_queue_depth}, "
                  f"sent={port.packets_sent}, dropped={port.packets_dropped}")
