import yaml
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Tuple


class NodeProperty(BaseModel):
    """Represents a node property with name and optional metadata"""

    name: str
    type: Optional[str] = None
    description: Optional[str] = None


class RelationshipProperty(BaseModel):
    """Represents a relationship property with name and optional metadata"""

    name: str
    type: Optional[str] = None
    description: Optional[str] = None


class RelationshipPattern(BaseModel):
    """Represents a relationship pattern between node types"""

    source_labels: List[str]
    target_labels: List[str]
    frequency: int


class NodeSample(BaseModel):
    """Represents a sample node with its properties"""

    properties: Dict[str, Any]


class RelationshipSample(BaseModel):
    """Represents a sample relationship with source/target labels and properties"""

    source_labels: List[str]
    target_labels: List[str]
    relation: Tuple


class DatabaseInfo(BaseModel):
    """Database connection and extraction metadata"""

    uri: str
    database: str
    extraction_time: str


class IndexInfo(BaseModel):
    """Represents a database index"""

    name: Optional[str] = None
    type: Optional[str] = None
    labelsOrTypes: Optional[List[str]] = None
    properties: Optional[List[str]] = None
    state: Optional[str] = None
    uniqueness: Optional[str] = None

    # Allow additional fields for different Neo4j versions
    class Config:
        extra = "allow"


class ConstraintInfo(BaseModel):
    """Represents a database constraint"""

    name: Optional[str] = None
    type: Optional[str] = None
    labelsOrTypes: Optional[List[str]] = None
    properties: Optional[List[str]] = None

    # Allow additional fields for different Neo4j versions
    class Config:
        extra = "allow"


class NodesInfo(BaseModel):
    """
    Extracted node information from Neo4j database
    Matches the structure from extract_node_labels_and_properties()
    """

    count: int
    properties: List[NodeProperty]
    samples: Optional[List[NodeSample]] = None

    # For backward compatibility with existing YAML parsing
    node_type: Optional[str] = None

    @classmethod
    def from_extracted_data(cls, node_label: str, extracted_data: Dict) -> "NodesInfo":
        """Create NodesInfo from extracted schema data"""
        properties = []
        if "properties" in extracted_data and extracted_data["properties"]:
            for prop in extracted_data["properties"]:
                if isinstance(prop, str):
                    properties.append(NodeProperty(name=prop))
                elif isinstance(prop, dict) and "name" in prop:
                    properties.append(NodeProperty(**prop))

        samples = []
        if "samples" in extracted_data and extracted_data["samples"]:
            for sample_data in extracted_data["samples"]:
                samples.append(NodeSample(properties=sample_data))

        return cls(
            node_type=node_label,
            count=extracted_data.get("count", 0),
            properties=properties,
            samples=samples if samples else None,
        )


class RelationsInfo(BaseModel):
    """
    Extracted relationship information from Neo4j database
    Matches the structure from extract_relationship_types_and_properties()
    """

    count: int
    properties: List[RelationshipProperty]
    patterns: Optional[List[RelationshipPattern]] = None
    samples: Optional[List[RelationshipSample]] = None

    # For backward compatibility with existing YAML parsing
    relation_type: Optional[str] = None

    @classmethod
    def from_extracted_data(
        cls, rel_type: str, extracted_data: Dict
    ) -> "RelationsInfo":
        """Create RelationsInfo from extracted schema data"""
        properties = []
        if "properties" in extracted_data and extracted_data["properties"]:
            for prop in extracted_data["properties"]:
                if isinstance(prop, str):
                    properties.append(RelationshipProperty(name=prop))
                elif isinstance(prop, dict) and "name" in prop:
                    properties.append(RelationshipProperty(**prop))

        patterns = []
        if "patterns" in extracted_data and extracted_data["patterns"]:
            for pattern_data in extracted_data["patterns"]:
                patterns.append(RelationshipPattern(**pattern_data))

        samples = []
        if "samples" in extracted_data and extracted_data["samples"]:
            for sample_data in extracted_data["samples"]:
                samples.append(RelationshipSample(**sample_data))

        return cls(
            relation_type=rel_type,
            count=extracted_data.get("count", 0),
            properties=properties,
            patterns=patterns if patterns else None,
            samples=samples if samples else None,
        )


class ExtractedGraphSchema(BaseModel):
    """
    Complete extracted Neo4j schema matching the structure from extract_full_schema()
    This represents the raw extracted data from Neo4j
    """

    database_info: DatabaseInfo
    nodes: Dict[str, Dict[str, Any]]  # node_label -> node_info
    relationships: Dict[str, Dict[str, Any]]  # rel_type -> rel_info
    constraints: List[Dict[str, Any]]
    indexes: List[Dict[str, Any]]

    @classmethod
    def from_extraction_result(cls, extraction_result: Dict) -> "ExtractedGraphSchema":
        """Create ExtractedGraphSchema from extraction result"""
        return cls(
            database_info=DatabaseInfo(**extraction_result["database_info"]),
            nodes=extraction_result.get("nodes", {}),
            relationships=extraction_result.get("relationships", {}),
            constraints=extraction_result.get("constraints", []),
            indexes=extraction_result.get("indexes", []),
        )

    def to_structured_schema(self) -> "GraphSchema":
        """Convert to structured GraphSchema with Pydantic models"""
        nodes = []
        for node_label, node_data in self.nodes.items():
            nodes.append(NodesInfo.from_extracted_data(node_label, node_data))

        relations = []
        for rel_type, rel_data in self.relationships.items():
            relations.append(RelationsInfo.from_extracted_data(rel_type, rel_data))

        # Convert constraints and indexes to structured models
        structured_constraints = []
        for constraint_data in self.constraints:
            structured_constraints.append(ConstraintInfo(**constraint_data))

        structured_indexes = []
        for index_data in self.indexes:
            structured_indexes.append(IndexInfo(**index_data))

        return GraphSchema(
            database_info=self.database_info,
            nodes=nodes,
            relations=relations,
            constraints=structured_constraints,
            indexes=structured_indexes,
        )


