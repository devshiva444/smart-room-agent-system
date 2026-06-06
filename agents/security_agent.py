"""
Security Agent - The Guard
Validates inputs, detects prompt injections, and enforces safety policies.
Now fully upgraded to prevent alphabetical Enum comparison bugs, regex compilation errors,
and false-positive blocking of standard meeting terms.
"""

import re
from typing import Dict, Any, Tuple, List
from datetime import datetime
from enum import Enum


class ThreatLevel(Enum):
    """Security threat classification levels."""
    SAFE = "safe"
    WARNING = "warning"
    CRITICAL = "critical"


class SecurityAgent:
    """
    Security Agent - Safety Validator and Policy Enforcer
    
    Acts as the guardian of the agent swarm, ensuring:
    - Environmental parameters stay within safe bounds
    - No prompt injection or adversarial inputs reach other agents
    - User authorization is validated
    - All security events are logged for auditing
    """
    
    # Threat level weights for proper comparison (not alphabetical)
    LEVEL_WEIGHTS = {
        ThreatLevel.SAFE: 0,
        ThreatLevel.WARNING: 1,
        ThreatLevel.CRITICAL: 2,
    }
    
    # Environmental control bounds
    SAFE_BOUNDS = {
        "temperature": {"min": 15.0, "max": 32.0, "emergency_min": 10.0, "emergency_max": 40.0},
        "fan_speed": {"min": 0, "max": 3},
        "brightness": {"min": 0, "max": 100},
    }
    
    # Suspicious pattern signatures - FIXED: Resolved the trailing unbalanced parenthesis error
    INJECTION_PATTERNS = [
        r"(?i)(union\s+select|select\s+.*\s+from|insert\s+into|delete\s+from|drop\s+table)",  # SQL injection (improved)
        r"(?i)(\bsql\b.*(\bunion\b|select|insert|delete|drop))",  # Original SQL pattern
        r"(?i)(javascript:|onerror=|onclick=|<script)",  # XSS attempts
        r"(?i)(\$\{.*\}|\{\{.*\}\})",  # Template injection
        r"(?i)(exec\s*\(|eval\s*\(|__import__|subprocess)",  # Code execution (properly escaped)
        r"(?i)(chmod|rm\s+-rf|del\s+/|format\s+c:)",  # Destructive commands
        r"(?i)(password|secret|apikey|token).*:.*[a-zA-Z0-9]{8,}",  # Fixed unescaped trailing parenthesis
    ]
    
    # Keywords indicating unauthorized operations
    UNAUTHORIZED_KEYWORDS = [
        "override", "bypass", "disable_safety", "force", "admin_mode",
        "root_access", "sudo", "superuser", "unlimited", "no_limits"
    ]
    
    def __init__(self):
        """Initialize Security Agent."""
        self.requests_validated = 0
        self.threats_detected = 0
        self.blocked_requests = 0
        self.security_log: List[Dict[str, Any]] = []
    
    def validate_environmental_command(self, command: Dict[str, Any]) -> Tuple[bool, str, ThreatLevel]:
        """
        Validate an environmental control command for safety.
        
        Args:
            command: Command dictionary with device and parameters.
            
        Returns:
            Tuple of (is_safe: bool, reason: str, threat_level: ThreatLevel)
        """
        self.requests_validated += 1
        
        try:
            device = command.get("device", "").lower()
            params = command.get("params", {})
            
            # Check for injection patterns in command structure
            threat_level = self._check_injection_patterns(command)
            if threat_level == ThreatLevel.CRITICAL:
                self.threats_detected += 1
                self.blocked_requests += 1
                self._log_security_event("injection_detected", command, threat_level)
                return False, "Possible injection attack detected", threat_level
            
            # Validate temperature bounds
            if device == "ac" or device == "thermostat":
                if "target_temp" in params:
                    target_temp = float(params["target_temp"])
                    bounds = self.SAFE_BOUNDS["temperature"]
                    if target_temp < bounds["emergency_min"] or target_temp > bounds["emergency_max"]:
                        self.threats_detected += 1
                        self.blocked_requests += 1
                        self._log_security_event("out_of_bounds", command, ThreatLevel.CRITICAL)
                        return False, f"Temperature {target_temp}°C is out of safe bounds [{bounds['min']}-{bounds['max']}°C]", ThreatLevel.CRITICAL
                    elif target_temp < bounds["min"] or target_temp > bounds["max"]:
                        self._log_security_event("boundary_warning", command, ThreatLevel.WARNING)
                        return True, f"Temperature {target_temp}°C is at edge of comfort zone", ThreatLevel.WARNING
            
            # Validate fan speed
            if device == "fan":
                if "speed" in params:
                    speed = int(params["speed"])
                    bounds = self.SAFE_BOUNDS["fan_speed"]
                    if speed < bounds["min"] or speed > bounds["max"]:
                        self.threats_detected += 1
                        self.blocked_requests += 1
                        self._log_security_event("invalid_parameter", command, ThreatLevel.CRITICAL)
                        return False, f"Fan speed {speed} is invalid. Valid range: {bounds['min']}-{bounds['max']}", ThreatLevel.CRITICAL
            
            # Validate brightness
            if device == "light" or device == "screen":
                if "brightness" in params:
                    brightness = int(params["brightness"])
                    bounds = self.SAFE_BOUNDS["brightness"]
                    if brightness < bounds["min"] or brightness > bounds["max"]:
                        self.threats_detected += 1
                        self.blocked_requests += 1
                        self._log_security_event("invalid_parameter", command, ThreatLevel.CRITICAL)
                        return False, f"Brightness {brightness}% is invalid. Valid range: {bounds['min']}-{bounds['max']}%", ThreatLevel.CRITICAL
            
            # Check for unauthorized operation keywords
            for keyword in self.UNAUTHORIZED_KEYWORDS:
                if keyword.lower() in str(command).lower():
                    self.threats_detected += 1
                    self._log_security_event("unauthorized_operation", command, ThreatLevel.WARNING)
                    return True, f"Warning: Potentially unauthorized operation detected ({keyword})", ThreatLevel.WARNING
            
            self._log_security_event("validation_success", command, ThreatLevel.SAFE)
            return True, "Command validated successfully", ThreatLevel.SAFE
            
        except Exception as e:
            self.threats_detected += 1
            self.blocked_requests += 1
            self._log_security_event("validation_error", {"error": str(e)}, ThreatLevel.CRITICAL)
            return False, f"Validation error: {str(e)}", ThreatLevel.CRITICAL
    
    def validate_user_input(self, user_input: str, context: str = "general") -> Tuple[bool, str, ThreatLevel]:
        """
        Validate raw user input for injection attacks and malicious content.
        
        Args:
            user_input: Raw text input from user.
            context: Context of input (e.g., "transcript", "command", "query").
            
        Returns:
            Tuple of (is_safe: bool, reason: str, threat_level: ThreatLevel)
        """
        self.requests_validated += 1
        
        if not user_input or not isinstance(user_input, str):
            return True, "Empty input", ThreatLevel.SAFE
        
        # SMART KEYWORD SCANNING: We only block actual malicious override/bypass phrases.
        # This allows standard corporate words like "override", "force", and "unlimited" to pass safely!
        user_input_lower = user_input.lower()
        critical_bypass_patterns = [
            r"\bsudo\b", 
            r"bypass\s+safety", 
            r"disable\s+safety", 
            r"ignore\s+security",
            r"sudo\s+override",
            r"admin\s+mode\s+override",
            r"disable\s+validation"
        ]
        
        for pattern in critical_bypass_patterns:
            if re.search(pattern, user_input_lower):
                self.threats_detected += 1
                self.blocked_requests += 1
                self._log_security_event("unauthorized_keyword_blocked", {"context": context, "pattern": pattern, "sample": user_input[:100]}, ThreatLevel.CRITICAL)
                return False, f"Unauthorized bypass pattern detected: {pattern}", ThreatLevel.CRITICAL
        
        # Check for injection patterns with safety try-except to prevent unhandled crashing
        try:
            threat_level = self._check_injection_patterns({"input": user_input})
        except Exception as e:
            self.threats_detected += 1
            self.blocked_requests += 1
            self._log_security_event("regex_compilation_exception", {"error": str(e)}, ThreatLevel.CRITICAL)
            return False, f"Security validation error: {str(e)}", ThreatLevel.CRITICAL
        
        if threat_level == ThreatLevel.CRITICAL:
            self.threats_detected += 1
            self.blocked_requests += 1
            self._log_security_event("injection_detected", {"context": context, "sample": user_input[:100]}, threat_level)
            return False, "Malicious input pattern detected", threat_level
        elif threat_level == ThreatLevel.WARNING:
            self._log_security_event("suspicious_input", {"context": context, "sample": user_input[:100]}, threat_level)
            return True, "Input contains suspicious patterns, proceed with caution", threat_level
        
        self._log_security_event("input_validation_success", {"context": context}, ThreatLevel.SAFE)
        return True, "Input validated", ThreatLevel.SAFE
    
    def validate_action_item(self, action_item: Dict[str, Any]) -> Tuple[bool, str, ThreatLevel]:
        """
        Validate an action item before execution.
        
        Args:
            action_item: Action item from Productivity Agent.
            
        Returns:
            Tuple of (is_safe: bool, reason: str, threat_level: ThreatLevel)
        """
        self.requests_validated += 1
        
        # Check task description for injection patterns
        task = action_item.get("task", "")
        threat_level = self._check_injection_patterns({"task": task})
        
        if threat_level == ThreatLevel.CRITICAL:
            self.threats_detected += 1
            self.blocked_requests += 1
            self._log_security_event("dangerous_action_item", action_item, threat_level)
            return False, "Action item contains potentially dangerous content", threat_level
        
        # Verify assignee field is reasonable
        assignee = action_item.get("assignee", "").lower()
        if assignee and not self._is_valid_assignee(assignee):
            self._log_security_event("invalid_assignee", action_item, ThreatLevel.WARNING)
            return True, f"Unusual assignee pattern: {assignee}", ThreatLevel.WARNING
        
        self._log_security_event("action_item_validated", action_item, ThreatLevel.SAFE)
        return True, "Action item validated", ThreatLevel.SAFE
    
    def _check_injection_patterns(self, data: Any, max_depth: int = 3) -> ThreatLevel:
        """
        Recursively check data structure for injection patterns.
        
        Args:
            data: Data to scan (dict, list, or string).
            max_depth: Maximum recursion depth.
            
        Returns:
            Highest threat level detected.
        """
        if max_depth <= 0:
            return ThreatLevel.SAFE
        
        threat = ThreatLevel.SAFE
        
        if isinstance(data, dict):
            for value in data.values():
                detected = self._check_injection_patterns(value, max_depth - 1)
                if self.LEVEL_WEIGHTS[detected] > self.LEVEL_WEIGHTS[threat]:
                    threat = detected
        elif isinstance(data, list):
            for item in data:
                detected = self._check_injection_patterns(item, max_depth - 1)
                if self.LEVEL_WEIGHTS[detected] > self.LEVEL_WEIGHTS[threat]:
                    threat = detected
        elif isinstance(data, str):
            for pattern in self.INJECTION_PATTERNS:
                if re.search(pattern, data):
                    return ThreatLevel.CRITICAL
            
            # Check for suspicious length or encoding
            if len(data) > 10000:
                threat = ThreatLevel.WARNING
        
        return threat
    
    def _is_valid_assignee(self, assignee: str) -> bool:
        """Check if assignee name is reasonable."""
        pattern = r"^[a-z0-9_\-\.@]+$"
        return bool(re.match(pattern, assignee)) and len(assignee) < 100
    
    def _log_security_event(self, event_type: str, data: Any, threat_level: ThreatLevel) -> None:
        """Log a security event for auditing."""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "threat_level": threat_level.value,
            "data_summary": str(data)[:200] if data else None,
        }
        self.security_log.append(event)
    
    def get_stats(self) -> Dict[str, Any]:
        """Return agent statistics."""
        return {
            "agent_type": "Security",
            "requests_validated": self.requests_validated,
            "threats_detected": self.threats_detected,
            "blocked_requests": self.blocked_requests,
            "threat_detection_rate": (
                self.threats_detected / self.requests_validated
                if self.requests_validated > 0 else 0
            ),
            "security_log_entries": len(self.security_log),
        }
    
    def get_security_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent security log entries."""
        return self.security_log[-limit:]
    
    def clear_security_log(self) -> None:
        """Clear security log (for testing or maintenance)."""
        self.security_log.clear()







# """
# Security Agent - The Guard
# Validates inputs, detects prompt injections, and enforces safety policies.

