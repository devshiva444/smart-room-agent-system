"""
Productivity Agent - The Scribe
Analyzes workspace discussions and meeting transcripts using LLM semantic parsing.
Now fully upgraded to read natural human language without requiring hardcoded 'TODO:' or 'ACTION:' tags.
Includes a robust regex-based fallback for offline resilience and preserves all legacy functions.
"""

import json
import re
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

# OpenAI client ko safe tarike se import karne ka try karein
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class ProductivityAgent:
    """
    Productivity Agent - Meeting & Transcript Analyzer
    
    Processes unstructured natural language discussions to extract:
    - Summary of key discussion points
    - Action items with assignees and priorities (semantic extraction)
    - Key topics and tags
    """
    
    # Priority classify karne ke liye keywords
    PRIORITY_KEYWORDS = {
        "high": ["urgent", "critical", "asap", "immediately", "blocking", "high priority", "must"],
        "medium": ["soon", "this week", "important", "should", "by Friday"],
        "low": ["when possible", "consider", "eventually", "nice to have"],
    }
    
    # Action item detect karne ke liye keywords (Legacy compatibility)
    ACTION_KEYWORDS = {
        "assign": ["assign", "assigned to", "owner is"],
        "create": ["create", "build", "implement", "develop"],
        "review": ["review", "check", "audit", "validate"],
        "fix": ["fix", "repair", "resolve", "patch"],
        "document": ["document", "write", "record", "log"],
        "deploy": ["deploy", "release", "publish", "ship"],
        "test": ["test", "qa", "verify"],
    }
    
    def __init__(self):
        """Initialize Productivity Agent with LLM capability."""
        # Stats aur counters reset karein
        self.transcripts_processed = 0
        self.action_items_extracted = 0
        
        # Env variables se API key aur config load karein
        self.api_key = os.getenv("HF_TOKEN") or os.getenv("AZURE_OPENAI_KEY") or os.getenv("OPENAI_API_KEY")
        self.api_base = os.getenv("API_BASE_URL", "http://localhost:11434/v1")  # Default local Ollama port
        self.model_name = os.getenv("MODEL_NAME", "phi3")  # Microsoft Phi-3 model offline mode ke liye
        
        self.client = None
        if OpenAI is not None and self.api_key:
            try:
                # LLM Client setup karein
                self.client = OpenAI(base_url=self.api_base, api_key=self.api_key)
                print(f"[ProductivityAgent] Connected to LLM Scribe Engine using model {self.model_name}")
            except Exception as e:
                print(f"[ProductivityAgent] Failed to init LLM. Falling back to pattern-matching: {e}")
                
    def analyze_transcript(self, transcript: str) -> Dict[str, Any]:
        """
        Unstructured text analyze karein. Pehle AI try karega, fail hone par local regex fallback chalega.
        """
        if not transcript or not isinstance(transcript, str):
            return self._empty_result()
            
        cleaned = self._clean_text(transcript)
        
        # Agar AI available hai toh smart semantic extraction chalao
        if self.client:
            try:
                ai_result = self._query_llm_for_extraction(cleaned)
                if ai_result:
                    self.transcripts_processed += 1
                    self.action_items_extracted += len(ai_result.get("action_items", []))
                    return {
                        "timestamp": datetime.utcnow().isoformat(),
                        "status": "success",
                        "summary": ai_result.get("summary", "Meeting processed via AI Scribe."),
                        "topics": ai_result.get("topics", []),
                        "action_items": ai_result.get("action_items", []),
                        "metadata": {
                            "processed_by": "AzureOpenAI_Scribe",
                            "transcript_length": len(cleaned),
                            "action_items_count": len(ai_result.get("action_items", []))
                        }
                    }
            except Exception as e:
                print(f"[ProductivityAgent] AI extraction failed: {str(e)}. Switching to local heuristics.")
                
        # --- OFFLINE HEURISTIC FALLBACK (Internet/AI na hone par) ---
        summary = self._extract_summary(cleaned)
        action_items = self._extract_action_items(cleaned)
        topics = self._extract_topics(cleaned)
        
        self.transcripts_processed += 1
        self.action_items_extracted += len(action_items)
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "status": "success",
            "summary": summary,
            "topics": topics,
            "action_items": action_items,
            "metadata": {
                "processed_by": "Heuristic_Fallback_Engine",
                "transcript_length": len(cleaned),
                "action_items_count": len(action_items),
            }
        }

    def _query_llm_for_extraction(self, transcript: str) -> Optional[Dict[str, Any]]:
        """
        Microsoft Azure OpenAI ya Local LLM ke madhyam se natural text ko parse karke clean JSON nikalein.
        """
        prompt = f"""
You are the Lead Workspace Scribe Agent. Your job is to listen to unstructured corporate meeting discussions and extract actionable developer tasks.
Do not require any tags like "TODO" or "ACTION". Instead, understand the natural conversation semantics.

TRANSCRIPT:
"{transcript}"

Analyze the text and output exactly in the following JSON format. Return ONLY the raw JSON block without markdown, sentences, or explanations.

JSON FORMAT:
{{
  "summary": "A concise 1-2 sentence summary of what was discussed.",
  "topics": ["database", "backend", "api", "deployment"],
  "action_items": [
    {{
      "task": "A clear, concise, actionable task description",
      "assignee": "Extract the specific person name if assigned, or use 'Unassigned'",
      "priority": "high" or "medium" or "low" based on verbal urgency cues,
      "action_type": "create" or "fix" or "review" or "deploy" or "test" or "document" or "general",
      "status": "pending",
      "created_at": "{datetime.utcnow().isoformat()}"
    }}
  ]
}}
"""
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": "You are a precise data extractor. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=500
        )
        
        response_text = response.choices[0].message.content.strip()
        # Markdown backticks clear karein
        response_text = re.sub(r"```json\s*|```", "", response_text)
        
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            print("[ProductivityAgent] Failed to parse LLM response JSON.")
            return None

    # ===== HEURISTIC FALLBACK METHODS (Local rules base) =====

    def _empty_result(self) -> Dict[str, Any]:
        """Khaali template jab text na mila ho."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "status": "empty",
            "summary": "No content to analyze",
            "topics": [],
            "action_items": [],
            "metadata": {}
        }
    
    def _clean_text(self, text: str) -> str:
        """Text se space aur brackets clean karein."""
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\[.*?\]', '', text)
        return text.strip()
    
    def _extract_summary(self, text: str) -> str:
        """Pehle do sentences lekar summary banayein."""
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            return "No summary available."
        summary = ". ".join(sentences[:2])
        if len(summary) > 300:
            summary = summary[:297] + "..."
        return summary + "."
    
    def _extract_topics(self, text: str) -> List[str]:
        """Pure original keywords aur topics list ko check karein."""
        topics = []
        
        # Technical fields keywords
        tech_keywords = ["api", "database", "frontend", "backend", "deployment", "testing", "architecture", "performance", "security"]
        for keyword in tech_keywords:
            if keyword.lower() in text.lower():
                topics.append(keyword)
                
        # Feature work related keywords
        work_keywords = ["feature", "bug", "issue", "refactor", "optimization", "migration", "integration"]
        for keyword in work_keywords:
            if keyword.lower() in text.lower():
                topics.append(keyword)
                
        return list(set(topics))
    
    def _extract_action_items(self, text: str) -> List[Dict[str, Any]]:
        """Text se task details aur assignees dhoondhein."""
        action_items = []
        
        # 1. Manual TODO pattern check karein (Tagging safety ke liye)
        pattern = r"(?i)(?:todo|action|task|assigned)\s*:?\s*([^.!?]+?)(?:assigned to|owner|responsible)?(?:\s+(\w+))?"
        matches = re.finditer(pattern, text)
        for match in matches:
            task_text = match.group(1).strip()
            assignee = match.group(2).strip() if match.group(2) else "Unassigned"
            priority = self._classify_priority(task_text)
            action_type = self._classify_action_type(task_text)
            
            action_items.append({
                "task": task_text,
                "assignee": assignee,
                "priority": priority,
                "action_type": action_type,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
            })
            
        # 2. Smart Natural Language Regex (Assignee + Auxiliary + Verb + Desc)
        # Matches: "Alice will refactor", "Bob should test" etc.
        natural_pattern = r"(?i)\b([A-Z][a-z]+)\s+(?:needs\s+to|should|has\s+to|must|will|is\s+going\s+to)\s+(?:urgently\s+)?(refactor|fix|deploy|review|create|update|implement|test|write|check|analyse|analyze|post|develop|setup|configure)\s+([^.!?]+)"
        matches = re.finditer(natural_pattern, text)
        for match in matches:
            assignee = match.group(1).strip()
            verb = match.group(2).strip()
            desc = match.group(3).strip()
            task_text = f"{verb.capitalize()} {desc}"
            
            # Deduplicate checking (Double entries rokne ke liye)
            if any(t["task"].lower() in task_text.lower() for t in action_items):
                continue
                
            priority = self._classify_priority(text)
            action_type = self._classify_action_type(verb)
            
            action_items.append({
                "task": task_text,
                "assignee": assignee,
                "priority": priority,
                "action_type": action_type,
                "status": "pending",
                "created_at": datetime.utcnow().isoformat(),
            })
            
        # Agar upar dono nahi chale toh direct imperative action dhoondho
        if not action_items:
            action_items = self._extract_imperative_actions(text)
            
        return action_items
    
    def _extract_imperative_actions(self, text: str) -> List[Dict[str, Any]]:
        """Sentences dhoondhein jo seedhe key verbs se start hote hain."""
        action_items = []
        sentences = re.split(r'[.!?]+', text)
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            imperative_verbs = ["implement", "create", "fix", "update", "deploy", "test", "review", "write", "check"]
            for verb in imperative_verbs:
                if sentence.lower().startswith(verb):
                    priority = self._classify_priority(sentence)
                    action_type = self._classify_action_type(sentence)
                    action_items.append({
                        "task": sentence,
                        "assignee": "Unassigned",
                        "priority": priority,
                        "action_type": action_type,
                        "status": "pending",
                        "created_at": datetime.utcnow().isoformat(),
                    })
                    break
        return action_items
    
    def _classify_priority(self, text: str) -> str:
        """Urgency keywords ke base par priority decide karein."""
        text_lower = text.lower()
        for priority, keywords in self.PRIORITY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return priority
        return "medium"
    
    def _classify_action_type(self, text: str) -> str:
        """Text content ke base par work category set karein."""
        text_lower = text.lower()
        for action_type, keywords in self.ACTION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return action_type
        return "general"
    
    def get_stats(self) -> Dict[str, Any]:
        """Agent processing metrics return karein."""
        return {
            "agent_type": "Productivity",
            "transcripts_processed": self.transcripts_processed,
            "action_items_extracted": self.action_items_extracted,
            "average_items_per_transcript": (
                self.action_items_extracted / self.transcripts_processed
                if self.transcripts_processed > 0 else 0
            ),
        }

    def batch_analyze(self, transcripts: List[str]) -> List[Dict[str, Any]]:
        """Multiple transcripts ko loop me analyze karein (Legacy original code)."""
        return [self.analyze_transcript(t) for t in transcripts]







# """
# Productivity Agent - The Scribe
# Analyzes workspace discussions and meeting transcripts using LLM semantic parsing.
# Now fully upgraded to read natural human language without requiring hardcoded 'TODO:' or 'ACTION:' tags.
# Includes a robust regex-based fallback for offline resilience.
# """

