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
if [[ -f "/etc/sysconfig/trace" ]]; then
  # shellcheck disable=SC1091
  source /etc/sysconfig/trace
fi
TRACE_DAYS="${TRACE_DAYS:-60}"
TRACE_LIMIT="${TRACE_LIMIT:-1}"
TRACE_SOURCE_CONFIG="${TRACE_SOURCE_CONFIG:-./prod-db.yml}"
TRACE_TARGET_CONFIG="${TRACE_TARGET_CONFIG:-./test-db.yml}"
if [[ ! -e "/etc/sysconfig/trace" ]]; then
  printf 'TRACE_DAYS=%s\nTRACE_LIMIT=%s\nTRACE_SOURCE_CONFIG=%s\nTRACE_TARGET_CONFIG=%s\n' \
    "${TRACE_DAYS}" "${TRACE_LIMIT}" "${TRACE_SOURCE_CONFIG}" "${TRACE_TARGET_CONFIG}" > /etc/sysconfig/trace
  chmod 0600 /etc/sysconfig/trace
fi

for required_file in docker-compose.yml deploy/run-trace.sh; do
  if [[ ! -f "${PROJECT_DIR}/${required_file}" ]]; then
    echo "缺少文件: ${PROJECT_DIR}/${required_file}" >&2
    exit 1
  fi
done
for config_file in "${TRACE_SOURCE_CONFIG}" "${TRACE_TARGET_CONFIG}"; do
  if [[ "${config_file}" = /* ]]; then
    resolved_config="${config_file}"
  else
    resolved_config="${PROJECT_DIR}/${config_file#./}"
  fi
  if [[ ! -f "${resolved_config}" ]]; then
    echo "缺少数据库配置: ${resolved_config}" >&2
    exit 1
  fi
done

chmod 0755 "${PROJECT_DIR}/deploy/run-trace.sh"
install -m 0644 "${PROJECT_DIR}/deploy/systemd/trace.service" /etc/systemd/system/trace.service
install -m 0644 "${PROJECT_DIR}/deploy/systemd/trace.timer" /etc/systemd/system/trace.timer
systemctl daemon-reload
systemctl enable trace.timer

echo "Trace systemd timer 已安装并设为开机启用，当前尚未启动。"
echo "当前默认只处理 1 条。完成 1 条和 20 条验证后，将 /etc/sysconfig/trace 的 TRACE_LIMIT 改为 0，再启动 trace.timer。"
