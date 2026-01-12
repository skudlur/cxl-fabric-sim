"""
CXL Switch model with proper queue-driven transmission.
"""

from collections import deque
from dataclasses import dataclass
from typing import Optional

from .packet import CXLPacket, SimulationEvent, CXL_SWITCH_LATENCY


@dataclass
class SwitchPort:
    """Single port on a CXL switch"""
    port_id: int
    max_queue_depth: int = 32
    bandwidth_gbps: float = 64.0

    def __post_init__(self):
        self.queue = deque()
        self.packets_sent = 0
        self.packets_dropped = 0
        self.total_queue_time = 0.0
        self.is_transmitting = False  # Is port currently busy?
        self.next_available_time = 0.0

    def enqueue(self, packet: CXLPacket) -> bool:
        """Enqueue packet. Returns True if successful."""
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
        return len(self.queue) / self.max_queue_depth

    @property
    def has_packets(self) -> bool:
        return len(self.queue) > 0


class CXLSwitch:
    """Models a CXL fabric switch with proper queueing."""

    def __init__(self, switch_id: int, num_ports: int, queue_depth: int = 32):
        self.switch_id = switch_id
        self.num_ports = num_ports
        self.ports = [SwitchPort(i, queue_depth) for i in range(num_ports)]
        self.routing_table = {}
        self.total_packets_processed = 0
        self.total_packets_dropped = 0

    def set_route(self, dst_device: int, output_port: int):
        if output_port >= self.num_ports:
            raise ValueError(f"Invalid port {output_port}")
        self.routing_table[dst_device] = output_port

    def route_packet(self, packet: CXLPacket, arrival_port: int, sim_engine) -> bool:
        """
        Route incoming packet to output port.
        Only schedules transmission if queue was empty.
        """
        self.total_packets_processed += 1

        if packet.dst_device not in self.routing_table:
            self.total_packets_dropped += 1
            return False

        output_port_id = self.routing_table[packet.dst_device]
        port = self.ports[output_port_id]

        # Check if queue was empty before enqueue
        was_empty = not port.has_packets

        # Try to enqueue
        if not port.enqueue(packet):
            self.total_packets_dropped += 1
            return False

        # Only schedule transmission if this is the first packet in queue
        if was_empty and not port.is_transmitting:
            self._schedule_port_transmission(output_port_id, sim_engine)

        return True

    def _schedule_port_transmission(self, output_port_id: int, sim_engine):
        """Schedule transmission of head packet from port queue."""
        port = self.ports[output_port_id]

        if not port.has_packets:
            port.is_transmitting = False
            return

        port.is_transmitting = True

        # Switch processing delay + serialization
        current_time = sim_engine.current_time

        # Ensure we don't schedule in the past
        if port.next_available_time > current_time:
            tx_start = port.next_available_time
        else:
            tx_start = current_time + CXL_SWITCH_LATENCY

        # Schedule the transmission event
        event = SimulationEvent(
            timestamp=tx_start,
            event_type="switch_transmit",
            packet=None,  # Will dequeue in handler
            switch_id=self.switch_id,
            metadata={"output_port": output_port_id}
        )
        sim_engine.schedule_event(event)

    def transmit_packet(self, output_port: int, sim_engine) -> Optional[CXLPacket]:
        """
        Transmit head packet from queue.
        Then schedule next packet if queue not empty.
        """
        port = self.ports[output_port]
        packet = port.dequeue()

        if packet:
            packet.route.append(self.switch_id)

            # Calculate serialization delay for this packet
            serialization_ns = (packet.size * 8) / (port.bandwidth_gbps * 1e9) * 1e9

            # Update when port will be free
            port.next_available_time = sim_engine.current_time + serialization_ns

            # If more packets in queue, schedule next transmission
            if port.has_packets:
                self._schedule_port_transmission(output_port, sim_engine)
            else:
                port.is_transmitting = False
        else:
            port.is_transmitting = False

        return packet

    def get_congestion_metrics(self) -> dict:
        return {
            "switch_id": self.switch_id,
            "total_processed": self.total_packets_processed,
            "total_dropped": self.total_packets_dropped,
            "drop_rate": self.total_packets_dropped / max(1, self.total_packets_processed),
            "port_occupancies": [p.occupancy for p in self.ports],
            "avg_occupancy": sum(p.occupancy for p in self.ports) / len(self.ports),
        }

    def print_status(self):
        print(f"\nSwitch {self.switch_id}:")
        print(f"  Processed: {self.total_packets_processed}, Dropped: {self.total_packets_dropped}")
        for i, port in enumerate(self.ports):
            print(f"  Port {i}: queue={len(port.queue)}/{port.max_queue_depth}, "
                  f"sent={port.packets_sent}, dropped={port.packets_dropped}")
