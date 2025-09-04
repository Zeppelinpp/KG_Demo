from pydantic import BaseModel
from typing import Optional, List, Dict


class NodesInfo(BaseModel):
    """
    node_type: string describing the node type
    properties: list of properties of the node
    samples: list of samples of the node
    """

    node_type: str
    properties: List[str]
    samples: Optional[List[dict]] = None


class RelationsInfo(BaseModel):
    """
    relation_type: string describing the relation type
    properties: list of properties of the relation
    samples: list of samples of the relation
    """

    relation_type: str
    properties: List[str]
    samples: Optional[List[dict]] = None


class GraphSchema(BaseModel):
    """
    nodes: Different node types and their properties including samples data
    relations: Different relations types and their properties including samples data
    constraints: Constraints in the graph
    indexes: Indexes in the graph
    guidelines: Cypher gen guidlines for LLM (Optional)
    examples: Examples in query -> cypher pairs (Optional)
    """

    nodes: List[NodesInfo]
    relations: List[RelationsInfo]
    constraints: List[dict]
    indexes: List[dict]
    guidelines: Optional[List[str]] = None
    examples: List[Dict[str, str]] = None

    def to_md(self) -> str:
        md = []
        
        node_types = [node.node_type for node in self.nodes]
        relation_types = [relation.relation_type for relation in self.relations]
        md.append("# Graph Schema\n")
        md.append("## Overall Node Types and Relations Types\n")
        md.append(f"Node Types: {node_types}\n")
        md.append(f"Relation Types: {relation_types}\n")

        md.append("## Node Details\n")
        for node in self.nodes:
            md.append(f'- {node.node_type} has properties: {node.properties}\n')
            