# Responsibilities:
# - Validate environmental control parameters (temperature bounds, etc.)
# - Detect prompt injection attempts and adversarial inputs
# - Enforce authorization policies
# - Log security events and suspicious activity
# """

# import re
# from typing import Dict, Any, Tuple, List
# from datetime import datetime
# from enum import Enum

# class ThreatLevel(Enum):
#     """Security threat classification levels."""
#     SAFE = "safe"
#     WARNING = "warning"
#     CRITICAL = "critical"

# class SecurityAgent:
#     """
#     Security Agent - Safety Validator and Policy Enforcer
    
#     Acts as the guardian of the agent swarm, ensuring:
#     - Environmental parameters stay within safe bounds
#     - No prompt injection or adversarial inputs reach other agents
#     - User authorization is validated
#     - All security events are logged for auditing
#     """
    
#     # Threat level weights for proper comparison (not alphabetical)
#     LEVEL_WEIGHTS = {
#         ThreatLevel.SAFE: 0,
#         ThreatLevel.WARNING: 1,
#         ThreatLevel.CRITICAL: 2,
#     }
    
#     # Environmental control bounds
#     SAFE_BOUNDS = {
#         "temperature": {"min": 15.0, "max": 32.0, "emergency_min": 10.0, "emergency_max": 40.0},
#         "fan_speed": {"min": 0, "max": 3},
#         "brightness": {"min": 0, "max": 100},
#     }
    
