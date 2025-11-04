import matplotlib.pyplot as plt
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
import logging
from dataclasses import asdict
import time
from collections import defaultdict
import numpy as np
#local imports
from DTAPSSimulator import DTAPSSimulator
from Config import SimulationConfig, DTAPSMode
from TraditionalSimulators import TraditionalTCPSimulator, TraditionalUDPSimulator
from SimulationEvent import SimulationEvent
from DisruptionGenerators import DisruptionGenerator
from TrafficGenerator import TrafficGenerator
from NetworkTopology import NetworkTopologyManager
from SimulatorConfig import PerformanceMetrics

# ============================================================================
# SIMULATION RUNNER AND ANALYSIS
# ============================================================================

class SimulationRunner:
    """Main simulation runner and analysis engine"""

    def __init__(self):
        self.logger = logging.getLogger("SimulationRunner")

    def run_comparative_simulation(self, config: SimulationConfig) -> Dict[str, PerformanceMetrics]:
        """Run comparative simulation of different protocols"""

        # Generate network topology first
        topology = NetworkTopologyManager(config)
        topology.initialize_topology(config.network_topology)
        topology.visualize_topology()

        # Generate events
        disruption_gen = DisruptionGenerator(config)
        traffic_gen = TrafficGenerator(config)

        disruption_events = disruption_gen.generate_disruption_events()
        message_events = traffic_gen.generate_message_events()

        # Add congestion update events
        congestion_events = []
        current_time = 0.0
        while current_time < config.duration:
            congestion_events.append(SimulationEvent(
                timestamp=current_time,
                event_type="congestion_update",
                node_id="network",
                data={}
            ))
            current_time += 10.0

        all_events = disruption_events + message_events + congestion_events
        all_events.sort(key=lambda x: x.timestamp)

        self.logger.info(f"Generated {len(disruption_events)} disruption events, "
                        f"{len(message_events)} message events, "
                        f"{len(congestion_events)} congestion events")

        # Initialize protocol simulators
        base_config_dict = {k: v for k, v in asdict(config).items() if k != 'dtaps_mode'}
        simulators = [
            DTAPSSimulator(SimulationConfig(**base_config_dict, dtaps_mode=DTAPSMode.LOW_LATENCY)),
            DTAPSSimulator(SimulationConfig(**base_config_dict, dtaps_mode=DTAPSMode.BALANCED)),
            DTAPSSimulator(SimulationConfig(**base_config_dict, dtaps_mode=DTAPSMode.HIGH_RELIABILITY)),
            TraditionalTCPSimulator(config),
            TraditionalUDPSimulator(config),
        ]

        simulators[0].name = "DTAPS_Low"
        simulators[1].name = "DTAPS_Balanced"
        simulators[2].name = "DTAPS_High"

        # Run simulations
        results = {}
        for simulator in simulators:
            self.logger.info(f"Running {simulator.name} simulation...")
            start_time = time.time()

            metrics = simulator.simulate(all_events)

            simulation_time = time.time() - start_time
            self.logger.info(f"{simulator.name} simulation completed in {simulation_time:.2f}s")

            results[simulator.name] = metrics

        return results

    def analyze_results(self, results: Dict[str, PerformanceMetrics]) -> Dict[str, Any]:
        """Analyze and compare simulation results"""

        analysis = {
            'summary': {},
            'comparisons': {},
            'recommendations': []
        }

        # Summary statistics
        for protocol_name, metrics in results.items():
            analysis['summary'][protocol_name] = {
                'delivery_ratio': f"{metrics.message_delivery_ratio:.3f}",
                'avg_delay': f"{metrics.average_delivery_delay:.2f}s" if metrics.average_delivery_delay < float('inf') else "N/A",
                'delay_variance': f"{metrics.delivery_delay_variance:.2f}",
                'transmission_efficiency': f"{metrics.transmission_efficiency:.3f}",
                'total_bytes': metrics.total_bytes_transmitted,
                'avg_hops': f"{metrics.average_routing_hops:.2f}",
                'route_failure_rate': f"{metrics.route_failure_rate:.3f}"
            }

        # Comparative analysis
        baseline = 'TCP'
        if baseline in results:
            baseline_metrics = results[baseline]
            for protocol in [p for p in results if p.startswith('DTAPS_')]:
                dtaps_metrics = results[protocol]
                analysis['comparisons'][protocol] = {
                    'delivery_ratio_improvement': dtaps_metrics.message_delivery_ratio / max(0.001, baseline_metrics.message_delivery_ratio),
                    'delay_improvement': (baseline_metrics.average_delivery_delay / max(0.001, dtaps_metrics.average_delivery_delay)
                                         if dtaps_metrics.average_delivery_delay < float('inf') else 0.0),
                    'efficiency_improvement': dtaps_metrics.transmission_efficiency / max(0.001, baseline_metrics.transmission_efficiency),
                }

                if dtaps_metrics.message_delivery_ratio > baseline_metrics.message_delivery_ratio * 1.5:
                    analysis['recommendations'].append(
                        f"{protocol} shows significant delivery ratio improvement over {baseline}"
                    )

                if dtaps_metrics.average_delivery_delay < baseline_metrics.average_delivery_delay * 0.8 and dtaps_metrics.average_delivery_delay < float('inf'):
                    analysis['recommendations'].append(
                        f"{protocol} achieves lower average delivery delay than {baseline}"
                    )

        return analysis

    def generate_visualizations(self, results: Dict[str, PerformanceMetrics],
                               analysis: Dict[str, Any]) -> None:
        """Generate visualization plots for results"""

        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('DTAPS vs Traditional Protocols - Performance Comparison', fontsize=16)

        protocols = list(results.keys())
        colors = plt.cm.rainbow(np.linspace(0, 1, len(protocols)))

        # Plot 1: Message Delivery Ratio
        delivery_ratios = [results[p].message_delivery_ratio for p in protocols]
        bars1 = ax1.bar(protocols, delivery_ratios, color=colors)
        ax1.set_title('Message Delivery Ratio')
        ax1.set_ylabel('Delivery Ratio')
        ax1.set_ylim(0, max(delivery_ratios) * 1.1 if max(delivery_ratios) > 0 else 1.0)
        ax1.tick_params(axis='x', rotation=45)

        for bar, ratio in zip(bars1, delivery_ratios):
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(delivery_ratios) * 0.01,
                    f'{ratio:.3f}', ha='center', va='bottom')

        # Plot 2: Average Delivery Delay - UPDATED FOR 3 DECIMAL PLACES
        avg_delays = [results[p].average_delivery_delay for p in protocols]
        valid_delays = [d for d in avg_delays if d < float('inf')]
        max_delay = max(valid_delays) * 1.1 if valid_delays else 1000.0
        bars2 = ax2.bar(protocols, [min(d, max_delay) for d in avg_delays], color=colors)
        ax2.set_title('Average Delivery Delay')
        ax2.set_ylabel('Delay (seconds)')
        ax2.set_ylim(0, max_delay)
        ax2.tick_params(axis='x', rotation=45)

        for bar, delay in zip(bars2, avg_delays):
            if delay < float('inf'):
                # Changed from f'{delay:.1f}s' to f'{delay:.3f}s' for 3 decimal places
                label = f'{delay:.3f}s'
            else:
                label = '∞'
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max_delay * 0.01,
                    label, ha='center', va='bottom')

        # Plot 3: Transmission Efficiency
        efficiencies = [results[p].transmission_efficiency for p in protocols]
        bars3 = ax3.bar(protocols, efficiencies, color=colors)
        ax3.set_title('Transmission Efficiency')
        ax3.set_ylabel('Efficiency Ratio')
        ax3.set_ylim(0, max(efficiencies) * 1.1 if max(efficiencies) > 0 else 1.0)
        ax3.tick_params(axis='x', rotation=45)

        for bar, eff in zip(bars3, efficiencies):
            ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(efficiencies) * 0.01,
                    f'{eff:.3f}', ha='center', va='bottom')

        # Plot 4: Average Routing Hops
        avg_hops = [results[p].average_routing_hops for p in protocols]
        bars4 = ax4.bar(protocols, avg_hops, color=colors)
        ax4.set_title('Average Routing Hops')
        ax4.set_ylabel('Number of Hops')
        ax4.set_ylim(0, max(avg_hops) * 1.1 if max(avg_hops) > 0 else 5.0)
        ax4.tick_params(axis='x', rotation=45)

        for bar, hops in zip(bars4, avg_hops):
            ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(avg_hops) * 0.01,
                    f'{hops:.2f}', ha='center', va='bottom')

        plt.tight_layout()
        plt.savefig('dtaps_performance_comparison.png', dpi=300, bbox_inches='tight')
        plt.show()

    def create_disruption_pattern_visualization(self, events: List[SimulationEvent]) -> None:
        """Create visualization of network disruption patterns"""
        link_events = [e for e in events if e.event_type in ['link_up', 'link_down']]

        node_timelines = defaultdict(list)
        for event in link_events:
            node_timelines[event.node_id].append(event)

        fig, ax = plt.subplots(figsize=(15, 8))

        y_pos = 0
        node_positions = {}
        colors = {'link_up': '#2E8B57', 'link_down': '#DC143C'}

        for node_id, timeline in sorted(node_timelines.items()):
            node_positions[node_id] = y_pos

            current_state = "down"
            period_start = 0

            for event in timeline:
                if event.event_type == "link_up" and current_state == "down":
                    period_start = event.timestamp
                    current_state = "up"
                elif event.event_type == "link_down" and current_state == "up":
                    ax.barh(y_pos, event.timestamp - period_start, left=period_start,
                           height=0.8, color=colors['link_up'], alpha=0.7)
                    current_state = "down"

            y_pos += 1

        ax.set_xlabel('Time (seconds)')
        ax.set_ylabel('Network Nodes')
        ax.set_title('Network Connectivity Timeline\n(Green: Connected, White: Disconnected)')
        ax.set_yticks(list(node_positions.values()))
        ax.set_yticklabels(list(node_positions.keys()))
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig('network_disruption_timeline.png', dpi=300, bbox_inches='tight')
        plt.show()