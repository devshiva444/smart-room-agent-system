"""
Swarm Manager - Agent Orchestration & Coordination
Coordinates the collaborative flow of the 4-agent swarm.
Now fully upgraded with Microsoft Azure OpenAI & Local LLM Semantic Intent Parsing,
complete with a robust bulletproof fallback engine for hackathon resilience.
"""

import re
import os
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

# Import OpenAI client safely
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from agents.environmental_agent import EnvironmentalAgent
from agents.productivity_agent import ProductivityAgent
from agents.execution_agent import ExecutionAgent
from agents.security_agent import SecurityAgent, ThreatLevel
from memory.state_store import StateStore


class SwarmManager:
    """
    Master Orchestrator for the Agent Swarm
    
    Coordinates 4 collaborative agents:
    - SecurityAgent: Input validation & threat detection
    - ProductivityAgent: Meeting/transcript analysis
    - ExecutionAgent: External service integration
    - EnvironmentalAgent: Room control via DQN
    
    Now uses dynamic LLM-driven parsing to analyze human speech, Hinglish, 
    and complex context patterns safely.
    """
    
    # Robust Heuristic Backup Synonyms to prevent crashes if LLM is offline/slow
    SEMANTIC_GROUPS = {
        "hot": ["hot", "boiling", "sweating", "garmi", "warm", "humid", "stuffy", "suffocating", "uncomfortable", "ac chalao", "garmi lag rahi hai"],
        "cold": ["cold", "freezing", "shivering", "thand", "cool", "chilly", "drafty", "icebox", "ac band karo", "thand lag rahi hai"],
        "presentation": ["presentation", "slides", "screen", "projector", "deck", "ppt", "demo", "pitch", "projector screen on"],
        "meeting": ["meeting", "standup", "sprint", "discussion", "collaboration", "sync", "conference", "charcha"],
        "focus": ["focus", "concentrate", "coding", "quiet", "work mode", "deep work", "shanti"],
        "relax": ["relax", "chill", "break", "coffee", "informal", "chai time"],
        "sleep": ["sleep", "nap", "darken", "quiet down"],
        "dark": ["dark", "dim", "low light", "lights out"],
        "bright": ["bright", "daylight", "maximum light", "lights on"]
    }
    
    # Action mappings associated with core intents
    ENV_CONTEXT_KEYWORDS = {
        "presentation": {"mode": "presentation", "light": "on", "screen": "on", "ac": "cool_22"},
        "meeting": {"mode": "meeting", "light": "on", "ac": "cool_22"},
        "focus": {"mode": "focus", "light": "on", "ac": "cool_22"},
        "relax": {"mode": "relax", "light": "dim", "ac": "cool_24"},
        "sleep": {"mode": "sleep", "light": "off", "ac": "cool_18"},
        "hot": {"temperature_up": True, "ac": "cool_18"},
        "cold": {"temperature_down": True, "ac": "off"},
        "dark": {"light": "on"},
        "bright": {"light": "off"},
    }
    
    def __init__(self, state_store: Optional[StateStore] = None):
        """
        Initialize SwarmManager with all agents and AI Gateway.
        """
        self.state_store = state_store or StateStore()
        
        # Initialize all 4 agents
        self.security_agent = SecurityAgent()
        self.productivity_agent = ProductivityAgent()
        self.execution_agent = ExecutionAgent()
        self.env_agent = EnvironmentalAgent()
        
        # Set up LLM connection (Azure OpenAI / Local Ollama / HF Token)
        self.api_key = os.getenv("HF_TOKEN") or os.getenv("AZURE_OPENAI_KEY") or os.getenv("OPENAI_API_KEY")
        self.api_base = os.getenv("API_BASE_URL", "http://localhost:11434/v1")  # Defaults to Local Ollama
        self.model_name = os.getenv("MODEL_NAME", "phi3")  # Microsoft Phi-3 is ideal for offline privacy
        
        self.client = None
        if OpenAI is not None and self.api_key:
            try:
                self.client = OpenAI(base_url=self.api_base, api_key=self.api_key)
                print(f"[SwarmManager] Connected to LLM Gateway at {self.api_base} using model {self.model_name}")
            except Exception as e:
                print(f"[SwarmManager] Failed to establish OpenAI connection: {e}. Falling back to Heuristics.")
                
        # Execution statistics
        self.executions_total = 0
        self.executions_blocked = 0
        self.executions_successful = 0
        self.executions_failed = 0
        
    def process_input(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
        execute_environmental: bool = True
    ) -> Dict[str, Any]:
        """
        Process user input through the full orchestration pipeline.
        """
        try:
            self.executions_total += 1
            
            result = {
                "timestamp": datetime.utcnow().isoformat(),
                "input_length": len(user_input),
                "stages": {},
                "summary": {},
                "errors": [],
                "status": "unknown",
            }
            
            # ===== STEP A: Security Validation =====
            result["stages"]["security"] = self._execute_security_stage(user_input)
            
            if result["stages"]["security"]["threat_level"] == "critical":
                self.executions_blocked += 1
                result["status"] = "blocked"
                result["summary"]["reason"] = "Security threat detected"
                self._log_execution_result(result, "BLOCKED")
                return result
            
            # ===== STEP B: Productivity Analysis =====
            result["stages"]["productivity"] = self._execute_productivity_stage(user_input)
            
            # ===== STEP C: Execution Publishing =====
            action_items = result["stages"]["productivity"].get("action_items", [])
            result["stages"]["execution"] = self._execute_execution_stage(action_items)
            
            # ===== STEP D: Environmental Adjustments =====
            if execute_environmental:
                # Dynamic AI-driven context extraction
                env_context = self._detect_environmental_context(user_input)
                result["stages"]["environmental"] = self._execute_environmental_stage(
                    env_context,
                    context or {}
                )
            
            # ===== STEP E: Summary & Logging =====
            result["status"] = "success"
            result["summary"] = self._generate_execution_summary(result)
            self.executions_successful += 1
            self._log_execution_result(result, "SUCCESS")
            
            return result
        except Exception as e:
            self.executions_failed += 1
            return {
                "status": "error",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
                "summary": {"reason": f"Processing error: {str(e)}"},
                "stages": {},
            }

    # ===== STAGE A: Security Validation =====
    
    def _execute_security_stage(self, user_input: str) -> Dict[str, Any]:
        """Stage A: Run input through Security Agent."""
        try:
            is_safe, reason, threat_level = self.security_agent.validate_user_input(
                user_input,
                context="swarm_input"
            )
            
            result = {
                "is_safe": is_safe,
                "threat_level": threat_level.value,
                "reason": reason,
            }
            
            self.state_store.log_agent_communication(
                source_agent="SwarmManager",
                target_agent="SecurityAgent",
                message=f"Validating input ({len(user_input)} chars)",
                payload={"is_safe": is_safe, "threat_level": threat_level.value},
                status="success" if is_safe else "warning"
            )
            
            self.state_store.log_security_event(
                event_type="input_validation",
                threat_level=threat_level.value,
                message=reason,
            )
            
            return result
        except Exception as e:
            return {
                "is_safe": False,
                "threat_level": "critical",
                "reason": f"Security validation error: {str(e)}",
            }

    # ===== STAGE B: Productivity Analysis =====
    
    def _execute_productivity_stage(self, user_input: str) -> Dict[str, Any]:
        """Stage B: Extract summary & action items using AI and Fallbacks."""
        try:
            # Let the Productivity Agent do standard processing
            analysis = self.productivity_agent.analyze_transcript(user_input)
            
            result = {
                "status": analysis.get("status", "unknown"),
                "summary": analysis.get("summary", ""),
                "topics": analysis.get("topics", []),
                "action_items": analysis.get("action_items", []),
                "metadata": analysis.get("metadata", {}),
            }
            
            self.state_store.log_agent_communication(
                source_agent="SecurityAgent",
                target_agent="ProductivityAgent",
                message=f"Analyzing transcript: {result['summary'][:100]}...",
                payload={
                    "action_items_count": len(result["action_items"]),
                    "topics": result["topics"]
                },
                status="success"
            )
            
            for action_item in result["action_items"]:
                self.state_store.log_action_item(action_item, source_agent="ProductivityAgent")
            
            return result
        except Exception as e:
            return {
                "status": "error",
                "summary": f"Analysis failed: {str(e)}",
                "topics": [],
                "action_items": [],
                "metadata": {"error": str(e)},
            }

    # ===== STAGE C: Execution Publishing =====
    
    def _execute_execution_stage(self, action_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Stage C: Publish action items through Execution Agent."""
        try:
            if not action_items:
                return {
                    "action_items_count": 0,
                    "executions": [],
                    "summary": "No action items to execute",
                }
            
            multi_results = self.execution_agent.multi_service_execute(action_items)
            
            result = {
                "action_items_count": len(action_items),
                "executions": multi_results,
                "summary": f"Published {len(action_items)} action items to GitHub, Slack, and Azure DevOps",
            }
            
            self.state_store.log_agent_communication(
                source_agent="ProductivityAgent",
                target_agent="ExecutionAgent",
                message=f"Publishing {len(action_items)} action items to external services",
                payload={
                    "github_count": len(multi_results.get("github", [])),
                    "slack_count": len(multi_results.get("slack", [])),
                    "azure_count": len(multi_results.get("azure_devops", [])),
                },
                status="success"
            )
            
            for i, item in enumerate(action_items):
                self.state_store.update_action_item_status(
                    action_id=i,
                    status="executing",
                    result={
                        "github": multi_results["github"][i] if i < len(multi_results["github"]) else None,
                        "slack": multi_results["slack"][i] if i < len(multi_results["slack"]) else None,
                        "azure": multi_results["azure_devops"][i] if i < len(multi_results["azure_devops"]) else None,
                    }
                )
            
            return result
        except Exception as e:
            return {
                "action_items_count": 0,
                "executions": [],
                "summary": f"Execution error: {str(e)}",
            }

    # ===== STAGE D: Environmental Adjustments =====
    
    def _execute_environmental_stage(
        self,
        env_context: Optional[Dict[str, Any]],
        current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Stage D: Invoke DQN via Environmental Agent with semantic target updates."""
        try:
            result = {
                "context_detected": env_context is not None,
                "action": None,
            }
            
            if not env_context:
                result["summary"] = "No environmental context detected"
                return result
            
            room_state = self.state_store.get_env_state()
            if current_state:
                room_state.update(current_state)
            
            # Intelligently simulate room boundaries to guide the DQN network
            if env_context.get("ac") == "cool_18":
                room_state["temperature"] = 28.0  # Force DQN to cool aggressively
            elif env_context.get("ac") == "off":
                room_state["temperature"] = 16.0  # Force DQN to shut down AC
                
            env_action = self.env_agent.execute_action(room_state)
            
            result["action"] = env_action
            result["summary"] = f"Environmental adjustments: {env_action['device']} -> {env_action['command']}"
            
            self.state_store.update_env_state({
                "last_action": env_action["action_id"],
                "last_action_device": env_action["device"],
                "ac": env_context.get("ac", room_state.get("ac")),
                "fan_speed": 3 if env_context.get("ac") == "cool_18" else (0 if env_context.get("ac") == "off" else 1)
            })
            
            self.state_store.log_agent_communication(
                source_agent="SwarmManager",
                target_agent="EnvironmentalAgent",
                message=f"Context resolved: {result['summary']}",
                payload={
                    "action_id": env_action["action_id"],
                    "device": env_action["device"],
                    "command": env_action["command"]
                },
                status="success"
            )
            
            return result
        except Exception as e:
            return {
                "context_detected": False,
                "action": None,
                "summary": f"Environmental adjustment error: {str(e)}",
            }

    # ===== Semantic Intent Parsing (AI-First + Heuristic Fallback) =====
    
    def _detect_environmental_context(self, user_input: str) -> Optional[Dict[str, Any]]:
        """
        Intelligently detects environmental context using LLM Semantic Analysis.
        If offline, seamlessly falls back to Heuristic Synonyms (Hinglish/English pattern match).
        """
        # Try AI-powered semantic parsing first
        if self.client:
            try:
                ai_result = self._query_llm_for_intent(user_input)
                if ai_result:
                    self.state_store.log_agent_communication(
                        source_agent="SwarmManager",
                        target_agent="AzureOpenAI_Sentinel",
                        message="Semantic Intent successfully classified via Enterprise AI Gateway",
                        payload={"resolved_intent": ai_result},
                        status="success"
                    )
                    return self.ENV_CONTEXT_KEYWORDS.get(ai_result)
            except Exception as e:
                # Log the API warning, but proceed silently to heuristics
                self.state_store.log_agent_communication(
                    source_agent="SwarmManager",
                    target_agent="AzureOpenAI_Sentinel",
                    message=f"API connection failed: {str(e)}. Falling back to offline heuristics.",
                    payload={},
                    status="warning"
                )

        # Robust Heuristic Fallback (Regex-based Hinglish matching)
        input_lower = user_input.lower()
        for intent, synonyms in self.SEMANTIC_GROUPS.items():
            for synonym in synonyms:
                pattern = r"\b" + re.escape(synonym) + r"\b"
                if re.search(pattern, input_lower):
                    return self.ENV_CONTEXT_KEYWORDS.get(intent)
                    
        return None

    def _query_llm_for_intent(self, user_input: str) -> Optional[str]:
        """
        Asks Azure OpenAI / Local Ollama to classify user intent to a specific key.
        Returns 'hot', 'cold', 'presentation', 'meeting', 'focus', etc.
        """
        prompt = f"""
You are the semantic router for an intelligent workspace.
Analyze the user utterance and classify its primary climate/workspace intent into exactly ONE of the following keys.
If no key matches perfectly, return "none".

KEYS:
- "hot": If the user complains about heat, sweating, suffocating, warm air, or wants aggressive cooling.
- "cold": If the user is shivering, freezing, cold, or wants the AC turned off/warmed.
- "presentation": If they mention starting a slide deck, looking at a screen, starting a demo, or projecting.
- "meeting": If they are starting a collaboration sync, standup, sprint meeting, or standard discussion.
- "focus": If they want to code, focus, need quiet, or deep work.
- "relax": If they are taking a break, drinking coffee, or chilling.
- "sleep": If they want quiet down/nap.

USER UTTERANCE: "{user_input}"

Response format: ONLY return the plain string key, e.g. "hot". Do not write markdown or sentences.
"""
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": "You are a precise classifier. Return only the classified key."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=10
        )
        
        reply = response.choices[0].message.content.strip().lower()
        # Clean potential markdown wrapping
        reply = re.sub(r'["\'`]', '', reply)
        
        if reply in self.ENV_CONTEXT_KEYWORDS:
            return reply
        return None

    # ===== Helper & Metrics Methods =====

    def _generate_execution_summary(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary statistics from execution result."""
        stages = result.get("stages", {})
        return {
            "total_stages": len(stages),
            "productivity": {
                "action_items": len(stages.get("productivity", {}).get("action_items", [])),
                "topics": stages.get("productivity", {}).get("topics", []),
            },
            "execution": {
                "status": stages.get("execution", {}).get("summary", "No execution"),
            },
            "environmental": {
                "action": stages.get("environmental", {}).get("action", {}).get("command") if stages.get("environmental") else "Not executed",
            },
        }
        
    def _log_execution_result(self, result: Dict[str, Any], status: str) -> None:
        """Log execution result to state store."""
        self.state_store.log_agent_communication(
            source_agent="SwarmManager",
            target_agent="StateStore",
            message=f"Execution {status}: {result['summary'].get('reason', '')}",
            payload={"execution_status": status},
            status="info"
        )
        
    def get_swarm_status(self) -> Dict[str, Any]:
        """Get current swarm status and metrics."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "manager_stats": {
                "total_executions": self.executions_total,
                "successful": self.executions_successful,
                "blocked": self.executions_blocked,
                "failed": self.executions_failed,
            },
            "agent_stats": {
                "security": self.security_agent.get_stats(),
                "productivity": self.productivity_agent.get_stats(),
                "execution": self.execution_agent.get_stats(),
                "environmental": self.env_agent.get_stats(),
            },
            "state_store": self.state_store.get_swarm_summary(),
        }
        
    def get_recent_logs(self, limit: int = 50) -> Dict[str, Any]:
        """Get recent agent communication logs."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "agent_logs": self.state_store.get_agent_logs(limit=limit),
            "security_events": self.state_store.get_security_events(limit=limit),
        }
        
    def export_execution_history(self) -> Dict[str, Any]:
        """Export full execution history for analysis."""
        return self.state_store.export_state_snapshot()





# """
# Swarm Manager - Agent Orchestration & Coordination
# Coordinates the collaborative flow of the 4-agent swarm.