# import json
# import re
# import os
# from typing import Dict, Any, List, Optional
# from datetime import datetime

# # Import OpenAI client safely
# try:
#     from openai import OpenAI
# except ImportError:
#     OpenAI = None


# class ProductivityAgent:
#     """
#     Productivity Agent - Meeting & Transcript Analyzer
    
#     Processes unstructured natural language discussions to extract:
#     - Summary of key discussion points
#     - Action items with assignees and priorities (semantic extraction)
#     - Key topics and tags
#     """
    
#     # Keywords for priority classification (fallback)
#     PRIORITY_KEYWORDS = {
#         "high": ["urgent", "critical", "asap", "immediately", "blocking", "high priority", "must"],
#         "medium": ["soon", "this week", "important", "should", "by Friday"],
#         "low": ["when possible", "consider", "eventually", "nice to have"],
#     }
    
#     # Keywords for action item detection (fallback)
#     ACTION_KEYWORDS = {
#         "assign": ["assign", "assigned to", "owner is"],
#         "create": ["create", "build", "implement", "develop"],
#         "review": ["review", "check", "audit", "validate"],
#         "fix": ["fix", "repair", "resolve", "patch"],
#         "document": ["document", "write", "record", "log"],
#         "deploy": ["deploy", "release", "publish", "ship"],
#         "test": ["test", "qa", "verify"],
#     }
    
