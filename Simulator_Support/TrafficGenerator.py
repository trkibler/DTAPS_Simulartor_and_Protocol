import numpy as np
from typing import List
#local imports
from Simulator.Config import SimulationConfig
from Simulator_Support.SimulationEvent import SimulationEvent

# ============================================================================
# MESSAGE GENERATION AND TRAFFIC PATTERNS
# ============================================================================

class TrafficGenerator:
    """Generates realistic message traffic patterns"""

    def __init__(self, config: SimulationConfig):
        self.config = config
        self.random_state = np.random.RandomState(123)

    def generate_message_events(self) -> List[SimulationEvent]:
        """Generate message generation events"""
        events = []

        current_time = 0.0
        message_id = 0

        while current_time < self.config.duration:
            inter_arrival = self.random_state.exponential(1.0 / self.config.message_generation_rate)
            current_time += inter_arrival

            if current_time >= self.config.duration:
                break

            source_node = self.random_state.randint(0, self.config.network_size)
            dest_node = self.random_state.randint(0, self.config.network_size)
            while dest_node == source_node:
                dest_node = self.random_state.randint(0, self.config.network_size)

            message_size = self.random_state.randint(*self.config.message_size_range)

            priority_roll = self.random_state.random()
            if priority_roll < 0.05:
                priority = 0
            elif priority_roll < 0.20:
                priority = 1
            elif priority_roll < 0.70:
                priority = 2
            else:
                priority = 3

            events.append(SimulationEvent(
                timestamp=current_time,
                event_type="message_generated",
                node_id=f"node_{source_node:03d}",
                message_id=f"msg_{message_id:06d}",
                data={
                    'destination': f"node_{dest_node:03d}",
                    'size': message_size,
                    'priority': priority,
                    'ttl': 3600 + priority * 1800
                }
            ))

            message_id += 1

        return events