#     # Suspicious pattern signatures - IMPROVED: Now catches SQL without "sql" keyword
#     INJECTION_PATTERNS = [
#         r"(?i)(union\s+select|select\s+.*\s+from|insert\s+into|delete\s+from|drop\s+table)",  # SQL injection (improved)
#         r"(?i)(\bsql\b.*(\bunion\b|select|insert|delete|drop))",  # Original SQL pattern
#         r"(?i)(javascript:|onerror=|onclick=|<script)",  # XSS attempts
#         r"(?i)(\$\{.*\}|\{\{.*\}\})",  # Template injection
#         r"(?i)(exec\(|eval\(|__import__|subprocess)",  # Code execution
#         r"(?i)(chmod|rm\s+-rf|del\s+/|format\s+c:)",  # Destructive commands
#         r"(?i)(password|secret|apikey|token).*:.*[a-zA-Z0-9]{8,})",  # Credential leak attempts
#     ]
    
#     # Keywords indicating unauthorized operations
#     UNAUTHORIZED_KEYWORDS = [
#         "override", "bypass", "disable_safety", "force", "admin_mode",
#         "root_access", "sudo", "superuser", "unlimited", "no_limits"
#     ]
    
#     def __init__(self):
#         """Initialize Security Agent."""
#         self.requests_validated = 0
#         self.threats_detected = 0
#         self.blocked_requests = 0
#         self.security_log: List[Dict[str, Any]] = []
    
