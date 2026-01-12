"""
Topology builder for CXL fabric configurations.

Implements common CXL fabric topologies:
- Single-tier (all hosts connect to one switch)
- Two-tier spine-leaf (datacenter-style)
- Custom topologies
"""

from typing import List, Dict, Tuple
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core import CXLSwitch, Host


class FabricTopology:
    """Base class for CXL fabric topologies"""
    
    def __init__(self):
        self.switches: List[CXLSwitch] = []
        self.hosts: List[Host] = []
        self.cxl_devices: List[int] = []
        
        # Connectivity maps
        self.host_to_switch: Dict[int, int] = {}  # host_id -> switch_id
        self.device_to_switch: Dict[int, int] = {}  # device_id -> switch_id
        self.switch_links: List[Tuple[int, int, int, int]] = []  # (sw1, port1, sw2, port2)
    
    def build(self):
        """Override in subclasses to construct topology"""
        raise NotImplementedError
    
    def configure_routing(self):
        """Configure routing tables for all switches"""
        raise NotImplementedError
    
    def print_topology(self):
        """Print topology summary"""
        print(f"\n{'='*50}")
        print(f"Topology: {self.__class__.__name__}")
        print(f"  Switches: {len(self.switches)}")
        print(f"  Hosts: {len(self.hosts)}")
        print(f"  CXL Devices: {len(self.cxl_devices)}")
        print(f"  Switch links: {len(self.switch_links)}")
        print(f"{'='*50}\n")


class SingleTierTopology(FabricTopology):
    r"""
    Simple single-switch topology:
    
        Host0  Host1  Host2  Host3
          |      |      |      |
          +------+------+------+
                 |
              Switch0
                 |
          +------+------+------+
          |      |      |      |
        Dev0   Dev1   Dev2   Dev3
    """
    
    def __init__(self, num_hosts: int, num_devices: int, queue_depth: int = 32):
        super().__init__()
        self.num_hosts = num_hosts
        self.num_devices = num_devices
        self.queue_depth = queue_depth
    
    def build(self):
        """Construct single-tier topology"""
        # Create switch with enough ports
        num_ports = self.num_hosts + self.num_devices
        switch = CXLSwitch(switch_id=0, num_ports=num_ports, queue_depth=self.queue_depth)
        self.switches.append(switch)
        
        # Create hosts (connected to ports 0 to num_hosts-1)
        for i in range(self.num_hosts):
            host = Host(host_id=i, connected_switch=0)
            self.hosts.append(host)
            self.host_to_switch[i] = 0
        
        # Create devices (connected to ports num_hosts onwards)
        self.cxl_devices = list(range(self.num_devices))
        for i, dev_id in enumerate(self.cxl_devices):
            port = self.num_hosts + i
            self.device_to_switch[dev_id] = 0
        
        return self
    
    def configure_routing(self):
        """Configure routing table for single switch"""
        switch = self.switches[0]
        
        # Route each device to its port
        for i, dev_id in enumerate(self.cxl_devices):
            output_port = self.num_hosts + i
            switch.set_route(dst_device=dev_id, output_port=output_port)


