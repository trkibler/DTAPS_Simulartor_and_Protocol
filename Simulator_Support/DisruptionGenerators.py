from typing import List
import numpy as np
#local imports
from Simulator_Support.SimulationEvent import SimulationEvent
from Simulator.SimulatorData import DisruptionPattern
from Simulator.Config import SimulationConfig

# ============================================================================
# NETWORK DISRUPTION GENERATORS
# ============================================================================

class DisruptionGenerator:
    """Generates realistic network disruption patterns"""

    def __init__(self, config: SimulationConfig):
        self.config = config
        self.random_state = np.random.RandomState(42)

    def generate_disruption_events(self) -> List[SimulationEvent]:
        """Generate disruption events based on configured pattern"""
        if not self.config.network_size or self.config.duration <= 0:
            raise ValueError("Invalid configuration: network_size and duration must be positive")

        if self.config.disruption_pattern == DisruptionPattern.UNIFORM_RANDOM:
            return self._generate_uniform_random()
        elif self.config.disruption_pattern == DisruptionPattern.CLUSTERED_OUTAGES:
            return self._generate_clustered_outages()
        elif self.config.disruption_pattern == DisruptionPattern.PERIODIC_CYCLES:
            return self._generate_periodic_cycles()
        elif self.config.disruption_pattern == DisruptionPattern.BURSTY_CONNECTIVITY:
            return self._generate_bursty_connectivity()
        elif self.config.disruption_pattern == DisruptionPattern.REALISTIC_MOBILE:
            return self._generate_realistic_mobile()
        else:
            return self._generate_uniform_random()

    def _generate_uniform_random(self) -> List[SimulationEvent]:
        """Generate uniformly random disruptions"""
        events = []
        current_time = 0.0

        for node_id in range(self.config.network_size):
            node_time = 0.0
            link_state = "down"

            while node_time < self.config.duration:
                if link_state == "down":
                    down_duration = self.random_state.exponential(
                        1.0 / (1 - self.config.disruption_rate) * 10
                    )
                    node_time += down_duration

                    if node_time < self.config.duration:
                        events.append(SimulationEvent(
                            timestamp=node_time,
                            event_type="link_up",
                            node_id=f"node_{node_id:03d}",
                            link_id=f"link_{node_id:03d}",
                            data={'quality': self.random_state.uniform(0.3, 0.9)}
                        ))
                        link_state = "up"
                else:
                    up_duration = self.random_state.uniform(
                        self.config.connectivity_window_min,
                        self.config.connectivity_window_max
                    )
                    node_time += up_duration

                    if node_time < self.config.duration:
                        events.append(SimulationEvent(
                            timestamp=node_time,
                            event_type="link_down",
                            node_id=f"node_{node_id:03d}",
                            link_id=f"link_{node_id:03d}"
                        ))
                        link_state = "down"

        return sorted(events, key=lambda x: x.timestamp)

    def _generate_clustered_outages(self) -> List[SimulationEvent]:
        """Generate clustered outage patterns"""
        events = []

        num_clusters = max(1, int(self.config.duration / 300))
        cluster_times = self.random_state.uniform(0, self.config.duration, num_clusters)

        for cluster_time in cluster_times:
            cluster_size = self.random_state.poisson(self.config.network_size * 0.3)
            cluster_size = min(cluster_size, self.config.network_size)

            affected_nodes = self.random_state.choice(
                self.config.network_size,
                size=cluster_size,
                replace=False
            )

            for node_id in affected_nodes:
                outage_start = cluster_time + self.random_state.exponential(10)
                outage_duration = self.random_state.exponential(120)

                if outage_start < self.config.duration:
                    events.append(SimulationEvent(
                        timestamp=outage_start,
                        event_type="link_down",
                        node_id=f"node_{node_id:03d}",
                        link_id=f"link_{node_id:03d}",
                        data={'cluster_id': len(events)}
                    ))

                    recovery_time = outage_start + outage_duration
                    if recovery_time < self.config.duration:
                        events.append(SimulationEvent(
                            timestamp=recovery_time,
                            event_type="link_up",
                            node_id=f"node_{node_id:03d}",
                            link_id=f"link_{node_id:03d}",
                            data={'quality': self.random_state.uniform(0.4, 0.8)}
                        ))

        baseline_events = self._generate_uniform_random()
        events.extend(baseline_events)

        return sorted(events, key=lambda x: x.timestamp)

    def _generate_periodic_cycles(self) -> List[SimulationEvent]:
        """Generate periodic connectivity cycles"""
        events = []
        cycle_period = 3600

        for node_id in range(self.config.network_size):
            phase_offset = (node_id / self.config.network_size) * cycle_period
            node_quality_base = 0.4 + (node_id % 3) * 0.2

            current_time = 0.0
            while current_time < self.config.duration:
                cycle_position = (current_time + phase_offset) % cycle_period
                connectivity_factor = 0.5 + 0.5 * np.sin(2 * np.pi * cycle_position / cycle_period)

                link_probability = connectivity_factor * (1 - self.config.disruption_rate + 0.3)

                if self.random_state.random() < link_probability:
                    quality = node_quality_base * connectivity_factor
                    quality += self.random_state.normal(0, 0.1)
                    quality = np.clip(quality, 0.1, 0.95)

                    events.append(SimulationEvent(
                        timestamp=current_time,
                        event_type="link_up",
                        node_id=f"node_{node_id:03d}",
                        link_id=f"link_{node_id:03d}",
                        data={'quality': quality, 'cycle_position': cycle_position}
                    ))

                    up_duration = self.random_state.exponential(20 * connectivity_factor)
                    up_duration = np.clip(up_duration, 1, 60)

                    down_time = current_time + up_duration
                    if down_time < self.config.duration:
                        events.append(SimulationEvent(
                            timestamp=down_time,
                            event_type="link_down",
                            node_id=f"node_{node_id:03d}",
                            link_id=f"link_{node_id:03d}"
                        ))

                current_time += self.random_state.exponential(10)

        return sorted(events, key=lambda x: x.timestamp)

    def _generate_bursty_connectivity(self) -> List[SimulationEvent]:
        """Generate bursty connectivity patterns"""
        events = []

        for node_id in range(self.config.network_size):
            current_time = 0.0
            state = "idle"

            while current_time < self.config.duration:
                if state == "idle":
                    idle_duration = self.random_state.exponential(200)
                    current_time += idle_duration
                    state = "burst_building"

                elif state == "burst_building":
                    buildup_duration = self.random_state.exponential(30)
                    steps = max(1, int(buildup_duration / 5))

                    for step in range(steps):
                        step_time = current_time + (step * buildup_duration / steps)
                        if step_time >= self.config.duration:
                            break

                        connectivity_prob = (step + 1) / steps * 0.8

                        if self.random_state.random() < connectivity_prob:
                            quality = 0.3 + (step / steps) * 0.5
                            events.append(SimulationEvent(
                                timestamp=step_time,
                                event_type="link_up",
                                node_id=f"node_{node_id:03d}",
                                link_id=f"link_{node_id:03d}",
                                data={'quality': quality, 'burst_phase': 'building'}
                            ))

                            down_time = step_time + self.random_state.exponential(5)
                            if down_time < self.config.duration:
                                events.append(SimulationEvent(
                                    timestamp=down_time,
                                    event_type="link_down",
                                    node_id=f"node_{node_id:03d}",
                                    link_id=f"link_{node_id:03d}"
                                ))

                    current_time += buildup_duration
                    state = "burst_active"

                elif state == "burst_active":
                    burst_duration = self.random_state.exponential(60)
                    burst_end = current_time + burst_duration

                    while current_time < burst_end and current_time < self.config.duration:
                        if self.random_state.random() < 0.9:
                            quality = self.random_state.uniform(0.6, 0.95)
                            events.append(SimulationEvent(
                                timestamp=current_time,
                                event_type="link_up",
                                node_id=f"node_{node_id:03d}",
                                link_id=f"link_{node_id:03d}",
                                data={'quality': quality, 'burst_phase': 'active'}
                            ))

                            up_duration = self.random_state.exponential(15)
                            down_time = current_time + up_duration

                            if down_time < burst_end and down_time < self.config.duration:
                                events.append(SimulationEvent(
                                    timestamp=down_time,
                                    event_type="link_down",
                                    node_id=f"node_{node_id:03d}",
                                    link_id=f"link_{node_id:03d}"
                                ))

                        current_time += self.random_state.exponential(3)

                    state = "idle"

        return sorted(events, key=lambda x: x.timestamp)

    def _generate_realistic_mobile(self) -> List[SimulationEvent]:
        """Generate realistic mobile network patterns"""
        events = []

        for node_id in range(self.config.network_size):
            speed = self.random_state.uniform(1, 20)
            path_length = speed * self.config.duration

            coverage_areas = 5 + node_id % 3
            area_size = path_length / coverage_areas

            current_time = 0.0
            current_area = 0

            while current_time < self.config.duration:
                area_quality = 0.3 + (current_area % 4) * 0.2
                handoff_penalty = 0.1 if current_area > 0 else 0

                area_transit_time = area_size / speed
                area_end_time = min(current_time + area_transit_time, self.config.duration)

                area_time = current_time
                while area_time < area_end_time:
                    base_prob = area_quality - handoff_penalty
                    connection_prob = max(0.1, base_prob + self.random_state.normal(0, 0.1))

                    if self.random_state.random() < connection_prob:
                        signal_strength = area_quality + self.random_state.uniform(-0.2, 0.2)
                        signal_strength = np.clip(signal_strength, 0.1, 0.95)

                        events.append(SimulationEvent(
                            timestamp=area_time,
                            event_type="link_up",
                            node_id=f"node_{node_id:03d}",
                            link_id=f"link_{node_id:03d}",
                            data={
                                'quality': signal_strength,
                                'area': current_area,
                                'mobility_speed': speed
                            }
                        ))

                        base_duration = 20 + signal_strength * 40
                        mobility_factor = max(0.5, 10 / speed)
                        connection_duration = base_duration * mobility_factor
                        connection_duration *= self.random_state.uniform(0.5, 1.5)

                        disconnect_time = area_time + connection_duration
                        if disconnect_time < area_end_time and disconnect_time < self.config.duration:
                            events.append(SimulationEvent(
                                timestamp=disconnect_time,
                                event_type="link_down",
                                node_id=f"node_{node_id:03d}",
                                link_id=f"link_{node_id:03d}"
                            ))

                    area_time += self.random_state.exponential(5 + handoff_penalty * 10)
                    handoff_penalty = 0

                current_time = area_end_time
                current_area += 1

        return sorted(events, key=lambda x: x.timestamp)