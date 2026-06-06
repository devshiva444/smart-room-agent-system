"""
State Store - Unified Memory Management
Thread-safe, in-memory state and log manager for the agent swarm.

Responsibilities:
- Store current environmental state (temperature, fan, lights, etc.)
- Maintain unified agent communication logs
- Track action items history
- Provide query/export methods for dashboard and monitoring
"""

import json
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import deque
from pathlib import Path

class StateStore:
    """
    Unified State and Log Manager
    
    Thread-safe in-memory store with optional JSON persistence.
    Maintains:
    - Environmental state snapshots
    - Agent communication logs
    - Action items history
    """
    
    def __init__(self, max_logs: int = 1000, persist_path: Optional[str] = None):
        """
        Initialize State Store.
        
        Args:
            max_logs: Maximum number of log entries to keep in memory (FIFO eviction).
            persist_path: Optional path to persist state to JSON file.
        """
        self._lock = threading.RLock()
        self.max_logs = max_logs
        self.persist_path = persist_path
        
        # Environmental state
        self._env_state: Dict[str, Any] = {
            "temperature": 25.0,
            "light_on": False,
            "fan_speed": 0,
            "ac_on": False,
            "occupancy": False,
            "energy_used": 0.0,
            "time_of_day": "day",
            "sleep_mode": False,
            "last_updated": datetime.utcnow().isoformat(),
        }
        
        # Agent communication logs (FIFO deque)
        self._agent_logs: deque = deque(maxlen=max_logs)
        
        # Action items history
        self._action_items: List[Dict[str, Any]] = []
        
        # Security events log
        self._security_events: deque = deque(maxlen=max_logs // 2)
    
    # ==================== Environmental State Management ====================
    
    def update_env_state(self, state_updates: Dict[str, Any]) -> None:
        """
        Update environmental state atomically.
        
        Args:
            state_updates: Dictionary of state fields to update.
        """
        with self._lock:
            self._env_state.update(state_updates)
            self._env_state["last_updated"] = datetime.utcnow().isoformat()
            self._persist_if_enabled()
    
    def get_env_state(self) -> Dict[str, Any]:
        """Get current environmental state (thread-safe snapshot)."""
        with self._lock:
            return dict(self._env_state)
    
    def get_env_state_field(self, field: str, default: Any = None) -> Any:
        """Get a specific environmental state field."""
        with self._lock:
            return self._env_state.get(field, default)
    
    # ==================== Agent Communication Logging ====================
    
    def log_agent_communication(
        self,
        source_agent: str,
        target_agent: str,
        message: str,
        payload: Optional[Dict[str, Any]] = None,
        status: str = "info"
    ) -> None:
        """
        Log an agent-to-agent communication event.
        
        Args:
            source_agent: Name of sending agent (e.g., "SecurityAgent").
            target_agent: Name of receiving agent.
            message: Human-readable message.
            payload: Optional data payload.
            status: Event status (info, warning, error, success).
        """
        with self._lock:
            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "source": source_agent,
                "target": target_agent,
                "message": message,
                "status": status,
                "payload": payload or {},
            }
            self._agent_logs.append(log_entry)
            self._persist_if_enabled()
    
    def get_agent_logs(self, limit: int = 100, agent_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get recent agent communication logs.
        
        Args:
            limit: Maximum number of entries to return.
            agent_filter: Optional agent name to filter logs (matches source or target).
            
        Returns:
            List of log entries (most recent first).
        """
        with self._lock:
            logs = list(self._agent_logs)
        
        # Filter if requested
        if agent_filter:
            logs = [
                log for log in logs
                if agent_filter.lower() in log["source"].lower() or 
                   agent_filter.lower() in log["target"].lower()
            ]
        
        # Return most recent first, limited to requested count
        return sorted(logs, key=lambda x: x["timestamp"], reverse=True)[:limit]
    
    def get_agent_conversation_chain(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get agent communication logs in conversation order (oldest first).
        
        Args:
            limit: Maximum number of entries.
            
        Returns:
            Conversation chain.
        """
        with self._lock:
            logs = sorted(list(self._agent_logs), key=lambda x: x["timestamp"])[:limit]
        return logs
    
    # ==================== Action Items Management ====================
    
    def log_action_item(self, action_item: Dict[str, Any], source_agent: str = "ProductivityAgent") -> None:
        """
        Log an extracted action item.
        
        Args:
            action_item: Action item dictionary from Productivity Agent.
            source_agent: Agent that extracted the action item.
        """
        with self._lock:
            entry = {
                "id": len(self._action_items),
                "timestamp": datetime.utcnow().isoformat(),
                "source_agent": source_agent,
                "item": action_item,
                "execution_status": "pending",
                "execution_result": None,
            }
            self._action_items.append(entry)
            self._persist_if_enabled()
    
    def update_action_item_status(
        self,
        action_id: int,
        status: str,
        result: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update execution status of an action item.
        
        Args:
            action_id: ID of action item.
            status: New status (pending, executing, success, failed).
            result: Optional execution result.
            
        Returns:
            True if found and updated, False otherwise.
        """
        with self._lock:
            for item in self._action_items:
                if item["id"] == action_id:
                    item["execution_status"] = status
                    item["execution_result"] = result
                    self._persist_if_enabled()
                    return True
        return False
    
    def get_action_items(self, status_filter: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get action items history.
        
        Args:
            status_filter: Optional filter by status (pending, executing, success, failed).
            limit: Maximum number to return.
            
        Returns:
            List of action items (most recent first).
        """
        with self._lock:
            items = list(self._action_items)
        
        if status_filter:
            items = [item for item in items if item["execution_status"] == status_filter]
        
        return sorted(items, key=lambda x: x["timestamp"], reverse=True)[:limit]
    
    # ==================== Security Events Logging ====================
    
    def log_security_event(
        self,
        event_type: str,
        threat_level: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a security validation event.
        
        Args:
            event_type: Type of security event (injection_detected, out_of_bounds, etc.).
            threat_level: Threat level (safe, warning, critical).
            message: Human-readable message.
            details: Optional additional details.
        """
        with self._lock:
            event = {
                "timestamp": datetime.utcnow().isoformat(),
                "event_type": event_type,
                "threat_level": threat_level,
                "message": message,
                "details": details or {},
            }
            self._security_events.append(event)
            self._persist_if_enabled()
    
    def get_security_events(self, threat_level_filter: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get security events log.
        
        Args:
            threat_level_filter: Optional filter by threat level.
            limit: Maximum number to return.
            
        Returns:
            List of security events (most recent first).
        """
        with self._lock:
            events = list(self._security_events)
        
        if threat_level_filter:
            events = [e for e in events if e["threat_level"] == threat_level_filter]
        
        return sorted(events, key=lambda x: x["timestamp"], reverse=True)[:limit]
    
    # ==================== Summary & Metrics ====================
    
    def get_swarm_summary(self) -> Dict[str, Any]:
        """
        Get high-level summary of swarm state and activity.
        
        Returns:
            Dictionary with key metrics and status.
        """
        with self._lock:
            pending_items = sum(1 for item in self._action_items if item["execution_status"] == "pending")
            completed_items = sum(1 for item in self._action_items if item["execution_status"] == "success")
            failed_items = sum(1 for item in self._action_items if item["execution_status"] == "failed")
            critical_events = sum(1 for e in self._security_events if e["threat_level"] == "critical")
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "environmental_state": dict(self._env_state),
                "action_items": {
                    "total": len(self._action_items),
                    "pending": pending_items,
                    "completed": completed_items,
                    "failed": failed_items,
                },
                "communication_logs": len(self._agent_logs),
                "security": {
                    "total_events": len(self._security_events),
                    "critical_events": critical_events,
                },
            }
    
    # ==================== Persistence ====================
    
    def _persist_if_enabled(self) -> None:
        """Persist state to JSON file if path is configured."""
        if not self.persist_path:
            return
        
        try:
            state_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "env_state": self._env_state,
                "agent_logs": list(self._agent_logs)[-100:],  # Keep last 100
                "action_items": self._action_items[-50:],     # Keep last 50
                "security_events": list(self._security_events)[-50:],  # Keep last 50
            }
            
            Path(self.persist_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.persist_path, 'w') as f:
                json.dump(state_data, f, indent=2)
        except Exception as e:
            print(f"[StateStore] Warning: Failed to persist state: {e}")
    
    def load_from_file(self, file_path: str) -> bool:
        """
        Load state from JSON file.
        
        Args:
            file_path: Path to JSON state file.
            
        Returns:
            True if loaded successfully, False otherwise.
        """
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            with self._lock:
                if "env_state" in data:
                    self._env_state.update(data["env_state"])
                if "agent_logs" in data:
                    self._agent_logs.clear()
                    self._agent_logs.extend(data["agent_logs"])
                if "action_items" in data:
                    self._action_items = data["action_items"]
                if "security_events" in data:
                    self._security_events.clear()
                    self._security_events.extend(data["security_events"])
            
            return True
        except Exception as e:
            print(f"[StateStore] Error loading state from {file_path}: {e}")
            return False
    
    def export_state_snapshot(self) -> Dict[str, Any]:
        """Export complete state snapshot as dictionary."""
        with self._lock:
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "environmental_state": dict(self._env_state),
                "agent_logs": list(self._agent_logs),
                "action_items": list(self._action_items),
                "security_events": list(self._security_events),
            }
    
    def clear_logs(self) -> None:
        """Clear all logs (useful for testing or maintenance)."""
        with self._lock:
            self._agent_logs.clear()
            self._security_events.clear()