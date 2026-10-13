#!/usr/bin/env bash
# Install pinned VictoriaMetrics single-node binary + user systemd unit.
# No Docker, no spending. Binds 127.0.0.1:8428 only. Data lives under
# ~/.local/share/victoriametrics with 400d retention (see victoriametrics.service).
set -euo pipefail

VERSION="${VM_VERSION:-v1.154.0}"
BASE="https://github.com/VictoriaMetrics/VictoriaMetrics/releases/download/${VERSION}"
TARBALL="victoria-metrics-linux-amd64-${VERSION}.tar.gz"
SUMS="victoria-metrics-linux-amd64-${VERSION}_checksums.txt"

BIN_DIR="${HOME}/.local/bin"
DATA_DIR="${HOME}/.local/share/victoriametrics"
UNIT_DIR="${HOME}/.config/systemd/user"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

mkdir -p "${BIN_DIR}" "${DATA_DIR}"
chmod 700 "${DATA_DIR}"

cd "${WORK}"
curl -fsSL --retry 3 -O "${BASE}/${TARBALL}"
curl -fsSL --retry 3 -O "${BASE}/${SUMS}"
grep "  ${TARBALL}$" "${SUMS}" | sha256sum -c -
tar -xzf "${TARBALL}" victoria-metrics-prod
install -m 755 victoria-metrics-prod "${BIN_DIR}/victoria-metrics"

install -m 644 "${SCRIPT_DIR}/victoriametrics.service" "${UNIT_DIR}/victoriametrics.service"

systemctl --user daemon-reload
systemctl --user enable --now victoriametrics.service

echo "installed ${BIN_DIR}/victoria-metrics ($("${BIN_DIR}/victoria-metrics" --version 2>&1 | head -1))"
systemctl --user is-active victoriametrics.service
curl -fsS --max-time 10 http://127.0.0.1:8428/health | head -c 200; echo
