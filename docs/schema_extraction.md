# Neo4j Schema Extraction Documentation

This document explains the intermediate results and data structures used during Neo4j schema extraction in the KG_Demo project.

## Overview

The schema extraction process is handled by the `Neo4jSchemaExtractor` class in `core.py`, which systematically discovers and validates the structure of a Neo4j knowledge graph. The extraction produces comprehensive metadata about nodes, relationships, constraints, and indexes.

## Extraction Process Flow

```
1. Connect to Neo4j Database
2. Extract Node Labels and Properties
3. Extract Relationship Types and Properties  
4. Extract Database Constraints and Indexes
5. Validate Schema Structure
6. Export to JSON/YAML
```

## Data Structures and Intermediate Results

### 1. Node Schema Extraction

#### Cypher Queries Used

**Get all node labels:**
```cypher
CALL db.labels()
```

**Get node properties for a specific label:**
```cypher
MATCH (n:`{node_type}`)
UNWIND keys(n) AS prop
RETURN DISTINCT prop
```

**Get node count:**
```cypher
MATCH (n:`{label}`) RETURN COUNT(n) as count
```

**Get sample nodes:**
```cypher
MATCH (n:`{label}`) RETURN n LIMIT 3
```

#### Data Structure: `NodesInfo`

```python
class NodesInfo(BaseModel):
    count: int                           # Total number of nodes with this label
    properties: List[NodeProperty]       # List of all properties found on nodes
    samples: Optional[List[NodeSample]]  # Sample node data (up to 3 examples)
    node_type: Optional[str]            # Node label name
```

#### Intermediate Result Example

```json
{
  "Person": {
    "count": 1250,
    "properties": [
      {"name": "id", "type": "string"},
      {"name": "name", "type": "string"},
      {"name": "age", "type": "integer"},
      {"name": "created_at", "type": "datetime"}
    ],
    "samples": [
      {"properties": {"id": "p001", "name": "John Doe", "age": 30}},
      {"properties": {"id": "p002", "name": "Jane Smith", "age": 25}}
    ]
  }
}
```

**Attributes Meaning:**
- `count`: Total instances of this node type in the database
- `properties`: All unique property keys found across all nodes of this type
- `samples`: Concrete examples showing actual data structure and values
- `node_type`: The Neo4j label used to identify this node type

### 2. Relationship Schema Extraction

#### Cypher Queries Used

**Get all relationship types:**
```cypher
CALL db.relationshipTypes()
```

**Get relationship properties:**
```cypher
MATCH (n)-[r:`{relation_type}`]-(m)
UNWIND keys(r) AS prop
RETURN DISTINCT prop
```

**Get relationship count:**
```cypher
MATCH ()-[r:`{relation_type}`]-()
RETURN COUNT(r) as count
```

**Get relationship patterns (source/target node types):**
```cypher
MATCH (source)-[r:`{relation_type}`]-(target)
RETURN DISTINCT labels(source) as source_labels, labels(target) as target_labels, COUNT(*) as frequency
ORDER BY frequency DESC
LIMIT 10
```

**Get sample relationships:**
```cypher
MATCH (source)-[r:`{relation_type}`]-(target)
RETURN labels(source) as source_labels, labels(target) as target_labels, r as relationship
LIMIT 2
```

#### Data Structure: `RelationsInfo`

```python
class RelationsInfo(BaseModel):
    count: int                                    # Total number of relationships of this type
    properties: List[RelationshipProperty]       # Properties found on relationships
    patterns: Optional[List[RelationshipPattern]] # Source-target node patterns
    samples: Optional[List[RelationshipSample]]  # Sample relationship data
    relation_type: Optional[str]                 # Relationship type name
```

#### Intermediate Result Example

```json
{
  "KNOWS": {
    "count": 3420,
    "properties": [
      {"name": "since", "type": "datetime"},
      {"name": "strength", "type": "float"}
    ],
    "patterns": [
      {
        "source_labels": ["Person"],
        "target_labels": ["Person"],
        "frequency": 3420
      }
    ],
    "samples": [
      {
        "source_labels": ["Person"],
        "target_labels": ["Person"],
        "properties": {"since": "2020-01-15", "strength": 0.8}
      }
    ]
  }
}
```

**Attributes Meaning:**
- `count`: Total number of relationships of this type in the database
- `properties`: All unique property keys found on relationships of this type
- `patterns`: Shows which node types are connected by this relationship and how frequently
- `samples`: Concrete examples of actual relationships with their properties
- `relation_type`: The Neo4j relationship type name

