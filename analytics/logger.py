"""
Analytics Logger - Track reward, energy, actions, violations
Useful for debugging training and evaluating performance
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any


class EpisodeLogger:
    """Log episode-level metrics"""
    
    def __init__(self, episode_id: int):
        self.episode_id = episode_id
        self.timestamp = datetime.now().isoformat()
        self.steps = []
        self.episode_stats = {}
    
    def log_step(self, 
                 step: int,
                 temperature: float,
                 action: int,
                 reward: float,
                 energy_used: float,
                 occupancy: bool,
                 violations: int):
        """Log one step of the episode"""
        self.steps.append({
            "step": step,
            "temperature": round(temperature, 2),
            "action": action,
            "reward": round(reward, 4),
            "energy_used": round(energy_used, 4),
            "occupancy": occupancy,
            "violations": violations
        })
    
    def finalize(self, stats: Dict[str, Any]):
        """Finalize episode and store stats"""
        self.episode_stats = stats
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "episode_id": self.episode_id,
            "timestamp": self.timestamp,
            "num_steps": len(self.steps),
            "stats": self.episode_stats,
            "steps": self.steps
        }


class AnalyticsLogger:
    """Main analytics system - track training progress"""
    
    def __init__(self, log_dir: str = "./logs"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        
        self.episodes: List[EpisodeLogger] = []
        self.current_episode: EpisodeLogger = None
    
    def start_episode(self, episode_id: int):
        """Start logging a new episode"""
        self.current_episode = EpisodeLogger(episode_id)
    
    def log_step(self,
                 step: int,
                 temperature: float,
                 action: int,
                 reward: float,
                 energy_used: float,
                 occupancy: bool = True,
                 violations: int = 0):
        """Log a step within current episode"""
        if self.current_episode is None:
            raise RuntimeError("No episode started. Call start_episode() first.")
        
        self.current_episode.log_step(
            step, temperature, action, reward, energy_used, occupancy, violations
        )
    
    def end_episode(self, stats: Dict[str, Any]):
        """End episode logging and save stats"""
        if self.current_episode is None:
            raise RuntimeError("No episode to end.")
        
        self.current_episode.finalize(stats)
        self.episodes.append(self.current_episode)
        self.current_episode = None
    
    def get_episode_summary(self, episode_idx: int = -1) -> Dict[str, Any]:
        """Get summary of an episode"""
        if not self.episodes:
            return {}
        
        episode = self.episodes[episode_idx]
        return episode.episode_stats
    
    def get_training_summary(self) -> Dict[str, Any]:
        """Get overall training summary"""
        if not self.episodes:
            return {}
        
        total_reward = sum(ep.episode_stats.get("total_reward", 0) for ep in self.episodes)
        avg_reward = total_reward / len(self.episodes)
        total_energy = sum(ep.episode_stats.get("total_energy", 0) for ep in self.episodes)
        
        return {
            "num_episodes": len(self.episodes),
            "total_episodes": len(self.episodes),
            "avg_reward": round(avg_reward, 4),
            "max_reward": max((ep.episode_stats.get("total_reward", 0) for ep in self.episodes), default=0),
            "min_reward": min((ep.episode_stats.get("total_reward", 0) for ep in self.episodes), default=0),
            "total_energy": round(total_energy, 2),
            "avg_energy": round(total_energy / len(self.episodes), 2)
        }
    
    def save_logs(self, filename: str = "training_log.json"):
        """Save all logs to JSON file"""
        filepath = os.path.join(self.log_dir, filename)
        
        logs = {
            "saved_at": datetime.now().isoformat(),
            "episodes": [ep.to_dict() for ep in self.episodes],
            "summary": self.get_training_summary()
        }
        
        with open(filepath, 'w') as f:
            json.dump(logs, f, indent=2)
        
        print(f"[Logger] Saved logs to {filepath}")
        return filepath
    
    def print_episode_report(self, episode_idx: int = -1):
        """Print human-readable episode report"""
        if not self.episodes:
            print("[Logger] No episodes logged yet.")
            return
        
        episode = self.episodes[episode_idx]
        stats = episode.episode_stats
        
        print(f"\n{'='*60}")
        print(f"Episode {episode.episode_id} Report")
        print(f"{'='*60}")
        print(f"Total Steps: {stats.get('total_steps', 'N/A')}")
        print(f"Total Reward: {stats.get('total_reward', 'N/A'):.4f}")
        print(f"Avg Reward: {stats.get('avg_reward', 'N/A'):.4f}")
        print(f"Total Energy: {stats.get('total_energy', 'N/A'):.2f}")
        print(f"Safety Violations: {stats.get('safety_violations', 'N/A')}")
        print(f"Supervisor Overrides: {stats.get('supervisor_overrides', 'N/A')}")
        print(f"{'='*60}\n")
    
    def print_training_report(self):
        """Print overall training summary"""
        summary = self.get_training_summary()
        
        print(f"\n{'='*60}")
        print(f"Training Summary")
        print(f"{'='*60}")
        print(f"Episodes Completed: {summary.get('num_episodes', 0)}")
        print(f"Avg Reward: {summary.get('avg_reward', 'N/A'):.4f}")
        print(f"Max Reward: {summary.get('max_reward', 'N/A'):.4f}")
        print(f"Min Reward: {summary.get('min_reward', 'N/A'):.4f}")
        print(f"Total Energy: {summary.get('total_energy', 'N/A'):.2f}")
        print(f"Avg Energy/Episode: {summary.get('avg_energy', 'N/A'):.2f}")
        print(f"{'='*60}\n")


# Singleton instance
_logger = None

def get_analytics_logger(log_dir: str = "./logs") -> AnalyticsLogger:
    """Get or create global analytics logger"""
    global _logger
    if _logger is None:
        _logger = AnalyticsLogger(log_dir)
    return _logger