#     def __init__(self):
#         """Initialize Productivity Agent with LLM capability."""
#         self.transcripts_processed = 0
#         self.action_items_extracted = 0
        
#         # Configure LLM Client
#         self.api_key = os.getenv("HF_TOKEN") or os.getenv("AZURE_OPENAI_KEY") or os.getenv("OPENAI_API_KEY")
#         self.api_base = os.getenv("API_BASE_URL", "http://localhost:11434/v1")  # Defaults to Local Ollama
#         self.model_name = os.getenv("MODEL_NAME", "phi3")  # Microsoft Phi-3 for offline privacy
        
#         self.client = None
#         if OpenAI is not None and self.api_key:
#             try:
#                 self.client = OpenAI(base_url=self.api_base, api_key=self.api_key)
#                 print(f"[ProductivityAgent] Connected to LLM Scribe Engine using model {self.model_name}")
#             except Exception as e:
#                 print(f"[ProductivityAgent] Failed to init LLM. Falling back to pattern-matching: {e}")
                
#     def analyze_transcript(self, transcript: str) -> Dict[str, Any]:
#         """
#         Analyze unstructured meeting text. Uses AI first, falls back to Regex if offline.
#         """
#         if not transcript or not isinstance(transcript, str):
#             return self._empty_result()
            
