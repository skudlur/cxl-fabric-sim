"""
Simple CXL fabric simulation example.

Topology:
    Host 0 --\
              Switch 0 --- CXL Device 0
    Host 1 --/            CXL Device 1

Demonstrates:
- Basic packet flow through a switch
- Queue congestion under load
- Latency measurements
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core import (
    SimulationEngine, CXLSwitch, Host, TrafficGenerator,
    SimulationEvent, CXL_DEVICE_LATENCY
)


def handle_host_send(event: SimulationEvent):
    """Host sends packet to switch"""
    packet = event.packet
    host_id = event.metadata["host_id"]
    
    # Route to connected switch (port 0 for host 0, port 1 for host 1)
    arrival_port = host_id
    
    success = switch.route_packet(packet, arrival_port, engine)
    
    if not success:
        print(f"[{engine.current_time:.1f}ns] Packet {packet.packet_id} dropped at switch!")


def handle_switch_transmit(event: SimulationEvent):
    """Switch transmits packet from output queue"""
    output_port = event.metadata["output_port"]
    packet = switch.transmit_packet(output_port, engine)
    
    if packet is None:
        return
    
    # Packet reaches CXL device
    # Schedule response after device processing delay
    response_time = engine.current_time + CXL_DEVICE_LATENCY
    
    response_event = SimulationEvent(
        timestamp=response_time,
        event_type="device_response",
        packet=packet
    )
    engine.schedule_event(response_event)


def handle_device_response(event: SimulationEvent):
    """CXL device responds, packet returns to host"""
    packet = event.packet
    host = hosts[packet.src_host]
    host.receive_response(packet)
    
    # Record latency statistics
    engine.stats.record_packet_completion(packet, engine.current_time)


if __name__ == "__main__":
    print("=== Simple CXL Fabric Simulation ===\n")
    
    # Create simulation engine
    engine = SimulationEngine()
    
    # Register event handlers
    engine.register_handler("host_send", handle_host_send)
    engine.register_handler("switch_transmit", handle_switch_transmit)
    engine.register_handler("device_response", handle_device_response)
    
    # Create topology: 2 hosts, 1 switch, 2 CXL devices
    hosts = [
        Host(host_id=0, connected_switch=0),
        Host(host_id=1, connected_switch=0)
    ]
    
    switch = CXLSwitch(switch_id=0, num_ports=4, queue_depth=16)
    
    # Configure routing: devices 0,1 on ports 2,3
    switch.set_route(dst_device=0, output_port=2)
    switch.set_route(dst_device=1, output_port=3)
    
    cxl_devices = [0, 1]
    
    # Generate traffic
    print("Generating uniform traffic...")
    traffic_gen = TrafficGenerator(hosts, cxl_devices)
    traffic_gen.generate_uniform_traffic(
        sim_engine=engine,
        duration_ns=10_000,  # 10 microseconds
        requests_per_host=100
    )
    
    print(f"Scheduled {engine.stats.packets_sent} initial events\n")
    
    # Run simulation
    print("Running simulation...")
    stats = engine.run(until=20_000)  # Run for 20us
    
    # Print results
    print("\n" + "="*50)
    stats.print_summary()
    
    switch.print_status()
    traffic_gen.print_status()
    
    print("\n" + "="*50)
    print("Simulation complete! ✓")
