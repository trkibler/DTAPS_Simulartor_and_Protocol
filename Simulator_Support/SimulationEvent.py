from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any

@dataclass
class SimulationEvent:
    """Discrete event for simulation"""
    timestamp: float
    event_type: str
    node_id: str
    link_id: Optional[str] = None
    message_id: Optional[str] = None
    data: Dict[str, Any] = None

    def __post_init__(self):
        if self.data is None:
            self.data = {}