"""
Environmental Agent - The Brain
Wraps existing DQN inference logic and executes room control actions.

Responsibilities:
- Load pre-trained DQN model (smart_room_ai_final.pth)
- Accept current room state (temperature, occupancy, etc.)
- Compute optimal action using Deep Q-Networks
- Return device adjustments (AC, lights, screen, fan)
"""

import torch
import torch.nn as nn
import numpy as np
import os
from typing import Dict, Any, Tuple
from pathlib import Path


class DQN(nn.Module):
    """Deep Q-Network architecture matching the pre-trained model."""
    
    def __init__(self, input_dim: int = 7, output_dim: int = 9):
        super(DQN, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 128),
            nn.ReLU(),
            nn.Linear(128, output_dim)
        )
    
    def forward(self, x):
        return self.network(x)


def state_to_vector(obs_dict: Dict[str, Any]) -> np.ndarray:
    """
    Convert observation dictionary to neural network state vector.
    Matches the encoding used during training.
    """
    return np.array([
        obs_dict.get("temperature", 25.0),
        float(obs_dict.get("occupancy", False)),
        float(obs_dict.get("light_on", False)),
        float(obs_dict.get("fan_speed", 0)) / 3.0,
        float(obs_dict.get("ac_on", False)),
        1.0 if obs_dict.get("time_of_day") == "night" else 0.0,
        float(obs_dict.get("sleep_mode", False))
    ], dtype=np.float32)


class EnvironmentalAgent:
    """
    Environmental Agent - Executive Controller for Smart Room
    
    Takes current room state and computes optimal environmental adjustments
    using the pre-trained DQN policy.
    """
    
    # Action mapping: action_id -> (device, control)
    ACTION_MAP = {
        0: {"device": "light", "command": "off"},
        1: {"device": "light", "command": "on"},
        2: {"device": "fan", "command": "off"},
        3: {"device": "fan", "command": "low"},
        4: {"device": "fan", "command": "high"},
        5: {"device": "ac", "command": "off"},
        6: {"device": "ac", "command": "cool_18"},
        7: {"device": "ac", "command": "cool_22"},
        8: {"device": "screen", "command": "toggle"},
    }
    
    def __init__(self, model_path: str = None):
        """
        Initialize Environmental Agent with pre-trained DQN model.
        
        Args:
            model_path: Path to smart_room_ai_final.pth. If None, searches default locations.
        """
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = self._load_dqn_model(model_path)
        self.last_action = None
        self.inference_count = 0
    
    def _load_dqn_model(self, model_path: str = None) -> DQN:
        """
        Load pre-trained DQN model safely.
        
        Args:
            model_path: Explicit path to model file. If None, search standard locations.
            
        Returns:
            Loaded DQN model on appropriate device.
        """
        model = DQN(input_dim=7, output_dim=9)
        
        # Determine model path
        if model_path is None:
            base = Path(__file__).parent.parent
            candidates = [
                base / "outputs" / "smart_room_ai_final.pth",
                base / "smart_room_ai_final.pth",
            ]
            model_path = None
            for candidate in candidates:
                if candidate.exists():
                    model_path = str(candidate)
                    break
        
        # Load model if found
        if model_path and os.path.exists(model_path):
            try:
                state_dict = torch.load(
                    model_path,
                    map_location=self.device,
                    weights_only=True
                )
                model.load_state_dict(state_dict)
                print(f"[EnvironmentalAgent] DQN model loaded from: {model_path}")
            except Exception as e:
                print(f"[EnvironmentalAgent] Warning: Failed to load model from {model_path}: {e}")
        else:
            print(f"[EnvironmentalAgent] Warning: Model not found. Using untrained network.")
        
        model.to(self.device)
        model.eval()
        return model
    
    def infer_action(self, room_state: Dict[str, Any]) -> int:
        """
        Infer optimal action from current room state using DQN.
        
        Args:
            room_state: Dictionary with keys like temperature, occupancy, light_on, etc.
            
        Returns:
            Action ID (0-8) representing optimal control command.
        """
        state_vec = state_to_vector(room_state)
        state_tensor = torch.from_numpy(state_vec).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            q_values = self.model(state_tensor)
            action = q_values.argmax(dim=1).item()
        
        self.last_action = action
        self.inference_count += 1
        
        return action
    
    def execute_action(self, room_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute full inference + action mapping pipeline.
        
        Args:
            room_state: Current room observation.
            
        Returns:
            Dictionary with optimal device adjustments and metadata.
        """
        action_id = self.infer_action(room_state)
        action_spec = self.ACTION_MAP.get(action_id, {})
        
        return {
            "action_id": action_id,
            "device": action_spec.get("device", "unknown"),
            "command": action_spec.get("command", "noop"),
            "q_values_top_3": self._get_top_actions(room_state),
            "metadata": {
                "temperature_current": room_state.get("temperature", 25.0),
                "occupancy": room_state.get("occupancy", False),
                "time_of_day": room_state.get("time_of_day", "day"),
            }
        }
    
    def _get_top_actions(self, room_state: Dict[str, Any]) -> list:
        """Return top 3 actions by Q-value (for debugging/transparency)."""
        state_vec = state_to_vector(room_state)
        state_tensor = torch.from_numpy(state_vec).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            q_values = self.model(state_tensor).squeeze(0).cpu().numpy()
        
        top_3_indices = np.argsort(q_values)[-3:][::-1]
        return [
            {
                "rank": i + 1,
                "action_id": int(idx),
                "q_value": float(q_values[idx]),
                "description": self.ACTION_MAP.get(idx, {}).get("command", "unknown")
            }
            for i, idx in enumerate(top_3_indices)
        ]
    
    def get_stats(self) -> Dict[str, Any]:
        """Return agent statistics."""
        return {
            "agent_type": "Environmental",
            "model_device": str(self.device),
            "inferences_executed": self.inference_count,
            "last_action": self.last_action,
        }