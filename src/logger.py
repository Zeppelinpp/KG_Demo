"""
Logging configuration for KG Demo system
"""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path


class KGLogger:
    """Knowledge Graph system logger with structured logging"""

    def __init__(self, log_level: str = "INFO", log_file: Optional[str] = None):
        self.logger = logging.getLogger("KG_Demo")
        self.logger.setLevel(getattr(logging, log_level.upper()))

        # Clear existing handlers
        self.logger.handlers.clear()

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Only add file handler, no console output
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

        # Prevent propagation to root logger to avoid console output
        self.logger.propagate = False

    def _make_serializable(self, obj):
        """Convert objects to JSON-serializable format"""
        if isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        elif hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes)):
            # Handle RepeatedScalarContainer and similar objects
            try:
                return list(obj)
            except:
                return str(obj)
        elif hasattr(obj, "model_dump"):
            # Handle Pydantic models
            return obj.model_dump()
        elif hasattr(obj, "__dict__"):
            # Handle other objects with attributes
            return self._make_serializable(obj.__dict__)
        else:
            # For primitive types and others
            return obj

    def log_context_loading(
        self, query: str, resources: List[str], context_data: Dict[str, Any]
    ):
        """Log context manager loading information (excluding schema)"""
        self.logger.info(f"[CONTEXT MANAGER] Query: {query}")
        self.logger.info(f"[CONTEXT MANAGER] Resources: {resources}")
        self.logger.info(
            f"[CONTEXT MANAGER] Context loaded items: {len(context_data) if context_data else 0}"
        )
        if context_data:
            try:
                # Filter out schema content from context data
                filtered_data = []
                if isinstance(context_data, list):
                    for item in context_data:
                        if isinstance(item, dict):
                            content = item.get("content", "")
                            # Skip schema-related content
                            if not (isinstance(content, str) and 
                                   ("Graph Schema" in content or "KG Schema" in content or 
                                    "Node Details" in content or "Relationship Details" in content)):
                                filtered_data.append(item)
                        else:
                            filtered_data.append(item)
                else:
                    filtered_data = context_data
                
                # Try to serialize filtered context data
                serializable_data = self._make_serializable(filtered_data)
                self.logger.info(
                    f"[CONTEXT MANAGER] Context data (excluding schema): {json.dumps(serializable_data, ensure_ascii=False, indent=2)}"
                )
            except Exception as e:
                self.logger.info(
                    f"[CONTEXT MANAGER] Context data (raw, excluding schema): {str(context_data)}"
                )
                self.logger.warning(
                    f"[CONTEXT MANAGER] Failed to serialize context data: {e}"
                )
        else:
            self.logger.info("[CONTEXT MANAGER] No context data loaded")

    def log_llm_call(
        self,
        system_prompt: str,
        user_query: str,
        model: str,
        messages: List[Dict[str, Any]],
    ):
        """Log LLM call information - user message only"""
        self.logger.info(f"[LLM CALL] Model: {model}")
        self.logger.info(f"[LLM CALL] User Query: {user_query}")
        
        # Log only user and assistant messages, skip system messages
        user_messages = [msg for msg in messages if msg.get("role") in ["user", "assistant"]]
        self.logger.info(f"[LLM CALL] User Message History Count: {len(user_messages)}")
        for i, msg in enumerate(user_messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            self.logger.info(
                f"[LLM CALL] Message {i + 1} ({role}): {content[:200]}{'...' if len(content) > 200 else ''}"
            )

    def log_schema_usage(self, schema: str):
        """Log graph schema information"""
        # Skip logging schema content as requested
        self.logger.info(
            f"[SCHEMA] Graph schema loaded, length: {len(schema)} characters"
        )

    def log_tool_call(
        self, tool_name: str, tool_args: Dict[str, Any], tool_result: str
    ):
        """Log tool call information"""
        self.logger.info(f"[TOOL CALL] Tool: {tool_name}")
        try:
            serializable_args = self._make_serializable(tool_args)
            self.logger.info(
                f"[TOOL CALL] Arguments: {json.dumps(serializable_args, ensure_ascii=False, indent=2)}"
            )
        except Exception as e:
            self.logger.info(f"[TOOL CALL] Arguments (raw): {str(tool_args)}")
            self.logger.warning(f"[TOOL CALL] Failed to serialize tool arguments: {e}")

        # Limit result length for readability
        result_preview = (
            tool_result[:1000] + "..." if len(tool_result) > 1000 else tool_result
        )
        self.logger.info(f"[TOOL CALL] Result: {result_preview}")

    def log_llm_response(self, response: str):
        """Log LLM response"""
        self.logger.info(f"[LLM RESPONSE] {response}")

    def log_error(self, error_msg: str, context: Dict[str, Any] = None):
        """Log error information"""
        self.logger.error(f"[ERROR] {error_msg}")
        if context:
            try:
                serializable_context = self._make_serializable(context)
                self.logger.error(
                    f"[ERROR] Context: {json.dumps(serializable_context, ensure_ascii=False, indent=2)}"
                )
            except Exception as e:
                self.logger.error(f"[ERROR] Context (raw): {str(context)}")
                self.logger.warning(f"[ERROR] Failed to serialize error context: {e}")


# Global logger instance
kg_logger = KGLogger(log_level="INFO", log_file="logs/kg_demo.log")