#     def validate_environmental_command(self, command: Dict[str, Any]) -> Tuple[bool, str, ThreatLevel]:
#         """
#         Validate an environmental control command for safety.
        
#         Args:
#             command: Command dictionary with device and parameters.
            
#         Returns:
#             Tuple of (is_safe: bool, reason: str, threat_level: ThreatLevel)
#         """
#         self.requests_validated += 1
        
#         try:
#             device = command.get("device", "").lower()
#             params = command.get("params", {})
            
#             # Check for injection patterns in command structure
#             threat_level = self._check_injection_patterns(command)
#             if threat_level == ThreatLevel.CRITICAL:
#                 self.threats_detected += 1
#                 self.blocked_requests += 1
#                 self._log_security_event("injection_detected", command, threat_level)
#                 return False, "Possible injection attack detected", threat_level
            
#             # Validate temperature bounds
#             if device == "ac" or device == "thermostat":
#                 if "target_temp" in params:
#                     target_temp = float(params["target_temp"])
#                     bounds = self.SAFE_BOUNDS["temperature"]
#                     if target_temp < bounds["emergency_min"] or target_temp > bounds["emergency_max"]:
#                         self.threats_detected += 1
#                         self.blocked_requests += 1
#                         self._log_security_event("out_of_bounds", command, ThreatLevel.CRITICAL)
#                         return False, f"Temperature {target_temp}°C is out of safe bounds [{bounds['min']}-{bounds['max']}°C]", ThreatLevel.CRITICAL
#                     elif target_temp < bounds["min"] or target_temp > bounds["max"]:
#                         self._log_security_event("boundary_warning", command, ThreatLevel.WARNING)
#                         return True, f"Temperature {target_temp}°C is at edge of comfort zone", ThreatLevel.WARNING
            
