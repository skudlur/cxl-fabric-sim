"""Characterize congestion vs load"""

import sys
sys.path.insert(0, 'src')

from core import SimulationEngine, SimulationEvent, CXL_DEVICE_LATENCY
from topology import create_topology
from workload import create_workload


def run_load_test(load, queue_depth=8):
    engine = SimulationEngine()
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
        next_hop = get_next_hop(switch_id, output_port, packet.dst_device)
        if next_hop == "DEVICE":
            engine.schedule_event(SimulationEvent(
                timestamp=engine.current_time + CXL_DEVICE_LATENCY,
                event_type="device_response",
                packet=packet
            ))
        else:
            next_switch_id, arrival_port = next_hop
            topology.switches[next_switch_id].route_packet(packet, arrival_port, engine)
    
    def handle_device_response(event):
        packet = event.packet
        topology.hosts[packet.src_host].receive_response(packet)
        engine.stats.record_packet_completion(packet, engine.current_time)
    
    def get_next_hop(switch_id, output_port, dst_device):
        if switch_id == topology.device_to_switch[dst_device]:
            return "DEVICE"
        for link in topology.switch_links:
            if link[0] == switch_id and link[1] == output_port:
                return (link[2], link[3])
            if link[2] == switch_id and link[3] == output_port:
                return (link[0], link[1])
        raise ValueError(f"No link")
    
    engine.register_handler("host_send", handle_host_send)
    engine.register_handler("switch_transmit", handle_switch_transmit)
    engine.register_handler("device_response", handle_device_response)
    
    topology = create_topology("two_tier", num_spines=2, num_leaves=3, 
                               hosts_per_leaf=2, devices_per_leaf=1, 
                               queue_depth=queue_depth)
    
    workload = create_workload("hotspot", hotspot_device=0, hotspot_fraction=0.9)
    requests = workload.generate_requests(
        num_hosts=4, num_devices=1, duration_ns=10_000, 
        requests_per_host=load
    )
    
    for req in requests:
        host = topology.hosts[req.host_id]
        packet = host.generate_memory_request(req.device_id, req.address, 
                                              timestamp=req.timestamp)
        engine.schedule_event(SimulationEvent(
            timestamp=req.timestamp, event_type="host_send",
            packet=packet, metadata={"host_id": req.host_id}
        ))
    
    stats = engine.run(until=30_000)
    return stats.packets_received, len(dropped), stats.avg_latency()


print("Load (req/host) | Total Offered | Received | Dropped | Drop % | Latency")
print("-" * 80)

for load in [50, 100, 200, 300, 400, 500, 750, 1000, 1500]:
    rx, drop, lat = run_load_test(load)
    total = load * 4
    drop_pct = (drop / total * 100) if total > 0 else 0
    print(f"{load:15} | {total:13} | {rx:8} | {drop:7} | {drop_pct:5.1f}% | {lat:6.1f}ns")
