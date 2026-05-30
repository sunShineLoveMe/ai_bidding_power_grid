#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export BUILD_COMMIT="${BUILD_COMMIT:-$(git rev-parse --short=12 HEAD 2>/dev/null || echo unknown)}"
export BUILD_BRANCH="${BUILD_BRANCH:-$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)}"
export BUILD_TIME="${BUILD_TIME:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
export BUILD_ID="${BUILD_ID:-$(date -u +%Y%m%d%H%M%S)-${BUILD_COMMIT}}"

echo "building frontend image: BUILD_ID=$BUILD_ID BUILD_COMMIT=$BUILD_COMMIT BUILD_BRANCH=$BUILD_BRANCH"
docker compose build frontend