# Orchestration Flow:
#   Step A: Security Agent validates input (block if CRITICAL)
#   Step B: Productivity Agent extracts action items
#   Step C: Execution Agent publishes to external services
#   Step D: Environmental Agent infers room adjustments (context-aware)
#   Step E: Log all activities to StateStore
# """

# import re
# from typing import Dict, Any, List, Optional, Tuple
# from datetime import datetime

# from agents.environmental_agent import EnvironmentalAgent
# from agents.productivity_agent import ProductivityAgent
# from agents.execution_agent import ExecutionAgent
# from agents.security_agent import SecurityAgent, ThreatLevel
# from memory.state_store import StateStore


# class SwarmManager:
#     """
#     Master Orchestrator for the Agent Swarm
    
#     Coordinates 4 collaborative agents:
#     - SecurityAgent: Input validation & threat detection
#     - ProductivityAgent: Meeting/transcript analysis
#     - ExecutionAgent: External service integration
#     - EnvironmentalAgent: Room control via DQN
    
#     All activities logged to StateStore for monitoring and dashboard.
#     """
    
#     # Environmental context keywords for room adjustments
#     ENV_CONTEXT_KEYWORDS = {
#         "presentation": {"mode": "presentation", "light": "on", "screen": "on", "ac": "cool_22"},
#         "meeting": {"mode": "meeting", "light": "on", "ac": "cool_22"},
#         "focus": {"mode": "focus", "light": "on", "ac": "cool_22"},
#         "relax": {"mode": "relax", "light": "dim", "ac": "cool_24"},
#         "sleep": {"mode": "sleep", "light": "off", "ac": "cool_18"},
#         "hot": {"temperature_up": True, "ac": "cool_18"},
#         "cold": {"temperature_down": True, "ac": "off"},
#         "dark": {"light": "on"},
#         "bright": {"light": "off"},
#     }
    