### 3. Database Constraints and Indexes

#### Cypher Queries Used

**Get constraints (Neo4j 4.0+):**
```cypher
SHOW CONSTRAINTS
```

**Get constraints (older versions):**
```cypher
CALL db.constraints()
```

**Get indexes (Neo4j 4.0+):**
```cypher
SHOW INDEXES
```

**Get indexes (older versions):**
```cypher
CALL db.indexes()
```

#### Data Structures

```python
class IndexInfo(BaseModel):
    name: Optional[str]              # Index name
    type: Optional[str]              # Index type (BTREE, FULLTEXT, etc.)
    labelsOrTypes: Optional[List[str]] # Node labels or relationship types
    properties: Optional[List[str]]   # Properties covered by index
    state: Optional[str]             # Index state (ONLINE, FAILED, etc.)
    uniqueness: Optional[str]        # UNIQUE or NONUNIQUE

class ConstraintInfo(BaseModel):
    name: Optional[str]              # Constraint name
    type: Optional[str]              # Constraint type (UNIQUENESS, EXISTENCE, etc.)
    labelsOrTypes: Optional[List[str]] # Node labels or relationship types
    properties: Optional[List[str]]   # Properties covered by constraint
```

#### Intermediate Result Example

```json
{
  "indexes": [
    {
      "name": "person_id_index",
      "type": "BTREE",
      "labelsOrTypes": ["Person"],
      "properties": ["id"],
      "state": "ONLINE",
      "uniqueness": "UNIQUE"
    }
  ],
  "constraints": [
    {
      "name": "person_id_unique",
      "type": "UNIQUENESS",
      "labelsOrTypes": ["Person"],
      "properties": ["id"]
    }
  ]
}
```

### 4. Complete Schema Structure

#### Final Data Structure: `ExtractedGraphSchema`

```python
class ExtractedGraphSchema(BaseModel):
    database_info: DatabaseInfo                  # Connection and extraction metadata
    nodes: Dict[str, Dict[str, Any]]            # All node type information
    relationships: Dict[str, Dict[str, Any]]     # All relationship type information
    constraints: List[Dict[str, Any]]           # Database constraints
    indexes: List[Dict[str, Any]]               # Database indexes
```

#### Complete Example

```json
{
  "database_info": {
    "uri": "bolt://localhost:7687",
    "database": "neo4j",
    "extraction_time": "2024-01-15T10:30:00"
  },
  "nodes": {
    "Person": { /* Node schema as shown above */ },
    "Company": { /* Another node type */ }
  },
  "relationships": {
    "KNOWS": { /* Relationship schema as shown above */ },
    "WORKS_FOR": { /* Another relationship type */ }
  },
  "constraints": [ /* Constraint list */ ],
  "indexes": [ /* Index list */ ]
}
```

## Schema Validation

The extraction process includes validation using Pydantic models to ensure data integrity:

1. **Structure Validation**: Ensures all required fields are present
2. **Type Validation**: Validates data types match expected schemas
3. **Constraint Validation**: Checks that constraints and indexes are properly formatted
4. **Sample Data Validation**: Ensures sample data matches expected patterns

## Export Formats

### JSON Format
Raw extraction data preserved as-is for programmatic use.

### YAML Format
Converted to a more human-readable format suitable for configuration:

```yaml
schema:
  nodeLabels:
    - Person
    - Company
  relationships:
    - type: KNOWS
      from: Person
      to: Person
      properties:
        since: datetime
        strength: float
  nodeProperties:
    Person:
      - id: string
      - name: string
      - age: integer
  indexes:
    - "INDEX ON :Person(id)"
```

## Usage in Application

The extracted schema is used by:

1. **FunctionCallingAgent**: Provides context for Cypher query generation
2. **Query Validation**: Ensures generated queries reference valid nodes/relationships
3. **Type Inference**: Helps determine appropriate data types for query parameters
4. **Documentation Generation**: Creates human-readable schema documentation

## Error Handling

The extraction process handles various error scenarios:

- **Connection Failures**: Graceful handling of database connectivity issues
- **Permission Errors**: Handles cases where user lacks schema access privileges
- **Version Compatibility**: Supports different Neo4j versions with fallback queries
- **Malformed Data**: Validates and sanitizes extracted data before processing