#         cleaned = self._clean_text(transcript)
        
#         # If AI Gateway is active, perform smart semantic extraction
#         if self.client:
#             try:
#                 ai_result = self._query_llm_for_extraction(cleaned)
#                 if ai_result:
#                     self.transcripts_processed += 1
#                     self.action_items_extracted += len(ai_result.get("action_items", []))
#                     return {
#                         "timestamp": datetime.utcnow().isoformat(),
#                         "status": "success",
#                         "summary": ai_result.get("summary", "Meeting processed via AI Scribe."),
#                         "topics": ai_result.get("topics", []),
#                         "action_items": ai_result.get("action_items", []),
#                         "metadata": {
#                             "processed_by": "AzureOpenAI_Scribe",
#                             "transcript_length": len(cleaned),
#                             "action_items_count": len(ai_result.get("action_items", []))
#                         }
#                     }
#             except Exception as e:
#                 print(f"[ProductivityAgent] AI extraction failed: {str(e)}. Switching to local heuristics.")
                
#         # --- OFFLINE HEURISTIC FALLBACK ---
#         summary = self._extract_summary(cleaned)
#         action_items = self._extract_action_items(cleaned)
#         topics = self._extract_topics(cleaned)
        
#         self.transcripts_processed += 1
#         self.action_items_extracted += len(action_items)
        
#         return {
#             "timestamp": datetime.utcnow().isoformat(),
#             "status": "success",
#             "summary": summary,
#             "topics": topics,
#             "action_items": action_items,
#             "metadata": {
#                 "processed_by": "Heuristic_Fallback_Engine",
#                 "transcript_length": len(cleaned),
#                 "action_items_count": len(action_items),
#             }
#         }

#     def _query_llm_for_extraction(self, transcript: str) -> Optional[Dict[str, Any]]:
#         """
#         Uses Microsoft Azure OpenAI / Local Phi-3 to parse unstructured discussions into clean JSON.
#         """
#         prompt = f"""
# You are the Lead Workspace Scribe Agent. Your job is to listen to unstructured corporate meeting discussions and extract actionable developer tasks.
# Do not require any tags like "TODO" or "ACTION". Instead, understand the natural conversation semantics.

# TRANSCRIPT:
# "{transcript}"

# Analyze the text and output exactly in the following JSON format. Return ONLY the raw JSON block without markdown, sentences, or explanations.

