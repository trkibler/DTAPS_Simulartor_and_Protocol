from enum import Enum
from collections import defaultdict, deque
import numpy as np
#local imports
from Simulator.ProtocolSimulator import ProtocolSimulator
from Simulator_Support.SimulationEvent import SimulationEvent
from Simulator.Config import SimulationConfig, DTAPSMode


# ============================================================================
# DTAPS MODE CONFIGURATION PARAMETERS
# ============================================================================
DTAPS_MODE_PARAMS = {
    DTAPSMode.LOW_LATENCY: {
        'replica_count': {0: 1, 1: 1, 2: 1, 3: 1},
        'success_prob_multiplier': 0.8,
        'ttl_factor': 0.5,
        'window_factor_range': (0.8, 1.2),
        'max_delivery_attempts': 3,
    },
    DTAPSMode.BALANCED: {
        'replica_count': {0: 2, 1: 2, 2: 1, 3: 1},
        'success_prob_multiplier': 0.9,
        'ttl_factor': 1.0,
        'window_factor_range': (0.7, 1.0),
        'max_delivery_attempts': 5,
    },
    DTAPSMode.HIGH_RELIABILITY: {
        'replica_count': {0: 3, 1: 3, 2: 2, 3: 2},
        'success_prob_multiplier': 0.95,
        'ttl_factor': 1.5,
        'window_factor_range': (0.6, 0.9),
        'max_delivery_attempts': 8,
    }
}

class DTAPSSimulator(ProtocolSimulator):
    """DTAPS protocol simulator"""
    def __init__(self, config: SimulationConfig):
        super().__init__("DTAPS", config)

        # DTAPS-specific state
        self.link_predictions = {}
        self.message_replicas = defaultdict(list)
        self.successful_deliveries = {}
        self.delivered_unique_ids = set()
        self.mode = config.dtaps_mode
        self.mode_params = DTAPS_MODE_PARAMS[config.dtaps_mode]

    def handle_link_up(self, event: SimulationEvent):
        """DTAPS-specific link up handling"""
        super().handle_link_up(event)

        quality = event.data.get('quality', 0.5)
        self._update_link_prediction(event.node_id, event.timestamp, quality)
        self._opportunistic_transmission(event.node_id, event.timestamp, quality)

    def handle_message_generated(self, event: SimulationEvent):
        """DTAPS-specific message generation handling"""
        super().handle_message_generated(event)

        message_data = event.data
        base_ttl = 3600 + message_data['priority'] * 1800
        ttl = base_ttl * self.mode_params['ttl_factor']

        message_info = {
            'id': event.message_id,
            'source': event.node_id,
            'destination': message_data['destination'],
            'size': message_data['size'],
            'priority': message_data['priority'],
            'created_time': event.timestamp,
            'ttl': ttl,
            'delivery_attempts': 0
        }

        # Add to source node queue
        self.node_states[event.node_id]['message_queue'].append(message_info)

        # Use mode-specific replication strategy from configuration
        replica_count = self.mode_params['replica_count'][message_data['priority']]
        self._replicate_message(message_info, replica_count)

    def _opportunistic_transmission(self, node_id: str, timestamp: float, quality: float):
        """Perform opportunistic transmission using network routing"""
        node_state = self.node_states[node_id]

        # Check if node has any neighbors
        neighbors = self.topology.get_neighbors(node_id)
        if not neighbors:
            return

        # Estimate transmission capacity based on quality
        estimated_bytes = quality * self.config.bandwidth_range[1] * 10

        transmitted_bytes = 0
        messages_to_remove = []

        for message in list(node_state['message_queue']):
            if transmitted_bytes >= estimated_bytes:
                break

            # Try to route message to destination through the network
            success, delay, route = self.topology.transmit_message(
                node_id, message['destination'], message['size'], timestamp
            )

            self.metrics['transmission_attempts'] += 1

            if success and len(route) > 0:
                # DTAPS-specific reliability check
                reliability = self.mode_params['success_prob_multiplier']
                # Additional penalty for longer routes
                route_penalty = (len(route) - 1) * 0.02
                delivery_probability = reliability - route_penalty

                if self.random_state.random() < delivery_probability:
                    # Message successfully delivered
                    self.metrics['successful_transmissions'] += 1
                    transmitted_bytes += message['size']
                    self.metrics['routing_hops'].append(len(route) - 1)

                    # Check if this is a unique delivery
                    if message['id'] not in self.delivered_unique_ids:
                        self.delivered_unique_ids.add(message['id'])
                        self.metrics['messages_delivered'] += 1
                        self.metrics['total_delivery_delay'] += delay
                        self.metrics['delivery_delays'].append(delay)
                        messages_to_remove.append(message)
                else:
                    # DTAPS transmission failed
                    self.metrics['failed_routes'] += 1
                    message['delivery_attempts'] += 1
            else:
                self.metrics['failed_routes'] += 1
                message['delivery_attempts'] += 1

            # Remove if max attempts reached
            max_attempts = self.mode_params['max_delivery_attempts']
            if message['delivery_attempts'] >= max_attempts:
                messages_to_remove.append(message)

        # Remove processed messages
        for message in messages_to_remove:
            if message in node_state['message_queue']:
                node_state['message_queue'].remove(message)

        self.metrics['bytes_transmitted'] += transmitted_bytes

    def _message_reaches_destination(self, message: dict, link_quality: float) -> bool:
        """Determine if message successfully reaches destination"""
        if self.config.disruption_rate < 0.1:
            base_success = 0.85
        else:
            base_success = link_quality * 0.8

        priority_bonus = (3 - message['priority']) * 0.01
        distance_penalty = self.random_state.uniform(0, 0.15)

        success_probability = base_success + priority_bonus - distance_penalty
        success_probability = np.clip(success_probability, 0.1, 0.95)

        return self.random_state.random() < success_probability

    def _update_link_prediction(self, node_id: str, timestamp: float, quality: float):
        """Update link quality prediction model for a node"""
        if node_id not in self.link_predictions:
            self.link_predictions[node_id] = {
                'quality_history': deque(maxlen=20),
                'up_durations': deque(maxlen=10),
                'last_up_time': timestamp
            }

        prediction = self.link_predictions[node_id]
        prediction['quality_history'].append((timestamp, quality))
        prediction['last_up_time'] = timestamp

    def _replicate_message(self, message: dict, replica_count: int):
        """Create message replicas for fault tolerance"""
        available_nodes = [nid for nid in self.node_states.keys()
                          if nid != message['source']]

        if len(available_nodes) < replica_count:
            replica_count = len(available_nodes)

        replica_nodes = self.random_state.choice(available_nodes, size=replica_count, replace=False)

        for node_id in replica_nodes:
            replica = message.copy()
            replica['is_replica'] = True
            replica['original_source'] = message['source']

            self.node_states[node_id]['message_queue'].append(replica)
            self.message_replicas[message['id']].append(node_id)
