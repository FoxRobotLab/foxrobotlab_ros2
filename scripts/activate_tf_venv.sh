#!/usr/bin/env bash

# Source this file from any directory to activate the workspace TensorFlow venv
# and expose NVIDIA pip-package libraries to TensorFlow.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
VENV_DIR="${WORKSPACE_DIR}/.venv"

if [ ! -f "${VENV_DIR}/bin/activate" ]; then
  echo "TensorFlow venv not found at ${VENV_DIR}" >&2
  return 1 2>/dev/null || exit 1
fi

source "${VENV_DIR}/bin/activate"

NVIDIA_LIBRARY_PATH="$(
  find "${VENV_DIR}" -name "*.so*" 2>/dev/null \
    | grep "/nvidia/" \
    | xargs -r dirname \
    | sort -u \
    | paste -d ":" -s -
)"

if [ -n "${NVIDIA_LIBRARY_PATH}" ]; then
  export LD_LIBRARY_PATH="${NVIDIA_LIBRARY_PATH}:${LD_LIBRARY_PATH}"
fi

echo "Activated ${VENV_DIR}"
