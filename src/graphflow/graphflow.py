import os
from dotenv import load_dotenv
from openai import AsyncOpenAI
from src.utils import tools_to_openai_schema

load_dotenv()

class Planner:
    def __init__(self, model: str):
        self.llm = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
        )
        self.model = model
        self.system_prompt = """"""
    
    def plan(self, query: str):
        pass