#     def __init__(self, state_store: Optional[StateStore] = None):
#         """
#         Initialize SwarmManager with all agents.
        
#         Args:
#             state_store: Optional StateStore instance. If None, creates a new one.
#         """
#         # Initialize shared state store
#         self.state_store = state_store or StateStore()
        
#         # Initialize all 4 agents
#         self.security_agent = SecurityAgent()
#         self.productivity_agent = ProductivityAgent()
#         self.execution_agent = ExecutionAgent()
#         self.env_agent = EnvironmentalAgent()
        
#         # Execution statistics
#         self.executions_total = 0
#         self.executions_blocked = 0
#         self.executions_successful = 0
#         self.executions_failed = 0
    
#     def process_input(
#         self,
#         user_input: str,
#         context: Optional[Dict[str, Any]] = None,
#         execute_environmental: bool = True
#     ) -> Dict[str, Any]:
#         """
#         Process user input through the full orchestration pipeline.
        
#         Orchestration Steps:
#           A: Security validation
#           B: Productivity analysis (if safe)
#           C: Execution publishing (if action items generated)
#           D: Environmental adjustments (if context detected)
#           E: Log everything
        
#         Args:
#             user_input: Raw text input (transcript, command, etc.)
#             context: Optional context dict with environmental state
#             execute_environmental: Whether to invoke environmental adjustments
            
