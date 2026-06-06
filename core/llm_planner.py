"""
LLM Planner - Hackathon Compliant Multi-Agent Supervisor
Acts as the Manager, reviewing the RL Agent's proposed actions.
Updated: Aware of User Manual Overrides and Sleep Patterns.
"""

import json
import os

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

class LLMPlanner:
    ACTION_DESCRIPTION = {
        0: "Do nothing", 1: "Light ON", 2: "Light OFF",
        3: "Fan speed 1", 4: "Fan speed 2", 5: "Fan speed 3", 6: "Fan OFF",
        7: "AC ON", 8: "AC OFF"
    }
    
    def __init__(self, model_name=None):
        # Mandatory Hackathon Variables from .env
        self.api_key = os.getenv("HF_TOKEN")
        self.api_base = os.getenv("API_BASE_URL")
        self.model_name = model_name or os.getenv("MODEL_NAME", "gpt-3.5-turbo")
        self.temperature = 0.1 # Very low temperature for consistent JSON output
        self.client = None
        
        if OpenAI is not None and self.api_key:
            try:
                if self.api_base:
                    self.client = OpenAI(base_url=self.api_base, api_key=self.api_key)
                else:
                    self.client = OpenAI(api_key=self.api_key)
            except Exception as e:
                print(f"[LLMPlanner] Failed to init OpenAI client: {e}")
                self.client = None
    
    def _state_to_prompt(self, state_dict):
        proposed_action_code = state_dict.get('rl_proposed_action', 0)
        proposed_action_desc = self.ACTION_DESCRIPTION.get(proposed_action_code, "Do nothing")
        override_active = state_dict.get('override_active', False)
        sleep_mode = state_dict.get('sleep_mode', False)
        
        # Override Awareness Logic for the Prompt
        override_msg = ""
        if override_active:
            override_msg = "\n⚠️ NOTE: USER MANUAL OVERRIDE IS ACTIVE. The user has manually set the room. Do not change their settings unless it is an EXTREME safety hazard (e.g., Temp > 35C)."

        return f"""You are the Master AI Supervisor for a Smart Room.
Review the RL Agent's proposal. {override_msg}

CURRENT ROOM STATE:
- Temperature: {state_dict.get('temperature', 25):.1f}C (Target: ~24C)
- Occupancy: {'YES' if state_dict.get('occupancy', False) else 'NO'}
- Time: {state_dict.get('time_of_day', 'day')}
- Sleep Mode: {'ACTIVE (Quiet/Dark Required)' if sleep_mode else 'OFF'}
- Light Status: {'ON' if state_dict.get('light_on', False) else 'OFF'}
- AC Status: {'ON' if state_dict.get('ac_on', False) else 'OFF'}

RL AGENT'S PROPOSAL: {proposed_action_code} ({proposed_action_desc})

INSTRUCTION: If Override is Active, prefer action 0 (Nothing) to respect user choice.
Respond with ONLY valid JSON: {{"action": <int>}}
"""
    
    def _smart_fallback_policy(self, state_dict):
        # Fallback if API fails or override is active
        if state_dict.get('override_active', False):
            return 0 # Do nothing, let user remain in control
        return state_dict.get('rl_proposed_action', 0)
    
    def plan_action(self, state_dict, use_fallback=False):
        if use_fallback or self.client is None:
            return self._smart_fallback_policy(state_dict), 'fallback', None
        
        try:
            prompt = self._state_to_prompt(state_dict)
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a smart home supervisor. Always output valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=50
            )
            response_text = response.choices[0].message.content.strip()
            
            # JSON Parsing with Regex Fallback
            try:
                data = json.loads(response_text)
                action = int(data.get("action", 0))
                if 0 <= action <= 8:
                    return action, 'llm_supervisor', None
            except:
                import re
                numbers = re.findall(r'\d+', response_text)
                if numbers and 0 <= int(numbers[0]) <= 8:
                    return int(numbers[0]), 'llm_parsed', None
            
            return self._smart_fallback_policy(state_dict), 'fallback_parse_error', "Parsing failed"
                
        except Exception as e:
            return self._smart_fallback_policy(state_dict), 'fallback_exception', str(e)

_llm_planner = None
def get_llm_planner(**kwargs):
    global _llm_planner
    if _llm_planner is None:
        _llm_planner = LLMPlanner(**kwargs)
    return _llm_planner