#             # Validate fan speed
#             if device == "fan":
#                 if "speed" in params:
#                     speed = int(params["speed"])
#                     bounds = self.SAFE_BOUNDS["fan_speed"]
#                     if speed < bounds["min"] or speed > bounds["max"]:
#                         self.threats_detected += 1
#                         self.blocked_requests += 1
#                         self._log_security_event("invalid_parameter", command, ThreatLevel.CRITICAL)
#                         return False, f"Fan speed {speed} is invalid. Valid range: {bounds['min']}-{bounds['max']}", ThreatLevel.CRITICAL
            
#             # Validate brightness
#             if device == "light" or device == "screen":
#                 if "brightness" in params:
#                     brightness = int(params["brightness"])
#                     bounds = self.SAFE_BOUNDS["brightness"]
#                     if brightness < bounds["min"] or brightness > bounds["max"]:
#                         self.threats_detected += 1
#                         self.blocked_requests += 1
#                         self._log_security_event("invalid_parameter", command, ThreatLevel.CRITICAL)
#                         return False, f"Brightness {brightness}% is invalid. Valid range: {bounds['min']}-{bounds['max']}%", ThreatLevel.CRITICAL
            
#             # Check for unauthorized operation keywords
#             for keyword in self.UNAUTHORIZED_KEYWORDS:
#                 if keyword.lower() in str(command).lower():
#                     self.threats_detected += 1
#                     self._log_security_event("unauthorized_operation", command, ThreatLevel.WARNING)
#                     return True, f"Warning: Potentially unauthorized operation detected ({keyword})", ThreatLevel.WARNING
            
#             self._log_security_event("validation_success", command, ThreatLevel.SAFE)
#             return True, "Command validated successfully", ThreatLevel.SAFE
            
#         except Exception as e:
#             self.threats_detected += 1
#             self.blocked_requests += 1
#             self._log_security_event("validation_error", {"error": str(e)}, ThreatLevel.CRITICAL)
#             return False, f"Validation error: {str(e)}", ThreatLevel.CRITICAL
    
#     def validate_user_input(self, user_input: str, context: str = "general") -> Tuple[bool, str, ThreatLevel]:
#         """
#         Validate raw user input for injection attacks and malicious content.
        
#         Args:
#             user_input: Raw text input from user.
#             context: Context of input (e.g., "transcript", "command", "query").
            
#         Returns:
#             Tuple of (is_safe: bool, reason: str, threat_level: ThreatLevel)
#         """
#         self.requests_validated += 1
        
#         if not user_input or not isinstance(user_input, str):
#             return True, "Empty input", ThreatLevel.SAFE
        
#         # DIRECT KEYWORD SCANNING: Check for unauthorized keywords FIRST
#         # This catches "SUDO OVERRIDE" and similar attacks in raw text input
#         user_input_lower = user_input.lower()
#         for keyword in self.UNAUTHORIZED_KEYWORDS:
#             if keyword.lower() in user_input_lower:
#                 self.threats_detected += 1
#                 self.blocked_requests += 1
#                 self._log_security_event("unauthorized_keyword_detected", {"context": context, "keyword": keyword, "sample": user_input[:100]}, ThreatLevel.CRITICAL)
#                 return False, f"Unauthorized operation keyword detected: {keyword}", ThreatLevel.CRITICAL
        
#         # Check for injection patterns
#         threat_level = self._check_injection_patterns({"input": user_input})
        
#         if threat_level == ThreatLevel.CRITICAL:
#             self.threats_detected += 1
#             self.blocked_requests += 1
#             self._log_security_event("injection_detected", {"context": context, "sample": user_input[:100]}, threat_level)
#             return False, "Malicious input pattern detected", threat_level
#         elif threat_level == ThreatLevel.WARNING:
#             self._log_security_event("suspicious_input", {"context": context, "sample": user_input[:100]}, threat_level)
#             return True, "Input contains suspicious patterns, proceed with caution", threat_level
        
