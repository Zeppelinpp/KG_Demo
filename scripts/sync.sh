#!/bin/bash

set -e  # Exit on any error

echo "=== Starting sync process ==="

# Step 0: Initialize Milvus collections & Update business mapping
echo "Step 0: Initializing Milvus collections..."
uv run scripts/init_milvus.py
uv run scripts/update_business_mapping.py

# Step 1: Extract schema and write to config/graph_schema.md
echo "Step 1: Extracting schema and writing to config/graph_schema.md..."
uv run scripts/node_schema.py

# Step 2: Insert mapping data and test search
echo "Step 2: Inserting mapping data and testing search..."
uv run scripts/sync_mapping.py --insert true
uv run scripts/sync_mapping.py --search true

echo "=== Sync process completed successfully ==="