# JSON FORMAT:
# {{
#   "summary": "A concise 1-2 sentence summary of what was discussed.",
#   "topics": ["database", "backend", "api", "deployment"],
#   "action_items": [
#     {{
#       "task": "A clear, concise, actionable task description",
#       "assignee": "Extract the specific person name if assigned, or use 'Unassigned'",
#       "priority": "high" or "medium" or "low" based on verbal urgency cues,
#       "action_type": "create" or "fix" or "review" or "deploy" or "test" or "document" or "general",
#       "status": "pending",
#       "created_at": "{datetime.utcnow().isoformat()}"
#     }}
#   ]
# }}
# """
#         response = self.client.chat.completions.create(
#             model=self.model_name,
#             messages=[
#                 {"role": "system", "content": "You are a precise data extractor. Return only valid JSON."},
#                 {"role": "user", "content": prompt}
#             ],
#             temperature=0.1,
#             max_tokens=500
#         )
        
#         response_text = response.choices[0].message.content.strip()
#         # Clean potential markdown JSON fences
#         response_text = re.sub(r"```json\s*|```", "", response_text)
        
#         try:
#             return json.loads(response_text)
#         except json.JSONDecodeError:
#             print("[ProductivityAgent] Failed to parse LLM response JSON.")
#             return None

#     # ===== HEURISTIC FALLBACK METHODS =====

#     def _empty_result(self) -> Dict[str, Any]:
#         return {
#             "timestamp": datetime.utcnow().isoformat(),
#             "status": "empty",
#             "summary": "No content to analyze",
#             "topics": [],
#             "action_items": [],
#             "metadata": {}
#         }
    
#     def _clean_text(self, text: str) -> str:
#         text = re.sub(r'\s+', ' ', text)
#         text = re.sub(r'\[.*?\]', '', text)  # Remove bracket artifacts
#         return text.strip()
    
#     def _extract_summary(self, text: str) -> str:
#         sentences = re.split(r'[.!?]+', text)
#         sentences = [s.strip() for s in sentences if s.strip()]
#         if not sentences:
#             return "No summary available."
#         summary = ". ".join(sentences[:2])
#         if len(summary) > 300:
#             summary = summary[:297] + "..."
#         return summary + "."
    
#     def _extract_topics(self, text: str) -> List[str]:
#         topics = []
        
#         # Restore full original technical topics
#         tech_keywords = ["api", "database", "frontend", "backend", "deployment", "testing", "architecture", "performance", "security"]
#         for keyword in tech_keywords:
#             if keyword.lower() in text.lower():
#                 topics.append(keyword)
                
#         # Restore full original work items topics
#         work_keywords = ["feature", "bug", "issue", "refactor", "optimization", "migration", "integration"]
#         for keyword in work_keywords:
#             if keyword.lower() in text.lower():
#                 topics.append(keyword)
                
#         return list(set(topics))
    
#     def _extract_action_items(self, text: str) -> List[Dict[str, Any]]:
#         action_items = []
        
#         # 1. Pattern-matching for TODO style (keeps compatibility with manual tagging)
#         pattern = r"(?i)(?:todo|action|task|assigned)\s*:?\s*([^.!?]+?)(?:assigned to|owner|responsible)?(?:\s+(\w+))?"
#         matches = re.finditer(pattern, text)
#         for match in matches:
#             task_text = match.group(1).strip()
#             assignee = match.group(2).strip() if match.group(2) else "Unassigned"
#             priority = self._classify_priority(task_text)
#             action_type = self._classify_action_type(task_text)
            
#             action_items.append({
#                 "task": task_text,
#                 "assignee": assignee,
#                 "priority": priority,
#                 "action_type": action_type,
#                 "status": "pending",
#                 "created_at": datetime.utcnow().isoformat(),
#             })
            
#         # 2. Smart Natural Language Regex (Assignee + Helper Verb + Action Verb + Description)
#         # Matches: "Alice needs to urgently refactor the database" or "Bob should review the code"
#         natural_pattern = r"(?i)\b([A-Z][a-z]+)\s+(?:needs\s+to|should|has\s+to|must|will|is\s+going\s+to)\s+(?:urgently\s+)?(refactor|fix|deploy|review|create|update|implement|test|write|check|analyse|analyze|post|develop|setup|configure)\s+([^.!?]+)"
#         matches = re.finditer(natural_pattern, text)
#         for match in matches:
#             assignee = match.group(1).strip()
#             verb = match.group(2).strip()
#             desc = match.group(3).strip()
#             task_text = f"{verb.capitalize()} {desc}"
            