#         Returns:
#             Result dictionary with execution summary and details.
#         """
#         try:
#             self.executions_total += 1
            
#             result = {
#                 "timestamp": datetime.utcnow().isoformat(),
#                 "input_length": len(user_input),
#                 "stages": {},
#                 "summary": {},
#                 "errors": [],
#                 "status": "unknown",
#             }
            
#             # ===== STEP A: Security Validation =====
#             result["stages"]["security"] = self._execute_security_stage(user_input)
            
#             if result["stages"]["security"]["threat_level"] == "critical":
#                 self.executions_blocked += 1
#                 result["status"] = "blocked"
#                 result["summary"]["reason"] = "Security threat detected"
#                 self._log_execution_result(result, "BLOCKED")
#                 return result
            
#             # ===== STEP B: Productivity Analysis =====
#             result["stages"]["productivity"] = self._execute_productivity_stage(user_input)
            
#             # ===== STEP C: Execution Publishing =====
#             action_items = result["stages"]["productivity"].get("action_items", [])
#             result["stages"]["execution"] = self._execute_execution_stage(action_items)
            
#             # ===== STEP D: Environmental Adjustments =====
#             if execute_environmental:
#                 env_context = self._detect_environmental_context(user_input)
#                 result["stages"]["environmental"] = self._execute_environmental_stage(
#                     env_context,
#                     context or {}
#                 )
            
