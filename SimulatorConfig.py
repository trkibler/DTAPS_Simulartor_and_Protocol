from dataclasses import dataclass
from enum import Enum


class DisruptionPattern(Enum):
    UNIFORM_RANDOM = "uniform_random"
    CLUSTERED_OUTAGES = "clustered_outages"
    PERIODIC_CYCLES = "periodic_cycles"
    BURSTY_CONNECTIVITY = "bursty_connectivity"
    REALISTIC_MOBILE = "realistic_mobile"

class NetworkTopology(Enum):
    FULLY_CONNECTED = "fully_connected"
    RANDOM_GRAPH = "random_graph"
    SCALE_FREE = "scale_free"
    SMALL_WORLD = "small_world"

@dataclass
class PerformanceMetrics:
    """Performance metrics for protocol comparison"""
    protocol_name: str
    message_delivery_ratio: float
    average_delivery_delay: float
    delivery_delay_variance: float
    total_bytes_transmitted: int
    transmission_efficiency: float
    resource_utilization: float = 0.0
    energy_consumption: float = 0.0
    convergence_time: float = 0.0
    average_routing_hops: float = 0.0
    route_failure_rate: float = 0.0