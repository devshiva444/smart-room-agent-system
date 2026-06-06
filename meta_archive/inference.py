"""
Hackathon-Compliant Clean Inference Script
Multi-Agent Logic:
1. core.multi_agent (RL Worker) - Action propose karega
2. core.llm_planner (Spythonupervisor) - Action finalise karega
"""

import os
import json
import time
from typing import Dict, Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

# Components import kar rahe hain
from environment import SmartRoomEnvironment, SmartRoomAction
from core.llm_planner import get_llm_planner
from core.multi_agent import RLWorker

class InferenceEngine:
    def __init__(self):
        self.env = SmartRoomEnvironment()
        
        # Hackathon variables for LLM (Agent 2 - Supervisor)
        model_name = os.getenv("MODEL_NAME", "gpt-3.5-turbo")
        self.llm_supervisor = get_llm_planner(model_name=model_name)
        
        # RL Worker (Agent 1)
        self.rl_worker = RLWorker()

    def run_inference(self):
        """
        Inference run karta he strict format ke sath, 
        plus Human-Readable table for debugging!
        """
        # [START] tag - Bot ke liye zaroori
        print("[START] Starting Multi-Agent Inference Run")
        
        # --- HUMAN READABLE HEADER ---
        print("\n" + "="*70)
        print(f"🤖 3-LAYER MULTI-AGENT SMART ROOM SYSTEM")
        print("="*70)
        print(f"{'STEP':<5} | {'ACTION':<15} | {'TEMP':<7} | {'OCCUPANCY':<10} | {'AC':<4} | {'REWARD':<8}")
        print("-" * 70)
        # -----------------------------

        obs = self.env.reset()
        obs_dict = obs.model_dump() if hasattr(obs, 'model_dump') else obs.dict() if hasattr(obs, 'dict') else obs.__dict__
        
        total_reward = 0.0
        max_steps = 20 
        
        for step in range(max_steps):
            # 1. RL Worker action propose karega
            rl_action = self.rl_worker.propose_action(obs_dict)
            obs_dict['rl_proposed_action'] = rl_action
            
            # 2. LLM Supervisor usko check karega
            final_action, source, _ = self.llm_supervisor.plan_action(obs_dict)
            
            # 3. Environment update
            next_obs = self.env.step(SmartRoomAction(action=final_action))
            next_obs_dict = next_obs.model_dump() if hasattr(next_obs, 'model_dump') else next_obs.dict() if hasattr(next_obs, 'dict') else next_obs.__dict__
            
            reward = next_obs_dict.get('reward', 0.0)
            total_reward += reward
            
            # --- 🧑‍💻 HUMAN READABLE FORMAT (Tumhare Padhne Ke Liye) ---
            action_desc = self.llm_supervisor.ACTION_DESCRIPTION.get(final_action, "Unknown")
            temp = f"{next_obs_dict.get('temperature', 0):.1f}°C"
            occ = "YES 👤" if next_obs_dict.get('occupancy', False) else "NO"
            ac_status = "ON ❄️" if next_obs_dict.get('ac_on', False) else "OFF"
            
            print(f"{step:<5} | {action_desc:<15} | {temp:<7} | {occ:<10} | {ac_status:<4} | {reward:>6.4f}")
            
            # --- 🤖 BOT REQUIRED FORMAT (Hackathon Bot Ke Padhne Ke Liye) ---
            print(f"[STEP] Step: {step} | Action: {final_action} | Observation: {json.dumps(next_obs_dict)} | Reward: {reward:.4f}")
            
            obs_dict = next_obs_dict
            if next_obs_dict.get('done', False):
                break
                
            time.sleep(0.1)
            
        print("="*70 + "\n")
        
        # [END] tag
        print(f"[END] Total Reward: {total_reward:.4f}")

if __name__ == "__main__":
    engine = InferenceEngine()
    engine.run_inference()


# """
# Hackathon-Compliant Clean Inference Script
# Multi-Agent Logic:
# 1. core.multi_agent (RL Worker) - Action propose karega
# 2. core.llm_planner (Supervisor) - Action finalise karega
# """

# import os
# import json
# import time
# from typing import Dict, Any

# try:
#     from dotenv import load_dotenv
#     load_dotenv()
# except:
#     pass

# # Components import kar rahe hain
# from environment import SmartRoomEnvironment, SmartRoomAction
# from core.llm_planner import get_llm_planner
# from core.multi_agent import RLWorker

# class InferenceEngine:
#     def __init__(self):
#         self.env = SmartRoomEnvironment()
        
#         # Hackathon variables for LLM (Agent 2 - Supervisor)
#         model_name = os.getenv("MODEL_NAME", "gpt-3.5-turbo")
#         self.llm_supervisor = get_llm_planner(model_name=model_name)
        
#         # RL Worker (Agent 1)
#         self.rl_worker = RLWorker()

#     def run_inference(self):
#         """
#         Inference run karta he strict format ke sath jisse grader bot reject na kare.
#         """
#         # [START] tag - Bot ke liye zaroori
#         print("[START] Starting Multi-Agent Inference Run")
        
#         obs = self.env.reset()
#         obs_dict = obs.model_dump() if hasattr(obs, 'model_dump') else obs.dict() if hasattr(obs, 'dict') else obs.__dict__
        
#         total_reward = 0.0
         
#         # API limit aur timeout bachane ke liye max steps 20 rakhe hain
#         max_steps = 20 
        
#         for step in range(max_steps):
#             # 1. RL Worker action propose karega
#             rl_action = self.rl_worker.propose_action(obs_dict)
#             obs_dict['rl_proposed_action'] = rl_action
            
#             # 2. LLM Supervisor usko check karega
#             final_action, source, _ = self.llm_supervisor.plan_action(obs_dict)
            
#             # 3. Environment update
#             next_obs = self.env.step(SmartRoomAction(action=final_action))
#             next_obs_dict = next_obs.model_dump() if hasattr(next_obs, 'model_dump') else next_obs.dict() if hasattr(next_obs, 'dict') else next_obs.__dict__
            
#             reward = next_obs_dict.get('reward', 0.0)
#             total_reward += reward
            
#             # [STEP] tag strictly formatted
#             print(f"[STEP] Step: {step} | Action: {final_action} | Observation: {json.dumps(next_obs_dict)} | Reward: {reward:.4f}")
            
#             obs_dict = next_obs_dict
#             if next_obs_dict.get('done', False):
#                 break
                
#             time.sleep(0.1) # Rate limits se bachne ke liye chhota delay
            
#         # [END] tag
#         print(f"[END] Total Reward: {total_reward:.4f}")

# if __name__ == "__main__":
#     engine = InferenceEngine()
#     engine.run_inference()


