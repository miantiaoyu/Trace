#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${TRACE_PROJECT_DIR:-/opt/trace}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "请使用 root 用户安装 systemd 定时任务。" >&2
  exit 1
fi
if [[ "${PROJECT_DIR}" != "/opt/trace" ]]; then
  echo "当前 systemd unit 固定使用 /opt/trace，请将项目部署到该目录。" >&2
  exit 1
fi
for required_file in docker-compose.yml prod-db.yml test-db.yml deploy/run-trace.sh; do
  if [[ ! -f "${PROJECT_DIR}/${required_file}" ]]; then
    echo "缺少文件: ${PROJECT_DIR}/${required_file}" >&2
    exit 1
  fi
done

chmod 0755 "${PROJECT_DIR}/deploy/run-trace.sh"
install -m 0644 "${PROJECT_DIR}/deploy/systemd/trace.service" /etc/systemd/system/trace.service
install -m 0644 "${PROJECT_DIR}/deploy/systemd/trace.timer" /etc/systemd/system/trace.timer
if [[ ! -e "/etc/sysconfig/trace" ]]; then
  printf 'TRACE_DAYS=60\nTRACE_LIMIT=1\n' > /etc/sysconfig/trace
  chmod 0600 /etc/sysconfig/trace
fi
systemctl daemon-reload
systemctl enable trace.timer

echo "Trace systemd timer 已安装并设为开机启用，当前尚未启动。"
echo "当前默认只处理 1 条。完成 1 条和 20 条验证后，将 /etc/sysconfig/trace 的 TRACE_LIMIT 改为 0，再启动 trace.timer。"
