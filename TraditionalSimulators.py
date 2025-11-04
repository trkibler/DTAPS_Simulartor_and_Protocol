from ProtocolSimulator import ProtocolSimulator
from SimulationEvent import SimulationEvent
from Config import SimulationConfig
from SimulatorConfig import PerformanceMetrics, DisruptionPattern

class TraditionalTCPSimulator(ProtocolSimulator):
    """Traditional TCP protocol simulator for comparison"""

    def __init__(self, config: SimulationConfig):
        super().__init__("TCP", config)
        self.active_connections = {}
        self.connection_timeout = 30.0
        self.failed_connections = 0  # Track failed connection attempts

    def handle_link_up(self, event: SimulationEvent):
        """TCP-specific link up handling"""
        super().handle_link_up(event)
        self._attempt_connections(event.node_id, event.timestamp)

    def handle_link_down(self, event: SimulationEvent):
        """TCP-specific link down handling"""
        super().handle_link_down(event)

        # Drop connections that use this link
        connections_to_drop = []
        for conn_id, conn in self.active_connections.items():
            if conn['source'] == event.node_id or conn['destination'] == event.node_id:
                connections_to_drop.append(conn_id)

        for conn_id in connections_to_drop:
            del self.active_connections[conn_id]

    def handle_message_generated(self, event: SimulationEvent):
        """TCP-specific message generation"""
        super().handle_message_generated(event)

        message_data = event.data
        message_info = {
            'id': event.message_id,
            'source': event.node_id,
            'destination': message_data['destination'],
            'size': message_data['size'],
            'created_time': event.timestamp,
            'connection_attempts': 0,
            'last_attempt_time': 0.0
        }

        self.node_states[event.node_id]['message_queue'].append(message_info)

    def _attempt_connections(self, node_id: str, timestamp: float):
        """Attempt to establish TCP connections for queued messages"""
        node_state = self.node_states[node_id]

        # Clean up old connections
        self._cleanup_connections(timestamp)

        for message in list(node_state['message_queue']):
            # Only attempt connection if enough time has passed since last attempt
            if timestamp - message.get('last_attempt_time', 0) < 2.0:
                continue

            # Check if we already have an active connection
            conn_id = f"{message['source']}_{message['destination']}"
            if conn_id in self.active_connections:
                # Use existing connection
                self._transmit_over_connection(message, conn_id, timestamp)
            else:
                # Try to establish new connection - COUNT THIS ATTEMPT
                self.metrics['transmission_attempts'] += 1
                connection_success = self._establish_connection(message, timestamp)
                if connection_success:
                    self._transmit_over_connection(message, conn_id, timestamp)
                else:
                    # Count failed connection attempt
                    self.failed_connections += 1
                    message['connection_attempts'] += 1
                    message['last_attempt_time'] = timestamp

    def _cleanup_connections(self, timestamp: float):
        """Remove stale connections"""
        stale_connections = []
        for conn_id, conn in self.active_connections.items():
            if timestamp - conn['last_used'] > self.connection_timeout:
                stale_connections.append(conn_id)

        for conn_id in stale_connections:
            del self.active_connections[conn_id]

    def _establish_connection(self, message: dict, timestamp: float) -> bool:
        """Simulate TCP connection establishment (3-way handshake)"""
        source = message['source']
        destination = message['destination']

        # Check if route exists and all links are active
        route = self.topology.get_route(source, destination)
        if not route or len(route) < 2:
            return False

        # Check if all links in the route are active
        for i in range(len(route) - 1):
            link = self.topology.links.get((route[i], route[i+1]))
            if not link or not link.is_active:
                return False

        # TCP connection success depends on network conditions
        if self.config.disruption_rate < 0.1:
            # Good network - high success rate
            handshake_success = 0.95
        elif self.config.disruption_pattern == DisruptionPattern.REALISTIC_MOBILE:
            # Mobile network - moderate success
            handshake_success = 0.8
        else:
            # High disruption - low success
            handshake_success = 0.4  # Increased from 0.3 to help TCP

        # Penalty for repeated attempts
        attempt_penalty = min(0.3, message['connection_attempts'] * 0.05)  # Reduced penalty
        success_probability = max(0.1, handshake_success - attempt_penalty)

        success = self.random_state.random() < success_probability

        if success:
            # Create connection
            conn_id = f"{source}_{destination}"
            self.active_connections[conn_id] = {
                'source': source,
                'destination': destination,
                'established_time': timestamp,
                'last_used': timestamp,
                'message_count': 0
            }

        return success

    def _transmit_over_connection(self, message: dict, conn_id: str, timestamp: float):
        """Simulate message transmission over established TCP connection"""
        if conn_id not in self.active_connections:
            return False

        connection = self.active_connections[conn_id]
        connection['last_used'] = timestamp
        connection['message_count'] += 1

        # Use network routing for the actual transmission
        success, delay, route = self.topology.transmit_message(
            message['source'], message['destination'], message['size'], timestamp
        )

        # Count this as a transmission attempt (already counted in connection establishment)
        # self.metrics['transmission_attempts'] += 1  # Don't double-count

        if success:
            self.metrics['successful_transmissions'] += 1
            self.metrics['bytes_transmitted'] += message['size']
            self.metrics['messages_delivered'] += 1
            self.metrics['total_delivery_delay'] += delay
            self.metrics['delivery_delays'].append(delay)
            self.metrics['routing_hops'].append(len(route) - 1)

            # Remove delivered message
            node_state = self.node_states[message['source']]
            if message in node_state['message_queue']:
                node_state['message_queue'].remove(message)
        else:
            self.metrics['failed_routes'] += 1
            # Connection might be broken, remove it
            if conn_id in self.active_connections:
                del self.active_connections[conn_id]

        return success

    def calculate_metrics(self) -> PerformanceMetrics:
        """Calculate final performance metrics with proper TCP accounting"""
        # Call parent calculation
        metrics = super().calculate_metrics()

        # Adjust transmission efficiency to account for failed connections
        total_attempts = self.metrics['transmission_attempts'] + self.failed_connections
        if total_attempts > 0:
            metrics.transmission_efficiency = self.metrics['successful_transmissions'] / total_attempts
        else:
            metrics.transmission_efficiency = 0.0

        return metrics