#             # ===== STEP E: Summary & Logging =====
#             result["status"] = "success"
#             result["summary"] = self._generate_execution_summary(result)
#             self.executions_successful += 1
#             self._log_execution_result(result, "SUCCESS")
            
#             return result
#         except Exception as e:
#             self.executions_failed += 1
#             return {
#                 "status": "error",
#                 "timestamp": datetime.utcnow().isoformat(),
#                 "error": str(e),
#                 "summary": {"reason": f"Processing error: {str(e)}"},
#                 "stages": {},
#             }
    
#     # ===== STAGE A: Security Validation =====
    
#     def _execute_security_stage(self, user_input: str) -> Dict[str, Any]:
#         """
#         Stage A: Run input through Security Agent.
        
#         Returns:
#             Security validation result.
#         """
#         try:
#             is_safe, reason, threat_level = self.security_agent.validate_user_input(
#                 user_input,
#                 context="swarm_input"
#             )
            
#             result = {
#                 "is_safe": is_safe,
#                 "threat_level": threat_level.value,
#                 "reason": reason,
#             }
            
#             # Log communication
#             self.state_store.log_agent_communication(
#                 source_agent="SwarmManager",
#                 target_agent="SecurityAgent",
#                 message=f"Validating input ({len(user_input)} chars)",
#                 payload={"is_safe": is_safe, "threat_level": threat_level.value},
#                 status="success" if is_safe else "warning"
#             )
            
