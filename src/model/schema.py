from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class Pattern(BaseModel):
    source: str
    target: str
    relation: str

    def __str__(self):
        return f"{self.source}-[:{self.relation}]->{self.target}"


class NodeSchema(BaseModel):
    node_type: str
    properties: List[str]
    samples: List[str]
    embeddings: List[float]
    out_relations: Optional[List[str]]
    in_relations: Optional[List[str]]
    patterns: Optional[List[Pattern]]

    model_config = {
        "json_encoders": {
            Pattern: lambda x: str(x),
        },
    }


if __name__ == "__main__":
    pattern = Pattern(source="Person", target="Person", relation="friends")
    node_schema = NodeSchema(
        node_type="Person",
        properties=["name", "age"],
        out_relations=["friends"],
        in_relations=["friends"],
        patterns=[pattern],
        embeddings=[0.1, 0.2, 0.3],
    )
    print(node_schema.model_dump(mode="json"))
    print(str(pattern))
