"""
Train GRPO - Reinforcement Learning Training Pipeline
Uses DQN + policy gradients to improve the Smart Room Agent.
Demonstrates baseline vs trained performance for Hackathon evaluation.
"""

import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from collections import deque
import random
from typing import Tuple, List
import os

from environment import SmartRoomEnvironment, SmartRoomAction
# Optional: Fallback agar analytics logger na ho
try:
    from analytics.logger import get_analytics_logger
    from db.database import get_database
    HAS_DB = True
except ImportError:
    HAS_DB = False


class DQN(nn.Module):
    """Deep Q-Network for Smart Room Control"""
    def __init__(self, input_dim: int, output_dim: int, hidden_dim: int = 128):
        super(DQN, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, output_dim)
        )
    
    def forward(self, x):
        return self.network(x)


class ReplayBuffer:
    """Experience replay buffer for training stability"""
    def __init__(self, capacity: int = 10000):
        self.buffer = deque(maxlen=capacity)
    
    def push(self, state, action, reward, next_state, done):
        self.buffer.append((state, action, reward, next_state, done))
    
    def sample(self, batch_size: int) -> Tuple[List, List, List, List, List]:
        states, actions, rewards, next_states, dones = zip(*random.sample(self.buffer, batch_size))
        return (
            np.array(states),
            np.array(actions),
            np.array(rewards),
            np.array(next_states),
            np.array(dones)
        )
    
    def __len__(self):
        return len(self.buffer)


class DQNAgent:
    """DQN Agent for Smart Room"""
    def __init__(self,
                 input_dim: int = 7,
                 action_dim: int = 9,
                 learning_rate: float = 1e-3,
                 gamma: float = 0.99,
                 epsilon: float = 1.0,
                 epsilon_decay: float = 0.995,
                 use_cuda: bool = False):
        
        self.device = torch.device("cuda" if use_cuda and torch.cuda.is_available() else "cpu")
        self.action_dim = action_dim
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        
        self.q_network = DQN(input_dim, action_dim).to(self.device)
        self.target_network = DQN(input_dim, action_dim).to(self.device)
        self.target_network.load_state_dict(self.q_network.state_dict())
        
        self.optimizer = optim.Adam(self.q_network.parameters(), lr=learning_rate)
        self.loss_fn = nn.MSELoss()
        self.memory = ReplayBuffer()
    
    def select_action(self, state: np.ndarray, training: bool = True) -> int:
        if training and random.random() < self.epsilon:
            return random.randint(0, self.action_dim - 1)
        
        state_tensor = torch.from_numpy(state).float().unsqueeze(0).to(self.device)
        with torch.no_grad():
            q_values = self.q_network(state_tensor)
        
        return q_values.argmax(dim=1).item()
    
    def remember(self, state, action, reward, next_state, done):
        self.memory.push(state, action, reward, next_state, done)
    
    def replay(self, batch_size: int = 32):
        if len(self.memory) < batch_size:
            return None
        
        states, actions, rewards, next_states, dones = self.memory.sample(batch_size)
        
        states = torch.from_numpy(states).float().to(self.device)
        actions = torch.from_numpy(actions).long().to(self.device)
        rewards = torch.from_numpy(rewards).float().to(self.device)
        next_states = torch.from_numpy(next_states).float().to(self.device)
        dones = torch.from_numpy(dones).float().to(self.device)
        
        q_values = self.q_network(states).gather(1, actions.unsqueeze(1)).squeeze(1)
        
        with torch.no_grad():
            max_next_q_values = self.target_network(next_states).max(dim=1)[0]
            target_q_values = rewards + self.gamma * max_next_q_values * (1 - dones)
        
        loss = self.loss_fn(q_values, target_q_values)
        
        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.q_network.parameters(), 1.0)
        self.optimizer.step()
        
        return loss.item()
    
    def update_target_network(self):
        self.target_network.load_state_dict(self.q_network.state_dict())
    
    def decay_epsilon(self):
        self.epsilon *= self.epsilon_decay
        self.epsilon = max(0.01, self.epsilon)
    
    def save(self, filepath: str):
        torch.save(self.q_network.state_dict(), filepath)


