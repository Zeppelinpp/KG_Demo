from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class Mapping(BaseModel):
    """
    Represents a mapping between a term and its attributes
    """

    term: str
    term_embedding: List[float]
    attributes: List[str]

