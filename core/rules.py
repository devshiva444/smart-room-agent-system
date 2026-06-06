"""
Safety Rules Engine for Smart Room
- Temperature bounds
- Occupancy rules
- Energy limits
- Sleep mode behavior
"""

class SafetyRules:
    """Hard rules that always apply - cannot be overridden by LLM"""
    
    # Temperature bounds
    MIN_SAFE_TEMP = 16.0
    MAX_SAFE_TEMP = 35.0
    TARGET_TEMP = 24.0
    COMFORT_RANGE = 2.0
    
    # Energy limits
    MAX_HOURLY_ENERGY = 100.0  # units per hour
    
    # Action constraints
    VALID_ACTIONS = {
        0: "none",
        1: "light_on",
        2: "light_off",
        3: "fan_speed_1",
        4: "fan_speed_2",
        5: "fan_speed_3",
        6: "fan_off",
        7: "ac_on",
        8: "ac_off"
    }
    
    def __init__(self):
        self.violations = []
    
    def is_valid_action(self, action):
        """Check if action is valid integer"""
        return action in self.VALID_ACTIONS
    
    def check_temperature_safety(self, temperature):
        """
        Temperature must stay within safe bounds.
        Returns: (is_safe, corrective_action)
        """
        if temperature > self.MAX_SAFE_TEMP:
            return False, 7  # AC ON (action 7)
        if temperature < self.MIN_SAFE_TEMP:
            return False, 6  # Fan OFF (action 6)
        return True, None
    
    def check_occupancy_rules(self, occupancy, light_on, fan_speed, ac_on):
        """
        When no one in room, lights/fans should be off.
        Returns: (is_compliant, violations_list)
        """
        violations = []
        
        if not occupancy:
            if light_on:
                violations.append("light_on_without_occupancy")
            if fan_speed > 0:
                violations.append("fan_on_without_occupancy")
            if ac_on:
                violations.append("ac_on_without_occupancy")
        
        return len(violations) == 0, violations
    
    def check_sleep_mode_rules(self, sleep_mode, light_on, fan_speed):
        """
        During sleep mode (night + occupancy + dark):
        - No bright lights
        - Keep fan speed low (max 1)
        """
        violations = []
        
        if sleep_mode:
            if light_on:
                violations.append("light_on_during_sleep")
            if fan_speed > 1:
                violations.append("fan_speed_too_high_during_sleep")
        
        return len(violations) == 0, violations
    
    def check_energy_budget(self, energy_used, max_energy):
        """
        Energy usage should not exceed budget.
        Returns: (is_within_budget, ratio)
        """
        ratio = energy_used / max_energy if max_energy > 0 else 0
        return ratio <= 1.0, ratio
    
    def enforce_hard_rules(self, 
                          state_dict,
                          temperature,
                          occupancy,
                          light_on,
                          fan_speed,
                          ac_on):
        """
        Apply all hard rules and return corrected state.
        
        Args:
            state_dict: current state
            temperature, occupancy, light_on, fan_speed, ac_on: current values
        
        Returns:
            (corrected_state, violations_list)
        """
        self.violations = []
        corrected = {
            'temperature': temperature,
            'occupancy': occupancy,
            'light_on': light_on,
            'fan_speed': fan_speed,
            'ac_on': ac_on
        }
        
        # Check temperature safety
        temp_safe, corrective_action = self.check_temperature_safety(temperature)
        if not temp_safe:
            self.violations.append(f"temperature_unsafe_{int(temperature)}C")
            if corrective_action == 7:
                corrected['ac_on'] = True
            elif corrective_action == 6:
                corrected['fan_speed'] = 0
                corrected['ac_on'] = False
        
        # Check occupancy rules
        occ_compliant, occ_violations = self.check_occupancy_rules(
            occupancy, light_on, fan_speed, ac_on
        )
        if not occ_compliant:
            self.violations.extend(occ_violations)
            if not occupancy:
                corrected['light_on'] = False
                corrected['fan_speed'] = 0
                corrected['ac_on'] = False
        
        # Check sleep mode rules
        sleep_mode = state_dict.get('sleep_mode', False)
        sleep_compliant, sleep_violations = self.check_sleep_mode_rules(
            sleep_mode, corrected['light_on'], corrected['fan_speed']
        )
        if not sleep_compliant:
            self.violations.extend(sleep_violations)
            if sleep_mode:
                corrected['light_on'] = False
                if corrected['fan_speed'] > 1:
                    corrected['fan_speed'] = 1
        
        return corrected, self.violations
    
    def get_violation_penalty(self):
        """How many safety violations occurred?"""
        return len(self.violations)


# Singleton instance
_safety_rules = None

def get_safety_rules():
    """Get or create safety rules engine"""
    global _safety_rules
    if _safety_rules is None:
        _safety_rules = SafetyRules()
    return _safety_rules