#             # Deduplicate to prevent overlapping matches
#             if any(t["task"].lower() in task_text.lower() for t in action_items):
#                 continue
                
#             priority = self._classify_priority(text)
#             action_type = self._classify_action_type(verb)
            
#             action_items.append({
#                 "task": task_text,
#                 "assignee": assignee,
#                 "priority": priority,
#                 "action_type": action_type,
#                 "status": "pending",
#                 "created_at": datetime.utcnow().isoformat(),
#             })
            
#         if not action_items:
#             action_items = self._extract_imperative_actions(text)
            
#         return action_items
    
#     def _extract_imperative_actions(self, text: str) -> List[Dict[str, Any]]:
#         action_items = []
#         sentences = re.split(r'[.!?]+', text)
#         for sentence in sentences:
#             sentence = sentence.strip()
#             if not sentence:
#                 continue
#             imperative_verbs = ["implement", "create", "fix", "update", "deploy", "test", "review", "write", "check"]
#             for verb in imperative_verbs:
#                 if sentence.lower().startswith(verb):
#                     priority = self._classify_priority(sentence)
#                     action_type = self._classify_action_type(sentence)
#                     action_items.append({
#                         "task": sentence,
#                         "assignee": "Unassigned",
#                         "priority": priority,
#                         "action_type": action_type,
#                         "status": "pending",
#                         "created_at": datetime.utcnow().isoformat(),
#                     })
#                     break
#         return action_items
    
#     def _classify_priority(self, text: str) -> str:
#         text_lower = text.lower()
#         for priority, keywords in self.PRIORITY_KEYWORDS.items():
#             for keyword in keywords:
#                 if keyword in text_lower:
#                     return priority
#         return "medium"
    
#     def _classify_action_type(self, text: str) -> str:
#         text_lower = text.lower()
#         for action_type, keywords in self.ACTION_KEYWORDS.items():
#             for keyword in keywords:
#                 if keyword in text_lower:
#                     return action_type
#         return "general"
    
#     def get_stats(self) -> Dict[str, Any]:
#         return {
#             "agent_type": "Productivity",
#             "transcripts_processed": self.transcripts_processed,
#             "action_items_extracted": self.action_items_extracted,
#         }





# """
# Productivity Agent - The Scribe
# Analyzes workspace discussions and meeting transcripts using LLM semantic parsing.
# Now fully upgraded to read natural human language without requiring hardcoded 'TODO:' or 'ACTION:' tags.
# Includes a robust regex-based fallback for offline resilience.
# """

# import json
# import re
# import os
# from typing import Dict, Any, List, Optional
# from datetime import datetime

# # Import OpenAI client safely
# try:
#     from openai import OpenAI
# except ImportError:
#     OpenAI = None


# class ProductivityAgent:
#     """
#     Productivity Agent - Meeting & Transcript Analyzer
    
#     Processes unstructured natural language discussions to extract:
#     - Summary of key discussion points
#     - Action items with assignees and priorities (semantic extraction)
#     - Key topics and tags
#     """
    
#     # Keywords for priority classification (fallback)
#     PRIORITY_KEYWORDS = {
#         "high": ["urgent", "critical", "asap", "immediately", "blocking", "high priority", "must"],
#         "medium": ["soon", "this week", "important", "should", "by Friday"],
#         "low": ["when possible", "consider", "eventually", "nice to have"],
#     }
    
#     # Keywords for action item detection (fallback)
#     ACTION_KEYWORDS = {
#         "assign": ["assign", "assigned to", "owner is"],
#         "create": ["create", "build", "implement", "develop"],
#         "review": ["review", "check", "audit", "validate"],
#         "fix": ["fix", "repair", "resolve", "patch"],
#         "document": ["document", "write", "record", "log"],
#         "deploy": ["deploy", "release", "publish", "ship"],
#         "test": ["test", "qa", "verify"],
#     }
    
#     def __init__(self):
#         """Initialize Productivity Agent with LLM capability."""
#         self.transcripts_processed = 0
#         self.action_items_extracted = 0
        