def state_to_vector(obs) -> np.ndarray:
    """Convert observation to state vector"""
    obs_dict = obs.model_dump() if hasattr(obs, 'model_dump') else obs.dict() if hasattr(obs, 'dict') else obs.__dict__
    return np.array([
        obs_dict.get("temperature", 25.0),
        float(obs_dict.get("occupancy", False)),
        float(obs_dict.get("light_on", False)),
        float(obs_dict.get("fan_speed", 0)) / 3.0,
        float(obs_dict.get("ac_on", False)),
        1.0 if obs_dict.get("time_of_day") == "night" else 0.0,
        float(obs_dict.get("sleep_mode", False))
    ], dtype=np.float32)


class TrainerGRPO:
    """GRPO-style Trainer for Smart Room Agent"""
    def __init__(self, model_path: str = "smart_room_ai_final.pth"):
        self.env = SmartRoomEnvironment()
        self.agent = DQNAgent(use_cuda=torch.cuda.is_available())
        self.model_path = model_path
        
        if HAS_DB:
            self.logger = get_analytics_logger()
            self.database = get_database()
    
    def train_episode(self, episode_id: int) -> float:
        obs = self.env.reset()
        state = state_to_vector(obs)
        episode_reward = 0
        
        for _ in range(100):
            action = self.agent.select_action(state, training=True)
            obs = self.env.step(SmartRoomAction(action=action))
            obs_dict = obs.model_dump() if hasattr(obs, 'model_dump') else obs.dict() if hasattr(obs, 'dict') else obs.__dict__
            
            next_state = state_to_vector(obs)
            reward = obs_dict['reward']
            done = obs_dict['done']
            
            episode_reward += reward
            self.agent.remember(state, action, reward, next_state, done)
            self.agent.replay(batch_size=32)
            
            state = next_state
            if done:
                break
        
        if episode_id % 10 == 0:
            self.agent.update_target_network()
        
        self.agent.decay_epsilon()
        return episode_reward
    
    def evaluate_episode(self, episode_id: int) -> float:
        obs = self.env.reset()
        state = state_to_vector(obs)
        episode_reward = 0
        
        for _ in range(100):
            action = self.agent.select_action(state, training=False)
            obs = self.env.step(SmartRoomAction(action=action))
            obs_dict = obs.model_dump() if hasattr(obs, 'model_dump') else obs.dict() if hasattr(obs, 'dict') else obs.__dict__
            
            next_state = state_to_vector(obs)
            reward = obs_dict['reward']
            done = obs_dict['done']
            
            episode_reward += reward
            state = next_state
            if done:
                break
        
        return episode_reward
    
    def run_training(self, num_episodes: int = 100, eval_every: int = 20, save_every: int = 50):
        print(f"\n{'='*70}")
        print(f"🎓 Starting RL Deep Training (Direct Environment Mode)")
        print(f"{'='*70}")
        
        train_rewards, eval_rewards = [], []
        
        for episode in range(num_episodes):
            train_reward = self.train_episode(episode)
            train_rewards.append(train_reward)
            
            if (episode + 1) % eval_every == 0:
                eval_reward = self.evaluate_episode(episode)
                eval_rewards.append(eval_reward)
                avg_train = np.mean(train_rewards[-eval_every:])
                
                print(f"Episode {episode+1:4d} | Train Avg: {avg_train:7.2f} | Eval: {eval_reward:7.2f} | Epsilon: {self.agent.epsilon:.3f}")
                
                if HAS_DB:
                    self.database.save_metric("train_reward", avg_train, episode)
                    self.database.save_metric("eval_reward", eval_reward, episode)
            
            if (episode + 1) % save_every == 0:
                self.agent.save(self.model_path)
                print(f"💾 Checkpoint saved to {self.model_path}")
        
        self.agent.save(self.model_path)
        print(f"\n✅ Training Complete! Final model saved to {self.model_path}\n")
        return train_rewards, eval_rewards

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Train GRPO Agent")
    parser.add_argument("--episodes", type=int, default=100)
    parser.add_argument("--eval-every", type=int, default=10)
    parser.add_argument("--save-every", type=int, default=50)
    parser.add_argument("--model-path", type=str, default="smart_room_ai_final.pth")
    
    args = parser.parse_args()
    trainer = TrainerGRPO(model_path=args.model_path)
    trainer.run_training(num_episodes=args.episodes, eval_every=args.eval_every, save_every=args.save_every)