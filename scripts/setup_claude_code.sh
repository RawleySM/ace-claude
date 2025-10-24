#!/usr/bin/env bash
# Environment bootstrap script for the Claude Code CLI.
#
# This script installs the Anthropic Claude Code CLI globally via npm,
# verifies prerequisite tooling, and performs a non-interactive login
# using the ANTHROPIC_API_KEY environment variable.

set -euo pipefail

if [[ "${DEBUG_STARTUP_SCRIPT:-}" == "1" ]]; then
  set -x
fi

command -v npm >/dev/null 2>&1 || {
  echo "[ERROR] npm is required but was not found in PATH." >&2
  exit 1
}

# Install or update the Claude Code CLI globally.
echo "Installing @anthropic-ai/claude-code globally via npm..."
npm install -g @anthropic-ai/claude-code

echo "Verifying claude-code CLI installation..."
command -v claude-code >/dev/null 2>&1 || {
  echo "[ERROR] claude-code CLI was not installed successfully." >&2
  exit 1
}

# Ensure the API key is available before attempting login.
if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "[ERROR] ANTHROPIC_API_KEY environment variable is not set." >&2
  exit 1
fi

# Perform a non-interactive login using the provided API key.
echo "Logging into claude-code using ANTHROPIC_API_KEY from environment..."
claude-code auth login --api-key "$ANTHROPIC_API_KEY"

echo "Claude Code environment is ready."