#         # Configure LLM Client
#         self.api_key = os.getenv("HF_TOKEN") or os.getenv("AZURE_OPENAI_KEY") or os.getenv("OPENAI_API_KEY")
#         self.api_base = os.getenv("API_BASE_URL", "http://localhost:11434/v1")  # Defaults to Local Ollama
#         self.model_name = os.getenv("MODEL_NAME", "phi3")  # Microsoft Phi-3 for offline privacy
        
#         self.client = None
#         if OpenAI is not None and self.api_key:
#             try:
#                 self.client = OpenAI(base_url=self.api_base, api_key=self.api_key)
#                 print(f"[ProductivityAgent] Connected to LLM Scribe Engine using model {self.model_name}")
#             except Exception as e:
#                 print(f"[ProductivityAgent] Failed to init LLM. Falling back to pattern-matching: {e}")
                
#     def analyze_transcript(self, transcript: str) -> Dict[str, Any]:
#         """
#         Analyze unstructured meeting text. Uses AI first, falls back to Regex if offline.
#         """
#         if not transcript or not isinstance(transcript, str):
#             return self._empty_result()
            
#         cleaned = self._clean_text(transcript)
        
#         # If AI Gateway is active, perform smart semantic extraction
#         if self.client:
#             try:
#                 ai_result = self._query_llm_for_extraction(cleaned)
#                 if ai_result:
#                     self.transcripts_processed += 1
#                     self.action_items_extracted += len(ai_result.get("action_items", []))
#                     return {
#                         "timestamp": datetime.utcnow().isoformat(),
#                         "status": "success",
#                         "summary": ai_result.get("summary", "Meeting processed via AI Scribe."),
#                         "topics": ai_result.get("topics", []),
#                         "action_items": ai_result.get("action_items", []),
#                         "metadata": {
#                             "processed_by": "AzureOpenAI_Scribe",
#                             "transcript_length": len(cleaned),
#                             "action_items_count": len(ai_result.get("action_items", []))
#                         }
#                     }
#             except Exception as e:
#                 print(f"[ProductivityAgent] AI extraction failed: {str(e)}. Switching to local heuristics.")
                
#         # --- OFFLINE HEURISTIC FALLBACK ---
#         summary = self._extract_summary(cleaned)
#         action_items = self._extract_action_items(cleaned)
#         topics = self._extract_topics(cleaned)
        
#         self.transcripts_processed += 1
#         self.action_items_extracted += len(action_items)
        
#         return {
#             "timestamp": datetime.utcnow().isoformat(),
#             "status": "success",
#             "summary": summary,
#             "topics": topics,
#             "action_items": action_items,
#             "metadata": {
#                 "processed_by": "Heuristic_Fallback_Engine",
#                 "transcript_length": len(cleaned),
#                 "action_items_count": len(action_items),
#             }
#         }

#     def _query_llm_for_extraction(self, transcript: str) -> Optional[Dict[str, Any]]:
#         """
#         Uses Microsoft Azure OpenAI / Local Phi-3 to parse unstructured discussions into clean JSON.
#         """
#         prompt = f"""
# You are the Lead Workspace Scribe Agent. Your job is to listen to unstructured corporate meeting discussions and extract actionable developer tasks.
# Do not require any tags like "TODO" or "ACTION". Instead, understand the natural conversation semantics.

# TRANSCRIPT:
# "{transcript}"

# Analyze the text and output exactly in the following JSON format. Return ONLY the raw JSON block without markdown, sentences, or explanations.

# JSON FORMAT:
# {{
#   "summary": "A concise 1-2 sentence summary of what was discussed.",
#   "topics": ["database", "backend", "api", "deployment"],
#   "action_items": [
#     {{
#       "task": "A clear, concise, actionable task description",
#       "assignee": "Extract the specific person name if assigned, or use 'Unassigned'",
#       "priority": "high" or "medium" or "low" based on verbal urgency cues,
#       "action_type": "create" or "fix" or "review" or "deploy" or "test" or "document" or "general",
#       "status": "pending",
#       "created_at": "{datetime.utcnow().isoformat()}"
#     }}
#   ]
# }}
# """
#         response = self.client.chat.completions.create(
#             model=self.model_name,
#             messages=[
#                 {"role": "system", "content": "You are a precise data extractor. Return only valid JSON."},
#                 {"role": "user", "content": prompt}
#             ],
#             temperature=0.1,
#             max_tokens=500
#         )
        
