from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import matplotlib.pyplot as plt
from dataclasses import dataclass
#local imports
from Simulator.Config import SimulationConfig
from Simulator.SimulatorData import NetworkTopology

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    print("Warning: NetworkX not available. Topology visualization will be disabled.")

# ============================================================================
# NETWORK TOPOLOGY AND ROUTING
# ============================================================================

@dataclass
class NetworkLink:
    """Represents a connection between two nodes"""
    node_a: str
    node_b: str
    bandwidth: int
    latency: float
    congestion_level: float = 0.0
    is_active: bool = True

    def get_effective_bandwidth(self) -> float:
        """Calculate bandwidth considering congestion"""
        return self.bandwidth * (1 - self.congestion_level)

    def get_transmission_delay(self, message_size: int) -> float:
        """Calculate transmission time considering congestion and latency"""
        effective_bandwidth = self.get_effective_bandwidth()
        if effective_bandwidth <= 0:
            return float('inf')
        return (message_size / effective_bandwidth) + self.latency

class NetworkTopologyManager:
    """Manages network topology, routing, and congestion"""

    def __init__(self, config: SimulationConfig):
        self.config = config
        self.random_state = np.random.RandomState(42)
        self.nodes = [f"node_{i:03d}" for i in range(config.network_size)]
        self.links: Dict[Tuple[str, str], NetworkLink] = {}
        self.routing_table: Dict[Tuple[str, str], List[str]] = {}
        self.node_queues: Dict[str, deque] = {node: deque() for node in self.nodes}
        self.congestion_update_interval = 10.0

    def initialize_topology(self, topology: NetworkTopology):
        """Initialize network topology based on type"""
        self.links.clear()

        if topology == NetworkTopology.FULLY_CONNECTED:
            self._create_fully_connected()
        elif topology == NetworkTopology.RANDOM_GRAPH:
            self._create_random_graph()
        elif topology == NetworkTopology.SCALE_FREE:
            self._create_scale_free()
        elif topology == NetworkTopology.SMALL_WORLD:
            self._create_small_world()

        self._build_routing_tables()

    def _create_fully_connected(self):
        """Create fully connected network"""
        for i, node_a in enumerate(self.nodes):
            for j, node_b in enumerate(self.nodes):
                if i < j:
                    bandwidth = self.random_state.randint(*self.config.bandwidth_range)
                    latency = self.random_state.uniform(0.001, 0.1)
                    link = NetworkLink(node_a, node_b, bandwidth, latency)
                    self.links[(node_a, node_b)] = link
                    self.links[(node_b, node_a)] = link

    def _create_random_graph(self):
        """Create random graph with average degree ~log(n)"""
        target_degree = max(2, int(np.log(len(self.nodes))))
        probability = target_degree / len(self.nodes)

        for i, node_a in enumerate(self.nodes):
            for j, node_b in enumerate(self.nodes):
                if i < j and self.random_state.random() < probability:
                    bandwidth = self.random_state.randint(*self.config.bandwidth_range)
                    latency = self.random_state.uniform(0.001, 0.1)
                    link = NetworkLink(node_a, node_b, bandwidth, latency)
                    self.links[(node_a, node_b)] = link
                    self.links[(node_b, node_a)] = link

        self._ensure_connectivity()

    def _create_scale_free(self):
        """Create scale-free network (Barabási–Albert model)"""
        core_size = min(3, len(self.nodes))
        for i in range(core_size):
            for j in range(i + 1, core_size):
                node_a, node_b = self.nodes[i], self.nodes[j]
                bandwidth = self.random_state.randint(*self.config.bandwidth_range)
                latency = self.random_state.uniform(0.001, 0.1)
                link = NetworkLink(node_a, node_b, bandwidth, latency)
                self.links[(node_a, node_b)] = link
                self.links[(node_b, node_a)] = link

        for new_node_idx in range(core_size, len(self.nodes)):
            new_node = self.nodes[new_node_idx]
            degrees = {node: self.get_node_degree(node) for node in self.nodes[:new_node_idx]}
            total_degree = sum(degrees.values())

            m = min(2, new_node_idx)
            targets = []
            for _ in range(m):
                if total_degree == 0:
                    target = self.random_state.choice(self.nodes[:new_node_idx])
                else:
                    probs = [degrees[node] / total_degree for node in self.nodes[:new_node_idx]]
                    target = self.random_state.choice(self.nodes[:new_node_idx], p=probs)
                targets.append(target)

            for target in set(targets):
                bandwidth = self.random_state.randint(*self.config.bandwidth_range)
                latency = self.random_state.uniform(0.001, 0.1)
                link = NetworkLink(new_node, target, bandwidth, latency)
                self.links[(new_node, target)] = link
                self.links[(target, new_node)] = link

    def _create_small_world(self):
        """Create small-world network (Watts-Strogatz model)"""
        k = 4
        for i, node_a in enumerate(self.nodes):
            for j in range(1, k // 2 + 1):
                node_b = self.nodes[(i + j) % len(self.nodes)]
                bandwidth = self.random_state.randint(*self.config.bandwidth_range)
                latency = self.random_state.uniform(0.001, 0.1)
                link = NetworkLink(node_a, node_b, bandwidth, latency)
                self.links[(node_a, node_b)] = link
                self.links[(node_b, node_a)] = link

        beta = 0.1
        links_to_rewire = []
        for (node_a, node_b), link in list(self.links.items()):
            if self.random_state.random() < beta and node_a < node_b:
                links_to_rewire.append((node_a, node_b))

        for node_a, old_node_b in links_to_rewire:
            del self.links[(node_a, old_node_b)]
            del self.links[(old_node_b, node_a)]

            possible_nodes = [n for n in self.nodes if n != node_a and
                            (node_a, n) not in self.links]
            if possible_nodes:
                new_node_b = self.random_state.choice(possible_nodes)
                bandwidth = self.random_state.randint(*self.config.bandwidth_range)
                latency = self.random_state.uniform(0.001, 0.1)
                link = NetworkLink(node_a, new_node_b, bandwidth, latency)
                self.links[(node_a, new_node_b)] = link
                self.links[(new_node_b, node_a)] = link

    def _ensure_connectivity(self):
        """Ensure graph is connected"""
        components = self._find_connected_components()
        if len(components) > 1:
            for i in range(len(components) - 1):
                node_a = self.random_state.choice(list(components[i]))
                node_b = self.random_state.choice(list(components[i + 1]))
                bandwidth = self.random_state.randint(*self.config.bandwidth_range)
                latency = self.random_state.uniform(0.001, 0.1)
                link = NetworkLink(node_a, node_b, bandwidth, latency)
                self.links[(node_a, node_b)] = link
                self.links[(node_b, node_a)] = link

    def _find_connected_components(self) -> List[set]:
        """Find connected components using BFS"""
        visited = set()
        components = []

        for node in self.nodes:
            if node not in visited:
                component = set()
                queue = deque([node])
                visited.add(node)

                while queue:
                    current = queue.popleft()
                    component.add(current)
                    neighbors = self.get_neighbors(current)
                    for neighbor in neighbors:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)

                components.append(component)

        return components

    def get_neighbors(self, node: str) -> List[str]:
        """Get all neighbors of a node"""
        neighbors = []
        for (node_a, node_b), link in self.links.items():
            if node_a == node and link.is_active:
                neighbors.append(node_b)
        return neighbors

    def get_node_degree(self, node: str) -> int:
        """Get degree of a node"""
        return len(self.get_neighbors(node))

    def _build_routing_tables(self):
        """Build routing tables using Dijkstra's algorithm"""
        self.routing_table.clear()

        for source in self.nodes:
            for destination in self.nodes:
                if source != destination:
                    path = self._find_shortest_path(source, destination)
                    if path:
                        self.routing_table[(source, destination)] = path

    def _find_shortest_path(self, source: str, destination: str) -> List[str]:
        """Find shortest path considering latency and congestion"""
        distances = {node: float('inf') for node in self.nodes}
        previous = {node: None for node in self.nodes}
        distances[source] = 0

        unvisited = set(self.nodes)

        while unvisited:
            current = min(unvisited, key=lambda node: distances[node])
            if distances[current] == float('inf'):
                break

            unvisited.remove(current)

            if current == destination:
                break

            for neighbor in self.get_neighbors(current):
                if neighbor in unvisited:
                    link = self.links.get((current, neighbor))
                    if link and link.is_active:
                        cost = link.latency + (link.congestion_level * 0.1)
                        new_distance = distances[current] + cost
                        if new_distance < distances[neighbor]:
                            distances[neighbor] = new_distance
                            previous[neighbor] = current

        path = []
        current = destination
        while previous[current] is not None:
            path.insert(0, current)
            current = previous[current]

        if path and current == source:
            path.insert(0, source)
            return path
        return []

    def get_route(self, source: str, destination: str) -> List[str]:
        """Get route from source to destination"""
        return self.routing_table.get((source, destination), [])

    def update_link_state(self, node_id: str, is_up: bool, timestamp: float):
        """Update link states and rebuild routing if needed"""
        links_updated = False

        for (node_a, node_b), link in list(self.links.items()):
            if node_a == node_id or node_b == node_id:
                if link.is_active != is_up:
                    link.is_active = is_up
                    links_updated = True

        if links_updated:
            self._build_routing_tables()

    def update_congestion(self, timestamp: float):
        """Update congestion levels based on traffic"""
        # Use a set of link identifiers instead of link objects
        processed_links = set()
        for (node_a, node_b), link in self.links.items():
            # Use tuple of sorted nodes as unique identifier to avoid duplicates
            link_id = tuple(sorted([node_a, node_b]))
            if link_id not in processed_links:
                link.congestion_level *= 0.9
                fluctuation = self.random_state.normal(0, 0.05)
                link.congestion_level += fluctuation
                link.congestion_level = np.clip(link.congestion_level, 0.0, 1.0)
                processed_links.add(link_id)

    def transmit_message(self, source: str, destination: str, message_size: int,
                        timestamp: float) -> Tuple[bool, float, List[str]]:
        """Attempt to transmit message through network"""
        route = self.get_route(source, destination)
        if not route or len(route) < 2:
            return False, float('inf'), []

        total_delay = 0.0
        current_node = source

        for i in range(len(route) - 1):
            node_a, node_b = route[i], route[i + 1]
            link = self.links.get((node_a, node_b))

            if not link or not link.is_active:
                return False, float('inf'), route

            hop_delay = link.get_transmission_delay(message_size)
            if hop_delay == float('inf'):
                return False, float('inf'), route

            total_delay += hop_delay
            congestion_increase = (message_size / link.bandwidth) * 0.1
            link.congestion_level = min(1.0, link.congestion_level + congestion_increase)
            current_node = node_b

        return True, total_delay, route

    def visualize_topology(self):
        """Visualize the network topology"""
        if not NETWORKX_AVAILABLE:
            print("NetworkX not available. Skipping topology visualization.")
            return
        try:
            import networkx as nx

            G = nx.Graph()

            for node in self.nodes:
                G.add_node(node)

            for (node_a, node_b), link in self.links.items():
                if node_a < node_b:  # Avoid duplicates
                    if link.is_active:
                        # Add edge with link attributes
                        G.add_edge(node_a, node_b,
                                 latency=link.latency,
                                 bandwidth=link.bandwidth,
                                 congestion=link.congestion_level,
                                 is_active=link.is_active)

            plt.figure(figsize=(12, 8))
            pos = nx.spring_layout(G, seed=42)  # Consistent layout

            # Node sizes based on degree
            node_sizes = [300 + 100 * self.get_node_degree(node) for node in G.nodes()]

            # Edge colors based on congestion - FIXED: get from edge data
            edge_colors = [G[u][v]['congestion'] for u, v in G.edges()]

            # Draw nodes
            nx.draw_networkx_nodes(G, pos, node_size=node_sizes,
                                 node_color='lightblue', alpha=0.9, edgecolors='black')

            # Draw edges with congestion-based coloring
            edges = nx.draw_networkx_edges(G, pos, edge_color=edge_colors,
                                         edge_cmap=plt.cm.Reds, edge_vmin=0, edge_vmax=1,
                                         width=2, alpha=0.7)

            # Draw node labels
            nx.draw_networkx_labels(G, pos, font_size=8, font_weight='bold')

            # Add edge labels for bandwidth
            edge_labels = {(u, v): f"{G[u][v]['bandwidth']//1000}K"
                          for u, v in G.edges()}
            nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=6)

            # Add colorbar for congestion
            if edges:
                plt.colorbar(edges, label='Congestion Level', shrink=0.8)

            plt.title(f"Network Topology: {len(self.nodes)} nodes, {len(G.edges())} edges\n"
                     f"(Node size = degree, Edge color = congestion)")
            plt.axis('off')
            plt.tight_layout()
            plt.savefig('network_topology.png', dpi=300, bbox_inches='tight')
            plt.show()

            # Print topology statistics
            print(f"\nTopology Statistics:")
            print(f"Nodes: {len(self.nodes)}")
            print(f"Active links: {len(G.edges())}")
            print(f"Average node degree: {np.mean([self.get_node_degree(node) for node in self.nodes]):.2f}")
            print(f"Network density: {nx.density(G):.3f}")
            if nx.is_connected(G):
                print(f"Average shortest path length: {nx.average_shortest_path_length(G):.2f}")
            else:
                print("Graph is not fully connected")

        except ImportError:
            print("NetworkX not available for topology visualization")