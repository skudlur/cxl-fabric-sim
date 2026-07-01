"""Per-run result serialization and load parameterization utilities."""

import json
import uuid
import time
from pathlib import Path
from typing import Optional

from src.core.engine import SimulationStats


def compute_link_metrics(topology) -> dict:
    """Derive per-link utilization stats from all switch port occupancies."""
    occupancies = []
    for switch in topology.switches:
        metrics = switch.get_congestion_metrics()
        occupancies.extend(metrics["port_occupancies"])

    if not occupancies:
        return {"link_util_variance": 0.0, "link_util_max_min_delta": 0.0}

    mean = sum(occupancies) / len(occupancies)
    variance = sum((x - mean) ** 2 for x in occupancies) / len(occupancies)
    return {
        "link_util_variance": variance,
        "link_util_max_min_delta": max(occupancies) - min(occupancies),
    }


def write_run_result(
    stats: SimulationStats,
    topology,
    policy: str,
    offered_load: float,
    seed: int,
    wall_clock_seconds: float,
    output_path: str,
    run_id: Optional[str] = None,
    topology_name: str = "spine_leaf",
    failure_reason: Optional[str] = None,
) -> dict:
    """
    Assemble a per-run result record matching the spec Section 5 JSON schema
    and write it to `output_path`.

    Returns the record dict.
    """
    if run_id is None:
        run_id = str(uuid.uuid4())

    status = "FAILED" if failure_reason else "OK"

    total_drops = sum(
        switch.total_packets_dropped
        + sum(p.packets_dropped for p in switch.ports)
        for switch in topology.switches
    )

    link_metrics = compute_link_metrics(topology)

    record = {
        "run_id": run_id,
        "topology": topology_name,
        "policy": policy,
        "offered_load": offered_load,
        "seed": seed,
        "status": status,
        "failure_reason": failure_reason,
        "wall_clock_seconds": wall_clock_seconds,
        "metrics": {
            "latency_p50_ns": stats.percentile_latency(50),
            "latency_p99_ns": stats.percentile_latency(99),
            "latency_p999_ns": stats.percentile_latency(99.9),
            "latency_mean_ns": stats.avg_latency(),
            "link_util_variance": link_metrics["link_util_variance"],
            "link_util_max_min_delta": link_metrics["link_util_max_min_delta"],
            "packets_dropped": total_drops,
        },
    }

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(record, f, indent=2)

    return record


def load_to_requests(
    utilization: float,
    duration_ns: float,
    bandwidth_gbps: float = 64.0,
    packet_size_bytes: int = 64,
) -> int:
    """
    Translate a target link utilization fraction to requests_per_host.

    Args:
        utilization: Target fraction of link capacity (0.0–1.0).
        duration_ns: Simulation window in nanoseconds.
        bandwidth_gbps: Per-link bandwidth (default 64 Gbps for CXL).
        packet_size_bytes: Packet size (default 64 bytes = 1 CXL flit).

    Returns:
        Integer requests_per_host to pass to run_workload().

    Example:
        # 10-point sweep from 10% to 100% at 100 µs window
        load_points = [load_to_requests(u/10, 100_000) for u in range(1, 11)]
    """
    bits_per_packet = packet_size_bytes * 8
    packets_at_full = bandwidth_gbps * 1e9 * (duration_ns * 1e-9) / bits_per_packet
    return max(1, round(utilization * packets_at_full))
