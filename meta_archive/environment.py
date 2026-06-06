"""
Smart Room Environment - Finale Version (Personalized Executive Assistant #3.2)
Integration: Modular logic from reward.py, rules.py, supervisor.py, and memory.py
"""

from openenv.core.env_server import Environment, Action, Observation, State
from pydantic import Field
import random
import numpy as np
import os

# Modular logic import kar rahe hain
from core.reward import get_reward_calculator
from core.rules import get_safety_rules
from core.supervisor import get_action_supervisor
from core.memory import MemoryManager

class SmartRoomAction(Action):
    action: int = Field(..., description="0-8: control action (light, fan, AC)")

class SmartRoomObservation(Observation):
    temperature: float
    light_on: bool
    fan_speed: int
    ac_on: bool
    occupancy: bool
    energy_used: float
    reward: float
    done: bool
    time_of_day: str
    sleep_mode: bool
    override_active: bool
    action_taken: int

class SmartRoomState(State):
    step_count: int

class SmartRoomEnvironment(Environment):
    def __init__(self, seed=42):
        random.seed(seed)
        np.random.seed(seed)
        
        # Subsystems initialize karein (Ye files ab handle karengi logic)
        self.reward_calc = get_reward_calculator()
        self.safety_rules = get_safety_rules()
        self.supervisor = get_action_supervisor()
        self.memory = MemoryManager() # User overrides handle karne ke liye
        
        # Room Base State
        self.temperature = 25.0
        self.outside_temp = 30.0
        self.light_on = False
        self.fan_speed = 0
        self.ac_on = False
        self.occupancy = False
        self.energy_used = 0.0
        
        # Logic Helpers
        self.time_of_day = "day"
        self.step_count = 0
        self.total_reward = 0.0
        self.last_action = -1
        
        # Sleep Pattern Logic
        self.sleep_mode = False
        self.sleep_certainty_counter = 0 
        
        self.reset()

    def reset(self) -> SmartRoomObservation:
        """Environment ko reset karke initial observation dena"""
        self.temperature = random.uniform(22.0, 32.0)
        self.outside_temp = random.uniform(28.0, 35.0)
        self.light_on = False
        self.fan_speed = 0
        self.ac_on = False
        self.occupancy = random.choice([True, False])
        self.energy_used = 0.0
        self.step_count = 0
        self.total_reward = 0.0
        self.last_action = -1
        self.sleep_mode = False
        self.sleep_certainty_counter = 0
        
        # Memory aur Supervisor stats reset
        self.memory.clear_override()
        self.supervisor.reset_stats()
        
        return self._get_obs(0.0, False, 0)

    @property
    def state(self) -> SmartRoomState:
        return SmartRoomState(step_count=self.step_count)

    def _update_time_cycle(self):
        """Day/Night cycle update (10 steps day, 10 steps night)"""
        if self.step_count % 20 < 10:
            self.time_of_day = "day"
        else:
            self.time_of_day = "night"

    def _detect_sleep_mode(self):
        """Pattern detection: 5 steps of night + occupied + dark = Sleep Mode"""
        if self.time_of_day == "night" and self.occupancy and not self.light_on:
            self.sleep_certainty_counter += 1
        else:
            self.sleep_certainty_counter = 0 
            self.sleep_mode = False

        if self.sleep_certainty_counter >= 5:
            self.sleep_mode = True
        
        self.memory.set_sleep_mode(self.sleep_mode)

    def apply_manual_override(self, action: int):
        """User manual click dashboard se"""
        self.memory.set_override(action, timer=10)
        self._process_action(action)

    def _process_action(self, action: int):
        """Hardware states ko update karna"""
        if action == 1: self.light_on = True
        elif action == 2: self.light_on = False
        elif action == 3: self.fan_speed = 1
        elif action == 4: self.fan_speed = 2
        elif action == 5: self.fan_speed = 3
        elif action == 6: self.fan_speed = 0
        elif action == 7: self.ac_on = True
        elif action == 8: self.ac_on = False

    def _physics_simulation(self) -> float:
        """Realistic temperature and energy math"""
        energy_step = 0.0
        
        # Cooling effect calculation
        cooling_map = {0: 0, 1: 0.3, 2: 0.6, 3: 0.9}
        energy_map = {0: 0, 1: 0.2, 2: 0.4, 3: 0.6}
        
        self.temperature -= cooling_map[self.fan_speed]
        energy_step += energy_map[self.fan_speed]

        if self.ac_on:
            self.temperature -= 1.5
            energy_step += 1.0
        
        # Natural Drift
        if not self.ac_on and self.fan_speed == 0:
            self.temperature += (self.outside_temp - self.temperature) * 0.05
        
        if self.light_on: energy_step += 0.1
        
        self.temperature += random.uniform(-0.1, 0.1)
        self.energy_used += energy_step
        return energy_step

    def _get_obs(self, reward: float, done: bool, action: int) -> SmartRoomObservation:
        return SmartRoomObservation(
            temperature=round(self.temperature, 2),
            light_on=self.light_on,
            fan_speed=self.fan_speed,
            ac_on=self.ac_on,
            occupancy=self.occupancy,
            energy_used=round(self.energy_used, 2),
            reward=float(reward),
            done=bool(done),
            time_of_day=self.time_of_day,
            sleep_mode=self.sleep_mode,
            override_active=self.memory.get("override_active", False),
            action_taken=action
        )

    def step(self, action: SmartRoomAction) -> SmartRoomObservation:
        """
        Execute one step using modular files (rules, supervisor, reward)
        """
        self.step_count += 1
        self.memory.decrement_override_timer() # Timer decrease karna
        
        # 1. Update Patterns
        self._update_time_cycle()
        self._detect_sleep_mode()

        # 2. Layer 2 Check (Supervisor + Rules)
        # Ab ye code logic rules.py aur supervisor.py se aayega
        action_val = action.action
        
        # Agar user override active hai, toh AI action ignore karo
        if self.memory.get("override_active", False):
            action_val = 0 # Agent action rejected during override
        
        state_dict = {
            'temperature': self.temperature,
            'occupancy': self.occupancy,
            'light_on': self.light_on,
            'fan_speed': self.fan_speed,
            'ac_on': self.ac_on,
            'sleep_mode': self.sleep_mode
        }
        
        # Supervisor check (Action validate karke safety apply karna)
        final_action, was_overridden, violation_count = self.supervisor.apply_safety_override(
            action_val, self.temperature, self.occupancy, 
            self.light_on, self.fan_speed, self.ac_on, state_dict
        )
        
        # 3. Layer 3 (Execute + Physics)
        self._process_action(final_action)
        energy_step = self._physics_simulation()
        
        # Human movement
        if random.random() < 0.10:
            self.occupancy = not self.occupancy
            
        # 4. Reward Calculation (reward.py handles this now)
        action_smooth = (final_action == self.last_action)
        reward = self.reward_calc.calculate_total_reward(
            temperature=self.temperature,
            energy_used=energy_step,
            safety_violations=violation_count,
            action_smooth=action_smooth,
            action_spam_count=1 if action_smooth and final_action != 0 else 0,
            occupancy=self.occupancy
        )
        
        self.total_reward += reward
        self.last_action = final_action
        
        done = self.step_count >= 100
        return self._get_obs(reward, done, final_action)