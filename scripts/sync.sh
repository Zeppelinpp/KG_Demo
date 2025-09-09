#!/bin/bash

set -e  # Exit on any error

echo "=== Starting sync process ==="

# Step 0: Initialize Milvus collections
echo "Step 0: Initializing Milvus collections..."
uv run scripts/init_milvus.py

# Step 1: Extract schema and write to config/graph_schema.md
echo "Step 1: Extracting schema and writing to config/graph_schema.md..."
uv run scripts/extract_schema.py

# Step 2: Generate mapping using OpenAI API
echo "Step 2: Generating business mapping..."
uv run scripts/gen_mapping.py

# Step 3: Insert mapping data and test search
echo "Step 3: Inserting mapping data and testing search..."
uv run scripts/sync_milvus.py --insert true
uv run scripts/sync_milvus.py --search true

# Step 4: Extract and sync node schema
echo "Step 4: Extracting and syncing node schema..."
uv run scripts/node_schema.py

echo "=== Sync process completed successfully ==="
