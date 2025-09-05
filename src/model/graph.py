from pydantic import BaseModel
from typing import Optional, List, Dict
import yaml


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
    examples: Optional[List[Dict[str, str]]] = None

    def to_md(self) -> str:
        md = []

        node_types = [node.node_type for node in self.nodes]
        relation_types = [relation.relation_type for relation in self.relations]
        md.append("# Graph Schema\n")
        md.append("## Overall Node Types and Relations Types\n")
        md.append(f"**Node Types**:\n\n{node_types}\n\n")
        md.append(f"**Relation Types**:\n\n{relation_types}\n\n")

        md.append("## Node Details\n")
        for node in self.nodes:
            md.append(f"- `{node.node_type}` has properties: {node.properties}\n")

        # Write the generated markdown to 'graph_schema.md'
        with open("graph_schema.md", "w", encoding="utf-8") as f:
            f.write("".join(md))
        return "".join(md)

    @classmethod
    def from_yaml(cls, yaml_file: str) -> "GraphSchema":
        """
        Parse a YAML file into a GraphSchema object.

        Args:
            yaml_file: Path to the YAML file containing the schema

        Returns:
            GraphSchema: Parsed schema object
        """
        with open(yaml_file, "r", encoding="utf-8") as file:
            data = yaml.safe_load(file)

        schema_data = data.get("schema", {})

        # Parse nodes
        nodes = []
        node_labels = schema_data.get("nodeLabels", [])
        node_properties = schema_data.get("nodeProperties", {})

        for node_label in node_labels:
            properties = []
            if node_label in node_properties:
                # Handle different formats of properties
                prop_list = node_properties[node_label]
                if isinstance(prop_list, list):
                    for prop in prop_list:
                        if isinstance(prop, str):
                            # Handle format like "name: string" or just "name"
                            properties.append(prop.split(":")[0].strip())
                        else:
                            properties.append(str(prop))
                else:
                    properties = []

            nodes.append(
                NodesInfo(node_type=node_label, properties=properties, samples=None)
            )

        # Parse relations
        relations = []
        relationships = schema_data.get("relationships", [])

        for rel in relationships:
            rel_type = rel.get("type", "")
            properties = []

            # Extract properties if they exist
            if "properties" in rel:
                for prop_name, prop_type in rel["properties"].items():
                    properties.append(f"{prop_name}: {prop_type}")

            relations.append(
                RelationsInfo(
                    relation_type=rel_type, properties=properties, samples=None
                )
            )

        # Parse indexes and constraints
        indexes = []
        constraints = []
        index_constraint_list = schema_data.get("indexes", [])

        for item in index_constraint_list:
            if isinstance(item, str):
                if "CONSTRAINT" in item.upper():
                    constraints.append({"constraint": item})
                elif "INDEX" in item.upper():
                    indexes.append({"index": item})
                else:
                    # Default to index if unclear
                    indexes.append({"index": item})

        # Parse guidelines
        guidelines = schema_data.get("guidelines", None)

        # Parse examples
        examples = None
        example_queries = schema_data.get("exampleQueries", [])
        if example_queries:
            examples = []
            for example in example_queries:
                if (
                    isinstance(example, dict)
                    and "question" in example
                    and "cypher" in example
                ):
                    examples.append(
                        {
                            "question": example["question"],
                            "cypher": example["cypher"].strip()
                            if isinstance(example["cypher"], str)
                            else str(example["cypher"]),
                        }
                    )

        return cls(
            nodes=nodes,
            relations=relations,
            constraints=constraints,
            indexes=indexes,
            guidelines=guidelines,
            examples=examples,
        )


if __name__ == "__main__":
    schema = GraphSchema.from_yaml(
        "/Users/ruipu/projects/KG_Demo/extracted_schema.yaml"
    )
    print(schema.to_md())
