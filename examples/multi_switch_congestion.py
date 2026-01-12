"""
Multi-switch CXL fabric simulation demonstrating congestion.

Topology: Two-tier spine-leaf
- 2 spine switches
- 3 leaf switches
- 4 hosts (2 per host-leaf)
- 2 CXL devices (on device-leaf)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core import SimulationEngine, SimulationEvent, CXL_DEVICE_LATENCY, CXL_SWITCH_LATENCY
from topology import create_topology


def handle_host_send(event: SimulationEvent):
    """Host sends packet into fabric"""
    packet = event.packet
    host_id = event.metadata["host_id"]
    
    # Find which switch this host connects to
    host_switch_id = topology.host_to_switch[host_id]
    host_switch = topology.switches[host_switch_id]
    
    # Host connects to port after spine ports
    arrival_port = topology.num_spines + (host_id % topology.hosts_per_leaf)
    
    success = host_switch.route_packet(packet, arrival_port, engine)
    
    if not success:
        dropped_packets.append((packet, "host_switch"))


def handle_switch_transmit(event: SimulationEvent):
    """Switch transmits packet from output queue"""
    switch_id = event.switch_id
    output_port = event.metadata["output_port"]
    
    switch = topology.switches[switch_id]
    packet = switch.transmit_packet(output_port, engine)
    
    if packet is None:
        return
    
    # Determine next hop
    next_hop = get_next_hop(switch_id, output_port, packet.dst_device)
    
    if next_hop == "DEVICE":
        # Packet reached device, schedule response
        response_time = engine.current_time + CXL_DEVICE_LATENCY
        response_event = SimulationEvent(
            timestamp=response_time,
            event_type="device_response",
            packet=packet
        )
        engine.schedule_event(response_event)
    else:
        # Packet goes to another switch
        next_switch_id, arrival_port = next_hop
        next_switch = topology.switches[next_switch_id]
        
        # Add inter-switch latency
        arrival_time = engine.current_time + CXL_SWITCH_LATENCY
        
        # Try to route at next switch
        success = next_switch.route_packet(packet, arrival_port, engine)
        
        if not success:
            dropped_packets.append((packet, f"switch_{next_switch_id}"))


def get_next_hop(switch_id, output_port, dst_device):
    """
    Determine where packet goes after leaving switch.
    
    Returns:
        "DEVICE" if packet reached destination
        (next_switch_id, arrival_port) if going to another switch
    """
    # Check if this is the device's switch
    if switch_id == topology.device_to_switch[dst_device]:
        return "DEVICE"
    
    # Find which switch this port connects to
    # Links are bidirectional, check both directions
    for link in topology.switch_links:
        # Forward direction: sw1 -> sw2
        if link[0] == switch_id and link[1] == output_port:
            return (link[2], link[3])
        # Reverse direction: sw2 -> sw1
        if link[2] == switch_id and link[3] == output_port:
            return (link[0], link[1])
    
    raise ValueError(f"No link found for switch {switch_id} port {output_port}")


def handle_device_response(event: SimulationEvent):
    """CXL device responds"""
    packet = event.packet
    host = topology.hosts[packet.src_host]
    host.receive_response(packet)
    
    engine.stats.record_packet_completion(packet, engine.current_time)


if __name__ == "__main__":
    print("="*60)
    print("Multi-Switch CXL Fabric Congestion Simulation")
    print("="*60)
    
    # Create simulation engine
    engine = SimulationEngine()
    
    # Register handlers
    engine.register_handler("host_send", handle_host_send)
    engine.register_handler("switch_transmit", handle_switch_transmit)
    engine.register_handler("device_response", handle_device_response)
    
    # Create two-tier topology
    print("\nBuilding two-tier spine-leaf topology...")
    topology = create_topology(
        "two_tier",
        num_spines=2,
        num_leaves=3,
        hosts_per_leaf=2,
        devices_per_leaf=1,
        queue_depth=16  # Small queue to induce congestion
    )
    topology.print_topology()
    
    dropped_packets = []
    
    # Generate hotspot traffic: all hosts -> Device 0
    print("Generating hotspot traffic (all hosts -> Device 0)...\n")
    
    hotspot_device = 0
    requests_per_host = 50
    duration_ns = 5_000  # 5 microseconds
    
    for host in topology.hosts:
        interval = duration_ns / requests_per_host
        
        for i in range(requests_per_host):
            timestamp = i * interval
            
            packet = host.generate_memory_request(
                dst_device=hotspot_device,
                address=0x1000 * i,
                timestamp=timestamp
            )
            
            event = SimulationEvent(
                timestamp=timestamp,
                event_type="host_send",
                packet=packet,
                metadata={"host_id": host.host_id}
            )
            engine.schedule_event(event)
    
    # Run simulation
    print("Running simulation...")
    stats = engine.run(until=20_000)  # Run for 20 microseconds
    
    # Print results
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    
    stats.print_summary()
    
    print("\n--- Switch Statistics ---")
    for switch in topology.switches:
        metrics = switch.get_congestion_metrics()
        print(f"\nSwitch {metrics['switch_id']}:")
        print(f"  Processed: {metrics['total_processed']}")
        print(f"  Dropped: {metrics['total_dropped']}")
        print(f"  Drop rate: {metrics['drop_rate']:.1%}")
        print(f"  Avg queue occupancy: {metrics['avg_occupancy']:.1%}")
    
    print("\n--- Traffic Statistics ---")
    for host in topology.hosts:
        print(f"Host {host.host_id}: sent={host.packets_sent}, "
              f"received={host.packets_received}, outstanding={host.num_outstanding}")
    
    print("\n--- Congestion Analysis ---")
    print(f"Total packets dropped: {len(dropped_packets)}")
    if dropped_packets:
        drop_locations = {}
        for _, location in dropped_packets:
            drop_locations[location] = drop_locations.get(location, 0) + 1
        
        print("Drop locations:")
        for location, count in sorted(drop_locations.items()):
            print(f"  {location}: {count} packets")
    
    print("\n" + "="*60)