#         response_text = response.choices[0].message.content.strip()
#         # Clean potential markdown JSON fences
#         response_text = re.sub(r"```json\s*|```", "", response_text)
        
#         try:
#             return json.loads(response_text)
#         except json.JSONDecodeError:
#             print("[ProductivityAgent] Failed to parse LLM response JSON.")
#             return None

#     # ===== HEURISTIC FALLBACK METHODS =====

#     def _empty_result(self) -> Dict[str, Any]:
#         return {
#             "timestamp": datetime.utcnow().isoformat(),
#             "status": "empty",
#             "summary": "No content to analyze",
#             "topics": [],
#             "action_items": [],
#             "metadata": {}
#         }
    
#     def _clean_text(self, text: str) -> str:
#         text = re.sub(r'\s+', ' ', text)
#         text = re.sub(r'\[.*?\]', '', text)  # Remove bracket artifacts
#         return text.strip()
    
#     def _extract_summary(self, text: str) -> str:
#         sentences = re.split(r'[.!?]+', text)
#         sentences = [s.strip() for s in sentences if s.strip()]
#         if not sentences:
#             return "No summary available."
#         summary = ". ".join(sentences[:2])
#         if len(summary) > 300:
#             summary = summary[:297] + "..."
#         return summary + "."
    
#     def _extract_topics(self, text: str) -> List[str]:
#         topics = []
#         tech_keywords = ["api", "database", "frontend", "backend", "deployment", "testing", "architecture", "security"]
#         for keyword in tech_keywords:
#             if keyword.lower() in text.lower():
#                 topics.append(keyword)
#         return list(set(topics))
    
#     def _extract_action_items(self, text: str) -> List[Dict[str, Any]]:
#         action_items = []
#         # Pattern-matching for TODO style (keeps compatibility with manual tagging)
#         pattern = r"(?i)(?:todo|action|task|assigned)\s*:?\s*([^.!?]+?)(?:assigned to|owner|responsible)?(?:\s+(\w+))?"
#         matches = re.finditer(pattern, text)
        
#         for match in matches:
#             task_text = match.group(1).strip()
#             assignee = match.group(2).strip() if match.group(2) else "Unassigned"
#             priority = self._classify_priority(task_text)
#             action_type = self._classify_action_type(task_text)
            
#             action_items.append({
#                 "task": task_text,
#                 "assignee": assignee,
#                 "priority": priority,
#                 "action_type": action_type,
#                 "status": "pending",
#                 "created_at": datetime.utcnow().isoformat(),
#             })
            
#         if not action_items:
#             action_items = self._extract_imperative_actions(text)
            
#         return action_items
    
#     def _extract_imperative_actions(self, text: str) -> List[Dict[str, Any]]:
#         action_items = []
#         sentences = re.split(r'[.!?]+', text)
#         for sentence in sentences:
#             sentence = sentence.strip()
#             if not sentence:
#                 continue
#             imperative_verbs = ["implement", "create", "fix", "update", "deploy", "test", "review", "write", "check"]
#             for verb in imperative_verbs:
#                 if sentence.lower().startswith(verb):
#                     priority = self._classify_priority(sentence)
#                     action_type = self._classify_action_type(sentence)
#                     action_items.append({
#                         "task": sentence,
#                         "assignee": "Unassigned",
#                         "priority": priority,
#                         "action_type": action_type,
#                         "status": "pending",
#                         "created_at": datetime.utcnow().isoformat(),
#                     })
#                     break
#         return action_items
    
#     def _classify_priority(self, text: str) -> str:
#         text_lower = text.lower()
#         for priority, keywords in self.PRIORITY_KEYWORDS.items():
#             for keyword in keywords:
#                 if keyword in text_lower:
#                     return priority
#         return "medium"
    
#     def _classify_action_type(self, text: str) -> str:
#         text_lower = text.lower()
#         for action_type, keywords in self.ACTION_KEYWORDS.items():
#             for keyword in keywords:
#                 if keyword in text_lower:
#                     return action_type
#         return "general"
    
#     def get_stats(self) -> Dict[str, Any]:
#         return {
#             "agent_type": "Productivity",
#             "transcripts_processed": self.transcripts_processed,
#             "action_items_extracted": self.action_items_extracted,
#         }