#             # Log security event
#             self.state_store.log_security_event(
#                 event_type="input_validation",
#                 threat_level=threat_level.value,
#                 message=reason,
#             )
            
#             return result
#         except Exception as e:
#             return {
#                 "is_safe": False,
#                 "threat_level": "critical",
#                 "reason": f"Security validation error: {str(e)}",
#             }
    
#     # ===== STAGE B: Productivity Analysis =====
    
#     def _execute_productivity_stage(self, user_input: str) -> Dict[str, Any]:
#         """
#         Stage B: Analyze input through Productivity Agent.
        
#         Returns:
#             Productivity analysis result.
#         """
#         try:
#             analysis = self.productivity_agent.analyze_transcript(user_input)
            
#             result = {
#                 "status": analysis.get("status", "unknown"),
#                 "summary": analysis.get("summary", ""),
#                 "topics": analysis.get("topics", []),
#                 "action_items": analysis.get("action_items", []),
#                 "metadata": analysis.get("metadata", {}),
#             }
            
#             # Log communication
#             self.state_store.log_agent_communication(
#                 source_agent="SecurityAgent",
#                 target_agent="ProductivityAgent",
#                 message=f"Analyzing transcript: {result['summary'][:100]}...",
#                 payload={
#                     "action_items_count": len(result["action_items"]),
#                     "topics": result["topics"]
#                 },
#                 status="success"
#             )
            