class TwoTierTopology(FabricTopology):
    r"""
    Two-tier spine-leaf topology:
    
           Spine0        Spine1
             |  \        /  |
             |   \      /   |
             |    \    /    |
             |     \  /     |
          Leaf0   Leaf1   Leaf2
           / \     / \     / \
          H0 H1   H2 H3   D0 D1
    
    Hosts connect to leaf switches
    Devices connect to dedicated device leaf switches
    All leaf switches connect to all spine switches (full mesh)
    """
    
    def __init__(
        self, 
        num_spines: int = 2,
        num_leaves: int = 3,
        hosts_per_leaf: int = 2,
        devices_per_leaf: int = 2,
        queue_depth: int = 32
    ):
        super().__init__()
        self.num_spines = num_spines
        self.num_leaves = num_leaves
        self.hosts_per_leaf = hosts_per_leaf
        self.devices_per_leaf = devices_per_leaf
        self.queue_depth = queue_depth
        
        # Track which leaves have hosts vs devices
        self.host_leaves = []
        self.device_leaves = []
    
    def build(self):
        """Construct two-tier topology"""
        # Create spine switches
        spine_ports = self.num_leaves  # One port per leaf
        for i in range(self.num_spines):
            spine = CXLSwitch(
                switch_id=i, 
                num_ports=spine_ports,
                queue_depth=self.queue_depth
            )
            self.switches.append(spine)
        
        # Create leaf switches
        # Each leaf needs: spine_ports + host/device ports
        leaf_ports = self.num_spines + max(self.hosts_per_leaf, self.devices_per_leaf)
        
        for i in range(self.num_leaves):
            leaf_id = self.num_spines + i
            leaf = CXLSwitch(
                switch_id=leaf_id,
                num_ports=leaf_ports,
                queue_depth=self.queue_depth
            )
            self.switches.append(leaf)
            
            # First half of leaves get hosts, second half get devices
            if i < self.num_leaves // 2 + 1:
                self.host_leaves.append(leaf_id)
            else:
                self.device_leaves.append(leaf_id)
        
        # Connect spines to leaves
        for spine_idx in range(self.num_spines):
            for leaf_idx in range(self.num_leaves):
                spine_port = leaf_idx
                leaf_id = self.num_spines + leaf_idx
                leaf_port = spine_idx
                
                self.switch_links.append((spine_idx, spine_port, leaf_id, leaf_port))
        
        # Create hosts on host leaves
        host_id = 0
        for leaf_id in self.host_leaves:
            for i in range(self.hosts_per_leaf):
                host = Host(host_id=host_id, connected_switch=leaf_id)
                self.hosts.append(host)
                self.host_to_switch[host_id] = leaf_id
                host_id += 1
        
        # Create devices on device leaves
        dev_id = 0
        for leaf_id in self.device_leaves:
            for i in range(self.devices_per_leaf):
                self.cxl_devices.append(dev_id)
                self.device_to_switch[dev_id] = leaf_id
                dev_id += 1
        
        return self
    
    def configure_routing(self):
        """
        Configure routing tables for two-tier topology.
        Uses simple shortest-path routing through spines.
        """
        # For each device, configure paths from all switches
        for dev_id in self.cxl_devices:
            device_leaf = self.device_to_switch[dev_id]
            
            # Find which port the device is on
            devices_on_leaf = [d for d in self.cxl_devices if self.device_to_switch[d] == device_leaf]
            device_index = devices_on_leaf.index(dev_id)
            device_port = self.num_spines + device_index
            
            # Configure device leaf to route locally
            leaf_switch = self.switches[device_leaf]
            leaf_switch.set_route(dst_device=dev_id, output_port=device_port)
            
            # Configure spine switches to route to device leaf
            for spine_idx in range(self.num_spines):
                spine = self.switches[spine_idx]
                # Find port that connects to device leaf
                for link in self.switch_links:
                    if link[0] == spine_idx and link[2] == device_leaf:
                        spine_port = link[1]
                        spine.set_route(dst_device=dev_id, output_port=spine_port)
                        break
            
            # Configure host leaves to route through spine 0 (simple policy)
            for leaf_id in self.host_leaves:
                leaf = self.switches[leaf_id]
                # Route to spine 0
                leaf.set_route(dst_device=dev_id, output_port=0)


def create_topology(topology_type: str, **kwargs) -> FabricTopology:
    """
    Factory function to create topologies.
    
    Args:
        topology_type: "single" or "two_tier"
        **kwargs: Topology-specific parameters
    
    Returns:
        Configured FabricTopology instance
    """
    if topology_type == "single":
        topo = SingleTierTopology(**kwargs)
    elif topology_type == "two_tier":
        topo = TwoTierTopology(**kwargs)
    else:
        raise ValueError(f"Unknown topology type: {topology_type}")
    
    topo.build()
    topo.configure_routing()
    return topo
