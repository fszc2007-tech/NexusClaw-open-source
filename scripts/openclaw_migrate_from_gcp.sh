#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "usage: $0 <instance-name> <zone> [remote-home]"
  exit 1
fi

INSTANCE_NAME="$1"
ZONE="$2"
REMOTE_HOME="${3:-\$HOME}"
LOCAL_OPENCLAW_HOME="${HOME}/.openclaw"
TMP_DIR="$(mktemp -d)"
ARCHIVE_PATH="${TMP_DIR}/openclaw-state.tgz"
REMOTE_ARCHIVE="/tmp/openclaw-state-$$.tgz"

cleanup() {
  rm -rf "${TMP_DIR}"
  gcloud compute ssh "${INSTANCE_NAME}" --zone "${ZONE}" --command "rm -f ${REMOTE_ARCHIVE}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

gcloud compute ssh "${INSTANCE_NAME}" --zone "${ZONE}" --command "tar -C ${REMOTE_HOME} -czf ${REMOTE_ARCHIVE} .openclaw"
gcloud compute scp --zone "${ZONE}" "${INSTANCE_NAME}:${REMOTE_ARCHIVE}" "${ARCHIVE_PATH}"

if [ -d "${LOCAL_OPENCLAW_HOME}" ]; then
  BACKUP_DIR="${HOME}/.openclaw.backup.$(date +%Y%m%d%H%M%S)"
  mv "${LOCAL_OPENCLAW_HOME}" "${BACKUP_DIR}"
  echo "existing local state backed up to ${BACKUP_DIR}"
fi

mkdir -p "${HOME}"
tar -C "${HOME}" -xzf "${ARCHIVE_PATH}"

echo "OpenClaw state restored to ${LOCAL_OPENCLAW_HOME}"