#             # Log each action item
#             for action_item in result["action_items"]:
#                 self.state_store.log_action_item(action_item, source_agent="ProductivityAgent")
            
#             return result
#         except Exception as e:
#             return {
#                 "status": "error",
#                 "summary": f"Analysis failed: {str(e)}",
#                 "topics": [],
#                 "action_items": [],
#                 "metadata": {"error": str(e)},
#             }
    
#     # ===== STAGE C: Execution Publishing =====
    
#     def _execute_execution_stage(self, action_items: List[Dict[str, Any]]) -> Dict[str, Any]:
#         """
#         Stage C: Publish action items through Execution Agent.
        
#         Args:
#             action_items: List of action items from Productivity Agent.
            
#         Returns:
#             Execution results.
#         """
#         try:
#             if not action_items:
#                 return {
#                     "action_items_count": 0,
#                     "executions": [],
#                     "summary": "No action items to execute",
#                 }
            
#             # Execute to all services
#             multi_results = self.execution_agent.multi_service_execute(action_items)
            
#             result = {
#                 "action_items_count": len(action_items),
#                 "executions": multi_results,
#                 "summary": f"Published {len(action_items)} action items to GitHub, Slack, and Azure DevOps",
#             }
            
#             # Log communication
#             self.state_store.log_agent_communication(
#                 source_agent="ProductivityAgent",
#                 target_agent="ExecutionAgent",
#                 message=f"Publishing {len(action_items)} action items to external services",
#                 payload={
#                     "github_count": len(multi_results.get("github", [])),
#                     "slack_count": len(multi_results.get("slack", [])),
#                     "azure_count": len(multi_results.get("azure_devops", [])),
#                 },
#                 status="success"
#             )
            
#             # Update action item statuses
#             for i, item in enumerate(action_items):
#                 self.state_store.update_action_item_status(
#                     action_id=i,
#                     status="executing",
#                     result={
#                         "github": multi_results["github"][i] if i < len(multi_results["github"]) else None,
#                         "slack": multi_results["slack"][i] if i < len(multi_results["slack"]) else None,
#                         "azure": multi_results["azure_devops"][i] if i < len(multi_results["azure_devops"]) else None,
#                     }
#                 )
            
#             return result
#         except Exception as e:
#             return {
#                 "action_items_count": 0,
#                 "executions": [],
#                 "summary": f"Execution error: {str(e)}",
#             }
    
#     # ===== STAGE D: Environmental Adjustments =====
    
#     def _execute_environmental_stage(
#         self,
#         env_context: Optional[Dict[str, Any]],
#         current_state: Dict[str, Any]
#     ) -> Dict[str, Any]:
#         """
#         Stage D: Invoke Environmental Agent for room adjustments.
        
#         Args:
#             env_context: Detected environmental context keywords.
#             current_state: Current room state from StateStore.
            
#         Returns:
#             Environmental adjustment results.
#         """
#         try:
#             result = {
#                 "context_detected": env_context is not None,
#                 "action": None,
#             }
            
#             if not env_context:
#                 result["summary"] = "No environmental context detected"
#                 return result
            
#             # Get current room state
#             room_state = self.state_store.get_env_state()
#             if current_state:
#                 room_state.update(current_state)
            
