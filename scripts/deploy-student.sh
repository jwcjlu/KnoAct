#!/usr/bin/env bash
# Deploy KnoAct student-app Docker image on a Linux server.
# Prerequisite: docker load -i knoact-student-app-<tag>.tar

set -euo pipefail

BACKEND_CONTAINER="${BACKEND_CONTAINER:-knoact-backend-1}"
STUDENT_CONTAINER="${STUDENT_CONTAINER:-knoact-student}"
STUDENT_PORT="${STUDENT_PORT:-8082}"

# ── Resolve backend ───────────────────────────────────────────────────
if ! docker inspect "$BACKEND_CONTAINER" &>/dev/null; then
    echo "ERROR: backend container '$BACKEND_CONTAINER' not found" >&2
    echo "Set BACKEND_CONTAINER env var if it has a different name." >&2
    exit 1
fi

NET=$(docker inspect "$BACKEND_CONTAINER" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}')
IP=$(docker inspect "$BACKEND_CONTAINER" --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')

echo "Backend: $BACKEND_CONTAINER (network=$NET, ip=$IP)"

# ── Remove old student container if any ───────────────────────────────
if docker inspect "$STUDENT_CONTAINER" &>/dev/null; then
    echo "Removing old container: $STUDENT_CONTAINER"
    docker rm -f "$STUDENT_CONTAINER" >/dev/null
fi

# ── Run ───────────────────────────────────────────────────────────────
docker run -d \
    --name "$STUDENT_CONTAINER" \
    -p "${STUDENT_PORT}:80" \
    --network "$NET" \
    --add-host "backend:$IP" \
    knoact-student-app:latest

echo ""
echo "Student app running on http://localhost:$STUDENT_PORT"
echo "Check: docker ps --filter name=$STUDENT_CONTAINER"