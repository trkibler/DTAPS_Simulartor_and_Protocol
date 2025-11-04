from dataclasses import dataclass
from typing import Tuple
from enum import Enum
#local imports
from SimulatorConfig import DisruptionPattern, NetworkTopology

# ============================================================================
# SIMULATION CONFIGURATION AND DATA STRUCTURES
# ============================================================================

class DTAPSMode(Enum):
    LOW_LATENCY = "low_latency"
    BALANCED = "balanced"
    HIGH_RELIABILITY = "high_reliability"

@dataclass
class SimulationConfig:
    """Simulation configuration parameters"""
    duration: float = 3600.0
    network_size: int = 10
    disruption_rate: float = 0.8
    disruption_pattern: DisruptionPattern = DisruptionPattern.UNIFORM_RANDOM
    connectivity_window_min: float = 1.0
    connectivity_window_max: float = 30.0
    message_generation_rate: float = 0.1
    message_size_range: Tuple[int, int] = (100, 10000)
    bandwidth_range: Tuple[int, int] = (1000, 1000000)
    dtaps_mode: DTAPSMode = DTAPSMode.BALANCED
    network_topology: NetworkTopology = NetworkTopology.RANDOM_GRAPH
