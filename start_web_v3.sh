#!/bin/bash

# Start the workflow v3 web application
echo "Starting Knowledge Graph Assistant V3..."
echo "The application will run on http://localhost:7688"
echo "Press Ctrl+C to stop the server"
echo ""

# Run the web app
uv run web_app_v3.py
