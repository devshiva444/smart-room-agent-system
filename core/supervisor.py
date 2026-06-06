"""
Action Supervisor - validates and overrides unsafe actions
- Intercepts actions from LLM
- Applies safety rules
- Logs violations
- Ensures safe operation
"""

from core.rules import get_safety_rules

class ActionSupervisor:
    """
    3-layer system: LLM → Supervisor → Environment
    Supervisor validates and potentially overrides actions
    """
    
    def __init__(self):
        self.safety_rules = get_safety_rules()
        self.last_action = None
        self.override_count = 0
        self.action_spam_threshold = 5  # If same action > 5 times, it's spam
        self.spam_count = 0
        self.violation_log = []
    
    def validate_action(self, action, occupancy):
        """
        Validate if action is in valid range.
        Returns: (is_valid, error_msg)
        """
        if not isinstance(action, int):
            return False, f"Action must be int, got {type(action)}"
        
        if not self.safety_rules.is_valid_action(action):
            return False, f"Invalid action {action}. Valid: 0-8"
        
        return True, None
    
    def check_action_spam(self, action):
        """
        Detect if agent is spamming same action repeatedly.
        This is a common "cheat" in RL - just keep sending one action.
        """
        if action == self.last_action:
            self.spam_count += 1
        else:
            self.spam_count = 0
        
        self.last_action = action
        
        is_spam = self.spam_count > self.action_spam_threshold
        return is_spam, self.spam_count
    
    def apply_safety_override(self, 
                             action,
                             temperature,
                             occupancy,
                             light_on,
                             fan_speed,
                             ac_on,
                             state_dict):
        """
        Safety rules may override LLM action.
        
        Args:
            action: LLM-suggested action
            temperature, occupancy, light_on, fan_speed, ac_on: current state
            state_dict: full state dict
        
        Returns:
            (final_action, was_overridden, violation_count)
        """
        
        # Check if action is valid
        is_valid, error_msg = self.validate_action(action, occupancy)
        if not is_valid:
            # Default safe action: do nothing
            self.violation_log.append(f"Invalid action: {error_msg}")
            return 0, True, 1
        
        # Check for spam
        is_spam, spam_count = self.check_action_spam(action)
        
        # Apply hard safety rules to current state
        corrected_state, violations = self.safety_rules.enforce_hard_rules(
            state_dict,
            temperature,
            occupancy,
            light_on,
            fan_speed,
            ac_on
        )
        
        violation_count = len(violations) + (1 if is_spam else 0)
        self.violation_log.append({
            "action": action,
            "violations": violations,
            "spam": is_spam,
            "spam_count": spam_count
        })
        
        # If safety rules had to correct state, consider overriding
        state_changed = (
            corrected_state['light_on'] != light_on or
            corrected_state['fan_speed'] != fan_speed or
            corrected_state['ac_on'] != ac_on
        )
        
        if state_changed:
            self.override_count += 1
            return action, True, violation_count
        
        return action, False, violation_count
    
    def get_supervisor_stats(self):
        """Debug info - how often did supervisor override?"""
        return {
            "total_overrides": self.override_count,
            "spam_count": self.spam_count,
            "total_violations": len(self.violation_log)
        }
    
    def reset_stats(self):
        """Reset supervisor counters for new episode"""
        self.last_action = None
        self.spam_count = 0
        self.override_count = 0
        self.violation_log = []


# Singleton instance
_supervisor = None

def get_action_supervisor():
    """Get or create action supervisor"""
    global _supervisor
    if _supervisor is None:
        _supervisor = ActionSupervisor()
    return _supervisor
