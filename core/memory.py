"""
Memory System - Stores user preferences and override history
Used for smart decision-making and learning user behavior
Meta OpenEnv Hackathon 2026 - Finale Version
"""

import json
import os
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

# MEMORY_FILE ko .env se uthayega ya default use karega
MEMORY_FILE = os.getenv("MEMORY_FILE", "user_memory.json")

class MemoryManager:
    """Manages user preferences and override history for Personal Assistant (#3.2)"""
    
    def __init__(self, memory_file: str = MEMORY_FILE):
        self.memory_file = memory_file
        self.data = self._load()
    
    def _load(self) -> Dict[str, Any]:
        """JSON file se memory load karta hai"""
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r") as f:
                    return json.load(f)
            except Exception:
                return self._default_memory()
        return self._default_memory()
    
    def _default_memory(self) -> Dict[str, Any]:
        """Initial memory structure for a new session"""
        return {
            "preferred_temp": 24.0,
            "preferred_fan_speed": 0,
            "sleep_mode_active": False,
            "override_active": False,
            "override_timer": 0,
            "last_override_action": 0,
            "override_history": [],
            "energy_target": 100.0,
            "created_at": str(datetime.now())
        }
    
    def _save(self):
        """Memory data ko JSON file mein save karta hai"""
        try:
            with open(self.memory_file, "w") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"[MemoryManager] Error saving memory: {e}")
    
    def set_override(self, action: int, timer: int = 10):
        """
        Jab user manually control kare, tab AI ko pause karne ke liye timer set karta hai.
        Default: 10 steps (as per environment logic).
        """
        self.data["override_active"] = True
        self.data["override_timer"] = timer
        self.data["last_override_action"] = action
        self.data["override_history"].append({
            "action": action,
            "timestamp": str(datetime.now()),
            "timer": timer
        })
        self._save() # Data persistence ke liye zaroori hai
    
    def clear_override(self):
        """Override ko khatam karta hai taaki AI wapas control le sake"""
        self.data["override_active"] = False
        self.data["override_timer"] = 0
        self._save()
    
    def set_preferred_temp(self, temp: float):
        """User ki favorite temperature store karta hai"""
        self.data["preferred_temp"] = round(temp, 1)
        self._save()
    
    def set_sleep_mode(self, active: bool):
        """Sleep mode status update karta hai (Pattern detection ke baad)"""
        self.data["sleep_mode_active"] = active
        # No need to save every step to file, keep in RAM for performance
    
    def get(self, key: str, default: Any = None) -> Any:
        """Memory se koi bhi specific value nikalne ke liye"""
        return self.data.get(key, default)
    
    def decrement_override_timer(self):
        """
        Har step par timer ko 1 kam karta hai. 
        Jab timer 0 hota hai, tab AI wapas control leta hai.
        """
        if self.data.get("override_timer", 0) > 0:
            self.data["override_timer"] -= 1
            if self.data["override_timer"] <= 0:
                self.clear_override()
            else:
                self._save()

# --- Singleton Pattern for Global Access ---
_memory = None

def get_memory() -> MemoryManager:
    """Poore project mein ek hi memory instance use karne ke liye"""
    global _memory
    if _memory is None:
        _memory = MemoryManager()
    return _memory