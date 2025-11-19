from dataclasses import dataclass
from typing import Tuple
from enum import Enum
import json
import os
#local imports
from Simulator.SimulatorData import DisruptionPattern, NetworkTopology

#dicts
disruption_pattern_dict = {
    "UNIFORM_RANDOM": DisruptionPattern.UNIFORM_RANDOM,
    "CLUSTERED_OUTAGES": DisruptionPattern.CLUSTERED_OUTAGES,
    "PERIODIC_CYCLES": DisruptionPattern.PERIODIC_CYCLES,
    "BURSTY_CONNECTIVITY": DisruptionPattern.BURSTY_CONNECTIVITY, 
    "REALISTIC_MOBILE": DisruptionPattern.REALISTIC_MOBILE
}
network_topology_dict = {
    "FULLY_CONNECTED": NetworkTopology.FULLY_CONNECTED,
    "RANDOM_GRAPH": NetworkTopology.RANDOM_GRAPH,
    "SCALE_FREE": NetworkTopology.SCALE_FREE,
    "SMALL_WORLD": NetworkTopology.SMALL_WORLD
}


# ============================================================================
# SIMULATION CONFIGURATION AND DATA STRUCTURES
# ============================================================================

class DTAPSMode(Enum):
    LOW_LATENCY = "low_latency"
    BALANCED = "balanced"
    HIGH_RELIABILITY = "high_reliability"

dtaps_modes_dict = {
    "LOW_LATENCY": DTAPSMode.LOW_LATENCY,
    "BALANCED": DTAPSMode.BALANCED,
    "HIGH_RELIABILITY": DTAPSMode.HIGH_RELIABILITY
}

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

    @classmethod
    def check_config(self, config_file_path="./configs.json"):
        if os.path.exists(config_file_path):
            with open(config_file_path, "r") as conf_file:
                try:
                    data = json.load(conf_file)
                    for i in data:
                        if str(i).lower() == "duration":
                            self.duration = data[i]
                        elif str(i).lower() == "network_size":
                            self.network_size = data[i]
                        elif str(i).lower() == "disruption_rate":
                            self.disruption_rate = data[i]
                        elif str(i).lower() == "connectivity_window_min":
                            self.connectivity_window_min = data[i]
                        elif str(i).lower() == "connectivity_window_max":
                            self.connectivity_window_max = data[i]
                        elif str(i).lower() == "message_generation_rate":
                            self.message_generation_rate = data[i]
                        elif str(i).lower() == "disruption_pattern":
                            self.disruption_pattern = disruption_pattern_dict[str(data[i]).upper()]
                        elif str(i).lower() == "dtaps_mode":
                            self.dtaps_mode = dtaps_modes_dict[str(data[i]).upper()]
                        elif str(i).lower() == "network_topology":
                            self.network_topology = network_topology_dict[str(data[i]).upper()]
                        elif str(i).lower() == "message_size_range":
                            self.message_size_range = tuple(data[i])
                        elif str(i).lower() == "bandwidth_range":
                            self.bandwidth_range = tuple(data[i])
                except json.JSONDecodeError:
                    print("Error: Config file JSON decoding failed. Please ensure that file is in proper JSON format")
        else:
            print("Configuration File Not Found")