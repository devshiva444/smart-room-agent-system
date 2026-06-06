"""
SmartRoom Agentic Swarm - Phase 2
Four Collaborative Agents for Autonomous Workspace OS

Environmental Agent: Wraps DQN inference for room control
Productivity Agent: Analyzes transcripts and extracts action items
Execution Agent: Connects to external APIs (GitHub, Slack)
Security Agent: Validates inputs and enforces safety policies
"""

from .environmental_agent import EnvironmentalAgent
from .productivity_agent import ProductivityAgent
from .execution_agent import ExecutionAgent
from .security_agent import SecurityAgent

__all__ = [
    "EnvironmentalAgent",
    "ProductivityAgent",
    "ExecutionAgent",
    "SecurityAgent",
]