"""
Multi-Component Reward System for Smart Room
- Comfort reward: target temperature
- Energy penalty: usage cost
- Safety penalty: violations
- Stability bonus: smooth operation
- Anti-cheat penalty: spamming actions
"""

class RewardCalculator:
    """Modular reward function - easy to tune"""
    
    def __init__(self, 
                 comfort_weight=1.0, 
                 energy_weight=0.5, 
                 safety_weight=1.0,
                 stability_weight=0.3,
                 anti_cheat_weight=0.2):
        self.comfort_weight = comfort_weight
        self.energy_weight = energy_weight
        self.safety_weight = safety_weight
        self.stability_weight = stability_weight
        self.anti_cheat_weight = anti_cheat_weight
        
    def comfort_reward(self, temperature, target=24.0, comfort_range=2.0):
        """
        Reward based on how close temperature is to target.
        Max reward: 1.0 when at target ± comfort_range
        Linear decay outside range
        """
        if abs(temperature - target) <= comfort_range:
            return 1.0
        else:
            # Decay: -0.1 per degree outside comfort range
            return max(0.0, 1.0 - 0.1 * abs(temperature - target - comfort_range))
    
    def energy_penalty(self, energy_used, max_energy=1.0):
        """
        Penalize energy usage.
        Min penalty (0): no energy used
        Max penalty: -1.0 when exceeding max_energy
        """
        if energy_used <= 0:
            return 0.0
        return -min(1.0, energy_used / max_energy)
    
    def safety_penalty(self, violations=0):
        """
        Penalize safety violations (override count, extreme temps, etc)
        -0.1 per violation
        """
        return -0.1 * violations
    
    def stability_bonus(self, action_smooth, max_action_changes=3):
        """
        Bonus for smooth operation (not changing actions every step).
        Reward: 0.1 if actions smooth (< max_action_changes per 5 steps)
        """
        if action_smooth:
            return 0.1
        return 0.0
    
    def anti_cheat_penalty(self, action_spam_count=0):
        """
        Penalize repeated same action (spamming).
        -0.05 per spam action (when action == last_action)
        """
        return -0.05 * action_spam_count
    
    def calculate_total_reward(self, 
                              temperature,
                              energy_used,
                              safety_violations,
                              action_smooth,
                              action_spam_count,
                              occupancy=True):
        """
        Combine all reward components into total reward.
        
        Args:
            temperature: current temp
            energy_used: energy in this step
            safety_violations: count of safety issues
            action_smooth: boolean - was action smooth?
            action_spam_count: times same action repeated
            occupancy: is someone in room?
        
        Returns:
            total_reward: weighted sum of all components
        """
        if not occupancy:
            # When no one in room, penalize energy use heavily
            return -0.5 * energy_used
        
        comfort = self.comfort_reward(temperature)
        energy = self.energy_penalty(energy_used)
        safety = self.safety_penalty(safety_violations)
        stability = self.stability_bonus(action_smooth)
        anti_cheat = self.anti_cheat_penalty(action_spam_count)
        
        total = (
            self.comfort_weight * comfort +
            self.energy_weight * energy +
            self.safety_weight * safety +
            self.stability_weight * stability +
            self.anti_cheat_weight * anti_cheat
        )
        
        return total
    
    def get_reward_breakdown(self,
                            temperature,
                            energy_used,
                            safety_violations,
                            action_smooth,
                            action_spam_count):
        """Debug helper - see individual reward components"""
        return {
            "comfort": self.comfort_weight * self.comfort_reward(temperature),
            "energy": self.energy_weight * self.energy_penalty(energy_used),
            "safety": self.safety_weight * self.safety_penalty(safety_violations),
            "stability": self.stability_weight * self.stability_bonus(action_smooth),
            "anti_cheat": self.anti_cheat_weight * self.anti_cheat_penalty(action_spam_count)
        }


# Default singleton instance
_reward_calculator = None

def get_reward_calculator(custom_weights=None):
    """Get or create reward calculator with optional custom weights"""
    global _reward_calculator
    if _reward_calculator is None:
        if custom_weights:
            _reward_calculator = RewardCalculator(**custom_weights)
        else:
            _reward_calculator = RewardCalculator()
    return _reward_calculator
