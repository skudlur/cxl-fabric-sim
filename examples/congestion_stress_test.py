"""
Workload Pattern Comparison Demo

Compares different workload patterns on same topology:
- Uniform random
- Zipfian (skewed)
- Hotspot (extreme skew)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core import SimulationEngine, SimulationEvent, CXL_DEVICE_LATENCY, CXL_SWITCH_LATENCY
from topology import create_topology
from workload import create_workload


def run_workload_experiment(workload_name, workload_params, topology):
    """Run single experiment with given workload"""
    
    # Create fresh engine for each experiment
    engine = SimulationEngine()
    
    # Track dropped packets
    dropped = []
    
    def handle_host_send(event):
        packet = event.packet
        host_id = event.metadata["host_id"]
        host_switch_id = topology.host_to_switch[host_id]
        host_switch = topology.switches[host_switch_id]
        arrival_port = topology.num_spines + (host_id % topology.hosts_per_leaf)
        
        success = host_switch.route_packet(packet, arrival_port, engine)
        if not success:
            dropped.append(packet)
    
    def handle_switch_transmit(event):
        switch_id = event.switch_id
        output_port = event.metadata["output_port"]
        switch = topology.switches[switch_id]
        packet = switch.transmit_packet(output_port, engine)
        
        if packet is None:
            return
        
        next_hop = get_next_hop(switch_id, output_port, packet.dst_device, topology)
        
        if next_hop == "DEVICE":
            response_time = engine.current_time + CXL_DEVICE_LATENCY
            response_event = SimulationEvent(
                timestamp=response_time,
                event_type="device_response",
                packet=packet
            )
            engine.schedule_event(response_event)
        else:
            next_switch_id, arrival_port = next_hop
            next_switch = topology.switches[next_switch_id]
            arrival_time = engine.current_time + CXL_SWITCH_LATENCY
            
            success = next_switch.route_packet(packet, arrival_port, engine)
            if not success:
                dropped.append(packet)
    
    def handle_device_response(event):
        packet = event.packet
        host = topology.hosts[packet.src_host]
        host.receive_response(packet)
        engine.stats.record_packet_completion(packet, engine.current_time)
    
    engine.register_handler("host_send", handle_host_send)
    engine.register_handler("switch_transmit", handle_switch_transmit)
    engine.register_handler("device_response", handle_device_response)
    
    # Generate workload
    workload = create_workload(workload_name, **workload_params)
    requests = workload.generate_requests(
        num_hosts=len(topology.hosts),
        num_devices=len(topology.cxl_devices),
        duration_ns=10_000,  # 10 microseconds
        requests_per_host=1000
    )
    
    # Schedule requests
    for req in requests:
        host = topology.hosts[req.host_id]
        packet = host.generate_memory_request(
            dst_device=req.device_id,
            address=req.address,
            is_read=req.is_read,
            timestamp=req.timestamp
        )
        
        event = SimulationEvent(
            timestamp=req.timestamp,
            event_type="host_send",
            packet=packet,
            metadata={"host_id": req.host_id}
        )
        engine.schedule_event(event)
    
    # Run simulation
    stats = engine.run(until=30_000)
    
    return {
        'workload': workload_name,
        'stats': stats,
        'dropped': len(dropped),
        'switches': topology.switches,
    }


def get_next_hop(switch_id, output_port, dst_device, topology):
    """Determine next hop for packet"""
    if switch_id == topology.device_to_switch[dst_device]:
        return "DEVICE"
    
    for link in topology.switch_links:
        if link[0] == switch_id and link[1] == output_port:
            return (link[2], link[3])
        if link[2] == switch_id and link[3] == output_port:
            return (link[0], link[1])
    
    raise ValueError(f"No link found for switch {switch_id} port {output_port}")


if __name__ == "__main__":
    print("="*70)
    print("CXL Fabric Workload Pattern Comparison")
    print("="*70)
    
    # Create shared topology
    print("\nCreating two-tier spine-leaf topology...")
    topology = create_topology(
        "two_tier",
        num_spines=2,
        num_leaves=3,
        hosts_per_leaf=2,
        devices_per_leaf=1,
        queue_depth=8
    )
    topology.print_topology()
    
    # Define workloads to compare
    workloads = [
        ("uniform", {}),
        ("zipfian", {"alpha": 1.0, "hot_device_fraction": 0.3}),
        ("hotspot", {"hotspot_device": 0, "hotspot_fraction": 0.9}),
    ]
    
    results = []
    
    # Run experiments
    for workload_name, params in workloads:
        print(f"\n{'='*70}")
        print(f"Running: {workload_name.upper()} workload")
        print(f"{'='*70}")
        
        # Need fresh topology for each run
        topo = create_topology(
            "two_tier",
            num_spines=2,
            num_leaves=3,
            hosts_per_leaf=2,
            devices_per_leaf=1,
            queue_depth=8
        )
        
        result = run_workload_experiment(workload_name, params, topo)
        results.append(result)
        
        print(f"\n{workload_name.upper()} Results:")
        print(f"  Packets received: {result['stats'].packets_received}")
        print(f"  Packets dropped: {result['dropped']}")
        print(f"  Avg latency: {result['stats'].avg_latency():.1f} ns")
        print(f"  P99 latency: {result['stats'].percentile_latency(99):.1f} ns")
    
    # Comparison summary
    print("\n" + "="*70)
    print("COMPARISON SUMMARY")
    print("="*70)
    print(f"\n{'Workload':<15} {'Received':<12} {'Dropped':<10} {'Avg Latency':<15} {'P99 Latency':<15}")
    print("-" * 70)
    
    for result in results:
        stats = result['stats']
        print(f"{result['workload']:<15} "
              f"{stats.packets_received:<12} "
              f"{result['dropped']:<10} "
              f"{stats.avg_latency():<15.1f} "
              f"{stats.percentile_latency(99):<15.1f}")
    
    print("\n" + "="*70)
