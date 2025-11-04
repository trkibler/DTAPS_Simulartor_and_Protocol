import numpy as np
import logging
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict, deque
#local imports
from SimulationEvent import SimulationEvent
from Config import SimulationConfig
from SimulatorConfig import PerformanceMetrics
from NetworkTopology import NetworkTopologyManager

class ProtocolSimulator:
    """Base class for protocol simulation"""

    def __init__(self, name: str, config: SimulationConfig):
        self.name = name
        self.config = config
        self.random_state = np.random.RandomState(42)
        self.logger = logging.getLogger(f"Simulation.{name}")

        self.topology = NetworkTopologyManager(config)
        self.topology.initialize_topology(config.network_topology)

        # State tracking
        self.node_states = {}
        self.message_queues = defaultdict(list)
        self.active_transmissions = {}

        # Performance metrics
        self.metrics = {
            'messages_generated': 0,
            'messages_delivered': 0,
            'total_delivery_delay': 0.0,
            'delivery_delays': [],
            'bytes_transmitted': 0,
            'transmission_attempts': 0,
            'successful_transmissions': 0,
            'routing_hops': [],
            'failed_routes': 0
        }

        # Initialize all nodes
        for node_id in range(self.config.network_size):
            node_name = f"node_{node_id:03d}"
            self.node_states[node_name] = {
                'message_queue': deque(),
                'storage_used': 0,
                'last_transmission': 0
            }

    def simulate(self, events: List[SimulationEvent]) -> PerformanceMetrics:
        """Run simulation with given events"""
        self.logger.info(f"Starting {self.name} simulation with {len(events)} events")

        # Process events chronologically
        for event in events:
            self.process_event(event)

        return self.calculate_metrics()

    def process_event(self, event: SimulationEvent):
        """Process a single simulation event"""
        if event.event_type == "link_up":
            self.handle_link_up(event)
        elif event.event_type == "link_down":
            self.handle_link_down(event)
        elif event.event_type == "message_generated":
            self.handle_message_generated(event)
        elif event.event_type == "congestion_update":
            self.handle_congestion_update(event)

    def handle_link_up(self, event: SimulationEvent):
        """Handle link up event - should be overridden by specific protocols"""
        self.topology.update_link_state(event.node_id, True, event.timestamp)

    def handle_link_down(self, event: SimulationEvent):
        """Handle link down event - should be overridden by specific protocols"""
        self.topology.update_link_state(event.node_id, False, event.timestamp)

    def handle_congestion_update(self, event: SimulationEvent):
        """Handle periodic congestion updates"""
        self.topology.update_congestion(event.timestamp)

    def handle_message_generated(self, event: SimulationEvent):
        """Handle message generation - should be overridden by specific protocols"""
        self.metrics['messages_generated'] += 1

    def calculate_metrics(self) -> PerformanceMetrics:
        """Calculate final performance metrics"""
        delivery_ratio = 0.0
        avg_delay = 0.0
        delay_variance = 0.0
        transmission_efficiency = 0.0
        avg_hops = 0.0
        route_failure_rate = 0.0

        if self.metrics['messages_generated'] > 0:
            delivery_ratio = self.metrics['messages_delivered'] / self.metrics['messages_generated']
            route_failure_rate = self.metrics['failed_routes'] / max(1, self.metrics['transmission_attempts'])

        if self.metrics['messages_delivered'] > 0:
            avg_delay = self.metrics['total_delivery_delay'] / self.metrics['messages_delivered']
            delay_variance = np.var(self.metrics['delivery_delays']) if self.metrics['delivery_delays'] else 0.0
            avg_hops = np.mean(self.metrics['routing_hops']) if self.metrics['routing_hops'] else 0.0

        if self.metrics['transmission_attempts'] > 0:
            transmission_efficiency = self.metrics['successful_transmissions'] / self.metrics['transmission_attempts']

        return PerformanceMetrics(
            protocol_name=self.name,
            message_delivery_ratio=delivery_ratio,
            average_delivery_delay=avg_delay,
            delivery_delay_variance=delay_variance,
            total_bytes_transmitted=self.metrics['bytes_transmitted'],
            transmission_efficiency=transmission_efficiency,
            average_routing_hops=avg_hops,
            route_failure_rate=route_failure_rate
        )