#         self._log_security_event("input_validation_success", {"context": context}, ThreatLevel.SAFE)
#         return True, "Input validated", ThreatLevel.SAFE
    
#     def validate_action_item(self, action_item: Dict[str, Any]) -> Tuple[bool, str, ThreatLevel]:
#         """
#         Validate an action item before execution.
        
#         Args:
#             action_item: Action item from Productivity Agent.
            
#         Returns:
#             Tuple of (is_safe: bool, reason: str, threat_level: ThreatLevel)
#         """
#         self.requests_validated += 1
        
#         # Check task description for injection patterns
#         task = action_item.get("task", "")
#         threat_level = self._check_injection_patterns({"task": task})
        
#         if threat_level == ThreatLevel.CRITICAL:
#             self.threats_detected += 1
#             self.blocked_requests += 1
#             self._log_security_event("dangerous_action_item", action_item, threat_level)
#             return False, "Action item contains potentially dangerous content", threat_level
        
#         # Verify assignee field is reasonable
#         assignee = action_item.get("assignee", "").lower()
#         if assignee and not self._is_valid_assignee(assignee):
#             self._log_security_event("invalid_assignee", action_item, ThreatLevel.WARNING)
#             return True, f"Unusual assignee pattern: {assignee}", ThreatLevel.WARNING
        
#         self._log_security_event("action_item_validated", action_item, ThreatLevel.SAFE)
#         return True, "Action item validated", ThreatLevel.SAFE
    
#     def _check_injection_patterns(self, data: Any, max_depth: int = 3) -> ThreatLevel:
#         """
#         Recursively check data structure for injection patterns.
        
#         Args:
#             data: Data to scan (dict, list, or string).
#             max_depth: Maximum recursion depth.
            
#         Returns:
#             Highest threat level detected.
#         """
#         if max_depth <= 0:
#             return ThreatLevel.SAFE
        
#         threat = ThreatLevel.SAFE
        
#         if isinstance(data, dict):
#             for value in data.values():
#                 detected = self._check_injection_patterns(value, max_depth - 1)
#                 if self.LEVEL_WEIGHTS[detected] > self.LEVEL_WEIGHTS[threat]:
#                     threat = detected
#         elif isinstance(data, list):
#             for item in data:
#                 detected = self._check_injection_patterns(item, max_depth - 1)
#                 if self.LEVEL_WEIGHTS[detected] > self.LEVEL_WEIGHTS[threat]:
#                     threat = detected
#         elif isinstance(data, str):
#             for pattern in self.INJECTION_PATTERNS:
#                 if re.search(pattern, data):
#                     return ThreatLevel.CRITICAL
            
#             # Check for suspicious length or encoding
#             if len(data) > 10000:
#                 threat = ThreatLevel.WARNING
        
#         return threat
    
#     def _is_valid_assignee(self, assignee: str) -> bool:
#         """Check if assignee name is reasonable."""
#         # Simple heuristic: assignee should be alphanumeric + underscores/hyphens
#         pattern = r"^[a-z0-9_\-\.@]+$"
#         return bool(re.match(pattern, assignee)) and len(assignee) < 100
    
#     def _log_security_event(self, event_type: str, data: Any, threat_level: ThreatLevel) -> None:
#         """Log a security event for auditing."""
#         event = {
#             "timestamp": datetime.utcnow().isoformat(),
#             "event_type": event_type,
#             "threat_level": threat_level.value,
#             "data_summary": str(data)[:200] if data else None,
#         }
#         self.security_log.append(event)
    
#     def get_stats(self) -> Dict[str, Any]:
#         """Return agent statistics."""
#         return {
#             "agent_type": "Security",
#             "requests_validated": self.requests_validated,
#             "threats_detected": self.threats_detected,
#             "blocked_requests": self.blocked_requests,
#             "threat_detection_rate": (
#                 self.threats_detected / self.requests_validated
#                 if self.requests_validated > 0 else 0
#             ),
#             "security_log_entries": len(self.security_log),
#         }
    
#     def get_security_log(self, limit: int = 50) -> List[Dict[str, Any]]:
#         """Get recent security log entries."""
#         return self.security_log[-limit:]
    
#     def clear_security_log(self) -> None:
#         """Clear security log (for testing or maintenance)."""
#         self.security_log.clear()