import torch
import torch.nn as nn
import numpy as np
import os
from typing import Dict, Any

# ==========================================
# DQN Network Definition
# ==========================================
class DQN(nn.Module):
    def __init__(self, input_dim: int, output_dim: int):
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
    """Observation dictionary ko neural network ke vector me convert karta he"""
    return np.array([
        obs_dict.get("temperature", 25.0),
        float(obs_dict.get("occupancy", False)),
        float(obs_dict.get("light_on", False)),
        float(obs_dict.get("fan_speed", 0)) / 3.0,
        float(obs_dict.get("ac_on", False)),
        1.0 if obs_dict.get("time_of_day") == "night" else 0.0,
        float(obs_dict.get("sleep_mode", False))
    ], dtype=np.float32)

# ==========================================
# RL Worker Wrapper Class
# ==========================================
class RLWorker:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = self._load_dqn()

    def _load_dqn(self):
        """Pre-trained model ko safe tarike se load karta he"""
        model = DQN(7, 9)
        model_path = os.getenv("MODEL_PATH", "smart_room_ai_final.pth")
        if os.path.exists(model_path):
            try:
                # Sirf weights load karo (safe tarika)
                model.load_state_dict(torch.load(model_path, map_location=self.device, weights_only=True))
            except Exception as e:
                print(f"Model load error: {e}")
        model.to(self.device)
        model.eval()
        return model

    def propose_action(self, obs_dict: Dict[str, Any]) -> int:
        """Environment state ke hisab se action propose karta he"""
        state_vec = state_to_vector(obs_dict)
        state_tensor = torch.from_numpy(state_vec).unsqueeze(0).to(self.device)
        with torch.no_grad():
            q_values = self.model(state_tensor)
            action = q_values.argmax(dim=1).item()
        return action