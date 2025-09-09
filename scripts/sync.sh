#!/bin/bash

set -e  # Exit on any error

echo "=== Starting sync process ==="

# Step 1: Extract schema and write to config/graph_schema.md
echo "Step 1: Extracting schema and writing to config/graph_schema.md..."
uv run scripts/extract_schema.py

# Step 2: Generate mapping using OpenAI API
echo "Step 2: Generating business mapping..."
uv run scripts/gen_mapping.py

# Step 4: Create Milvus collection
echo "Step 4: Creating Milvus collection..."
uv run src/storage/milvus_db.py --collection_name mapping

# Step 5: Insert data and test search
echo "Step 5: Inserting data and testing search..."
uv run scripts/sync_milvus.py --insert true
uv run scripts/sync_milvus.py --search true

echo "=== Sync process completed successfully ==="
