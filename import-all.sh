#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# import-all.sh
# Imports all tools and the agent for the Course Content Simplification Agent
# into watsonx Orchestrate.
#
# Usage:
#   chmod +x import-all.sh
#   ./import-all.sh
#
# Prerequisites:
#   - `orchestrate` CLI installed and authenticated
#   - An active watsonx Orchestrate environment
# ─────────────────────────────────────────────────────────────────────────────

set -e

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

echo "=========================================="
echo " Course Content Simplification Agent"
echo " Import Script"
echo "=========================================="

# ── 1. Import Python tools ────────────────────────────────────────────────────
echo ""
echo ">> Importing Python tools..."
for tool_file in simplify_content_tool.py; do
  echo "   Importing tool: ${tool_file}"
  orchestrate tools import -k python -f "${SCRIPT_DIR}/tools/${tool_file}"
done

# ── 2. Import Flow tools ──────────────────────────────────────────────────────
echo ""
echo ">> Importing Flow tools..."
for flow_file in simplification_flow.py; do
  echo "   Importing flow: ${flow_file}"
  orchestrate tools import -k flow -f "${SCRIPT_DIR}/tools/${flow_file}"
done

# ── 3. Import Agent ───────────────────────────────────────────────────────────
echo ""
echo ">> Importing Agent..."
for agent_file in course_simplification_agent.yaml; do
  echo "   Importing agent: ${agent_file}"
  orchestrate agents import -f "${SCRIPT_DIR}/agents/${agent_file}"
done

echo ""
echo "=========================================="
echo " Import complete!"
echo " Run: orchestrate chat start"
echo " Then select: course_simplification_agent"
echo "=========================================="