class GraphSchema(BaseModel):
    """
    Structured graph schema with Pydantic models for all components
    This is the processed version suitable for application use

    nodes: Different node types and their properties including samples data
    relations: Different relations types and their properties including samples data
    constraints: Structured constraints in the graph
    indexes: Structured indexes in the graph
    database_info: Database connection and extraction metadata
    guidelines: Cypher gen guidelines for LLM (Optional)
    examples: Examples in query -> cypher pairs (Optional)
    """

    database_info: Optional[DatabaseInfo] = None
    nodes: List[NodesInfo]
    relations: List[RelationsInfo]
    constraints: List[ConstraintInfo]
    indexes: List[IndexInfo]
    guidelines: Optional[List[str]] = None
    examples: Optional[List[Dict[str, str]]] = None

    @classmethod
    def from_extracted_schema(
        cls, extracted_schema: ExtractedGraphSchema
    ) -> "GraphSchema":
        """Create GraphSchema from ExtractedGraphSchema"""
        return extracted_schema.to_structured_schema()

    def to_md(self) -> str:
        md = []

        node_types = [node.node_type or "Unknown" for node in self.nodes]
        relation_types = [
            relation.relation_type or "Unknown" for relation in self.relations
        ]
        md.append("# Graph Schema\n")

        md.append("## Overall Node Types and Relations Types\n")
        md.append(f"**Node Types**:\n\n{node_types}\n\n")
        md.append(f"**Relation Types**:\n\n{relation_types}\n\n")

        md.append("## Node Details\n")
        for node in self.nodes:
            property_names = [prop.name for prop in node.properties]
            md.append(
                f"- `{node.node_type}` ({node.count} nodes) has properties: {property_names}\n"
            )

            # Add sample data if available
            if node.samples and len(node.samples) > 0:
                sample = node.samples[0]  # Show only one sample
                md.append(f"  - Sample data: {sample.properties}\n")

        md.append("\n## Relationship Details\n")
        for relation in self.relations:
            property_names = [prop.name for prop in relation.properties]
            md.append(
                f"- `{relation.relation_type}` ({relation.count} relationships) has properties: {property_names}\n"
            )
            if relation.patterns:
                md.append(f"  - Common patterns:\n")
                for pattern in relation.patterns[:3]:  # Show top 3 patterns
                    md.append(
                        f"    - {pattern.source_labels} -> {pattern.target_labels} (frequency: {pattern.frequency})\n"
                    )

            # Add sample data if available
            if relation.samples and len(relation.samples) > 0:
                sample = relation.samples[0]  # Show only one sample
                md.append(
                    f"  - Sample data: {sample.source_labels}- [:{sample.relation[1]}] -> {sample.target_labels}\n"
                )

        # Write the generated markdown to 'graph_schema.md'
        with open("config/graph_schema.md", "w", encoding="utf-8") as f:
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
                            prop_name = prop.split(":")[0].strip()
                            prop_type = (
                                prop.split(":")[1].strip() if ":" in prop else None
                            )
                            properties.append(
                                NodeProperty(name=prop_name, type=prop_type)
                            )
                        elif isinstance(prop, dict):
                            # Handle dict format {prop_name: prop_type}
                            for prop_name, prop_type in prop.items():
                                properties.append(
                                    NodeProperty(name=prop_name, type=str(prop_type))
                                )
                        else:
                            properties.append(NodeProperty(name=str(prop)))

            nodes.append(
                NodesInfo(
                    node_type=node_label, count=0, properties=properties, samples=None
                )
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
                    properties.append(
                        RelationshipProperty(name=prop_name, type=str(prop_type))
                    )

            relations.append(
                RelationsInfo(
                    relation_type=rel_type, count=0, properties=properties, samples=None
                )
            )

        # Parse indexes and constraints
        structured_indexes = []
        structured_constraints = []
        index_constraint_list = schema_data.get("indexes", [])

        for item in index_constraint_list:
            if isinstance(item, str):
                if "CONSTRAINT" in item.upper():
                    structured_constraints.append(
                        ConstraintInfo(name=item, type="unknown")
                    )
                elif "INDEX" in item.upper():
                    structured_indexes.append(IndexInfo(name=item, type="unknown"))
                else:
                    # Default to index if unclear
                    structured_indexes.append(IndexInfo(name=item, type="unknown"))

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
            constraints=structured_constraints,
            indexes=structured_indexes,
            guidelines=guidelines,
            examples=examples,
        )


if __name__ == "__main__":
    import os
    from src.core import Neo4jSchemaExtractor

    extractor = Neo4jSchemaExtractor(
        uri=os.getenv("NEO4J_URI"),
        database=os.getenv("NEO4J_DATABASE"),
        username=os.getenv("NEO4J_USER"),
        password=os.getenv("NEO4J_PASSWORD"),
    )

    # Extract structured schema for demonstration
    structured_schema = extractor.extract_structured_schema()
    if structured_schema:
        print(structured_schema.to_md())
    else:
        print("Failed to extract schema")