#             # Invoke Environmental Agent
#             env_action = self.env_agent.execute_action(room_state)
            
#             result["action"] = env_action
#             result["summary"] = f"Environmental adjustments: {env_action['device']} -> {env_action['command']}"
            
#             # Update state store with new environmental state
#             self.state_store.update_env_state({
#                 "last_action": env_action["action_id"],
#                 "last_action_device": env_action["device"],
#             })
            
#             # Log communication
#             self.state_store.log_agent_communication(
#                 source_agent="SwarmManager",
#                 target_agent="EnvironmentalAgent",
#                 message=f"Context detected: {list(env_context.keys())[0] if env_context else 'none'}",
#                 payload={
#                     "action_id": env_action["action_id"],
#                     "device": env_action["device"],
#                     "command": env_action["command"]
#                 },
#                 status="success"
#             )
            
#             return result
#         except Exception as e:
#             return {
#                 "context_detected": False,
#                 "action": None,
#                 "summary": f"Environmental adjustment error: {str(e)}",
#             }
    
#     # ===== Helper Methods =====
    
#     def _detect_environmental_context(self, user_input: str) -> Optional[Dict[str, Any]]:
#         """
#         Detect environmental context keywords in input.
        
#         Args:
#             user_input: Raw input text.
            
#         Returns:
#             Context dict if keywords matched, None otherwise.
#         """
#         input_lower = user_input.lower()
        
#         for keyword, context in self.ENV_CONTEXT_KEYWORDS.items():
#             if keyword in input_lower:
#                 return context
        
#         return None
    
#     def _generate_execution_summary(self, result: Dict[str, Any]) -> Dict[str, Any]:
#         """Generate summary statistics from execution result."""
#         stages = result.get("stages", {})
        
#         summary = {
#             "total_stages": len(stages),
#             "productivity": {
#                 "action_items": len(stages.get("productivity", {}).get("action_items", [])),
#                 "topics": stages.get("productivity", {}).get("topics", []),
#             },
#             "execution": {
#                 "status": stages.get("execution", {}).get("summary", "No execution"),
#             },
#             "environmental": {
#                 "action": stages.get("environmental", {}).get("action", {}).get("command") if stages.get("environmental") else "Not executed",
#             },
#         }
        
#         return summary
    
#     def _log_execution_result(self, result: Dict[str, Any], status: str) -> None:
#         """Log execution result to state store."""
#         self.state_store.log_agent_communication(
#             source_agent="SwarmManager",
#             target_agent="StateStore",
#             message=f"Execution {status}: {result['summary'].get('reason', '')}",
#             payload={"execution_status": status},
#             status="info"
#         )
    
#     # ===== Monitoring & Diagnostics =====
    
#     def get_swarm_status(self) -> Dict[str, Any]:
#         """Get current swarm status and metrics."""
#         return {
#             "timestamp": datetime.utcnow().isoformat(),
#             "manager_stats": {
#                 "total_executions": self.executions_total,
#                 "successful": self.executions_successful,
#                 "blocked": self.executions_blocked,
#                 "failed": self.executions_failed,
#             },
#             "agent_stats": {
#                 "security": self.security_agent.get_stats(),
#                 "productivity": self.productivity_agent.get_stats(),
#                 "execution": self.execution_agent.get_stats(),
#                 "environmental": self.env_agent.get_stats(),
#             },
#             "state_store": self.state_store.get_swarm_summary(),
#         }
    
#     def get_recent_logs(self, limit: int = 50) -> Dict[str, Any]:
#         """Get recent agent communication logs."""
#         return {
#             "timestamp": datetime.utcnow().isoformat(),
#             "agent_logs": self.state_store.get_agent_logs(limit=limit),
#             "security_events": self.state_store.get_security_events(limit=limit),
#         }
    
#     def export_execution_history(self) -> Dict[str, Any]:
#         """Export full execution history for analysis."""
#         return self.state_store.export_state_snapshot()