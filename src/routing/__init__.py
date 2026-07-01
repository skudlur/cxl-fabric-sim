"""Routing strategies for TraceCXL."""

from .strategy import RoutingStrategy, StaticRouting, ECMPRouting, WeightedRouting, OccupancyWeightedECMPRouting

__all__ = [
    'RoutingStrategy',
    'StaticRouting',
    'ECMPRouting',
    'WeightedRouting',
    'OccupancyWeightedECMPRouting',
]
