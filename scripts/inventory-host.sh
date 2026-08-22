#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${1:-artifacts/inventory}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_FILE="${OUT_DIR}/host-${STAMP}.json"
mkdir -p "${OUT_DIR}"

json_escape() {
  python3 - <<'PY' "$1"
import json, sys
print(json.dumps(sys.argv[1]))
PY
}

command_exists() { command -v "$1" >/dev/null 2>&1; }

HOSTNAME_VALUE="$(hostname 2>/dev/null || echo unknown)"
OS_NAME="$(sw_vers -productName 2>/dev/null || uname -s)"
OS_VERSION="$(sw_vers -productVersion 2>/dev/null || uname -r)"
ARCH="$(uname -m)"
CHIP="$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo unknown)"
MEM_BYTES="$(sysctl -n hw.memsize 2>/dev/null || echo 0)"
MEM_GB="$(python3 - <<PY
b=int('${MEM_BYTES}' or 0)
print(round(b/1024/1024/1024, 2))
PY
)"

OLLAMA_PRESENT=false
OLLAMA_VERSION=""
OLLAMA_MODELS='[]'
if command_exists ollama; then
  OLLAMA_PRESENT=true
  OLLAMA_VERSION="$(ollama --version 2>&1 | head -n 1 | sed 's/"/\\"/g')"
  OLLAMA_MODELS="$(ollama list 2>/dev/null | python3 -c '
import sys,json
rows=[]
lines=[l.rstrip("\n") for l in sys.stdin]
for line in lines[1:]:
    if not line.strip(): continue
    parts=line.split()
    if len(parts) >= 4:
        rows.append({"name":parts[0],"id":parts[1],"size":" ".join(parts[2:4]),"modified":" ".join(parts[4:])})
print(json.dumps(rows))
')"
fi

MLX_PRESENT=false
MLX_VERSION=""
if python3 -c 'import mlx' >/dev/null 2>&1; then
  MLX_PRESENT=true
  MLX_VERSION="$(python3 -c 'import mlx; print(getattr(mlx,"__version__","unknown"))' 2>/dev/null || echo unknown)"
fi

MLX_LM_PRESENT=false
MLX_LM_VERSION=""
if python3 -c 'import mlx_lm' >/dev/null 2>&1; then
  MLX_LM_PRESENT=true
  MLX_LM_VERSION="$(python3 -c 'import importlib.metadata as m; print(m.version("mlx-lm"))' 2>/dev/null || echo unknown)"
fi

PYTHON_VERSION="$(python3 --version 2>&1 || true)"
GIT_VERSION="$(git --version 2>&1 || true)"

cat >"${OUT_FILE}" <<JSON
{
  "schema_version": 1,
  "captured_at_utc": "${STAMP}",
  "host": {
    "hostname": $(json_escape "${HOSTNAME_VALUE}"),
    "os": $(json_escape "${OS_NAME}"),
    "os_version": $(json_escape "${OS_VERSION}"),
    "architecture": $(json_escape "${ARCH}"),
    "chip": $(json_escape "${CHIP}"),
    "unified_memory_gb": ${MEM_GB}
  },
  "runtime": {
    "python": $(json_escape "${PYTHON_VERSION}"),
    "git": $(json_escape "${GIT_VERSION}"),
    "ollama": {
      "present": ${OLLAMA_PRESENT},
      "version": $(json_escape "${OLLAMA_VERSION}"),
      "models": ${OLLAMA_MODELS}
    },
    "mlx": {
      "present": ${MLX_PRESENT},
      "version": $(json_escape "${MLX_VERSION}"),
      "mlx_lm_present": ${MLX_LM_PRESENT},
      "mlx_lm_version": $(json_escape "${MLX_LM_VERSION}")
    }
  }
}
JSON

printf 'Inventory written to %s\n' "${OUT_FILE}"