class TraditionalUDPSimulator(ProtocolSimulator):
    """Traditional UDP protocol simulator for comparison"""

    def __init__(self, config: SimulationConfig):
        super().__init__("UDP", config)
        self.packet_loss_rate = 0.1  # Base UDP packet loss

    def handle_link_up(self, event: SimulationEvent):
        """UDP-specific link up handling"""
        super().handle_link_up(event)

        quality = event.data.get('quality', 0.5)
        self._opportunistic_udp_transmission(event.node_id, event.timestamp, quality)

    def handle_message_generated(self, event: SimulationEvent):
        """UDP-specific message generation"""
        super().handle_message_generated(event)

        message_data = event.data
        message_info = {
            'id': event.message_id,
            'source': event.node_id,
            'destination': message_data['destination'],
            'size': message_data['size'],
            'priority': message_data['priority'],
            'created_time': event.timestamp,
            'delivery_attempts': 0
        }

        self.node_states[event.node_id]['message_queue'].append(message_info)

    def _opportunistic_udp_transmission(self, node_id: str, timestamp: float, quality: float):
        """Perform connectionless UDP transmission"""
        node_state = self.node_states[node_id]

        # Check if node has neighbors
        neighbors = self.topology.get_neighbors(node_id)
        if not neighbors:
            return

        # UDP transmission window - shorter than TCP in good conditions
        if self.config.disruption_rate < 0.1:
            estimated_bytes = quality * self.config.bandwidth_range[1] * 5  # Shorter window
        else:
            estimated_bytes = quality * self.config.bandwidth_range[1] * 10

        transmitted_bytes = 0
        messages_to_remove = []

        for message in list(node_state['message_queue']):
            if transmitted_bytes >= estimated_bytes:
                break

            # Use network routing for UDP
            success, delay, route = self.topology.transmit_message(
                node_id, message['destination'], message['size'], timestamp
            )

            self.metrics['transmission_attempts'] += 1

            if success and len(route) > 0:
                # UDP-specific packet loss simulation
                packet_loss = self.packet_loss_rate
                if self.config.disruption_rate > 0.5:
                    packet_loss += 0.2  # Higher loss in disrupted networks

                # Simulate UDP packet loss
                if self.random_state.random() < packet_loss:
                    # Packet lost in transmission
                    self.metrics['failed_routes'] += 1
                    message['delivery_attempts'] += 1
                else:
                    # Packet delivered successfully
                    self.metrics['successful_transmissions'] += 1
                    transmitted_bytes += message['size']
                    self.metrics['routing_hops'].append(len(route) - 1)

                    self.metrics['messages_delivered'] += 1
                    self.metrics['total_delivery_delay'] += delay
                    self.metrics['delivery_delays'].append(delay)
                    messages_to_remove.append(message)
            else:
                self.metrics['failed_routes'] += 1
                message['delivery_attempts'] += 1

            # Remove messages with too many failed attempts
            if message['delivery_attempts'] >= 3:
                messages_to_remove.append(message)

        for message in messages_to_remove:
            if message in node_state['message_queue']:
                node_state['message_queue'].remove(message)

        self.metrics['bytes_transmitted'] += transmitted_bytes
