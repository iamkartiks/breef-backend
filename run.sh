#!/bin/bash
# Run script for the API Gateway

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Set PYTHONPATH to include the backend directory
export PYTHONPATH="${SCRIPT_DIR}:${PYTHONPATH}"

# Change to api-gateway directory
cd "${SCRIPT_DIR}/api-gateway"

# Run the server
python main.py

