# Trace 服务器运行包

本目录只包含 Trace 运行、Docker 构建和 systemd 定时调度所需文件，不包含测试、设计文档、调研报告、Git 元数据、本地日志或数据库密码。

## 准备配置

在 `/opt/trace` 单独放置：

- `prod-db.yml`：阿里正式 ERP 只读连接。
- `test-db.yml`：内网测试 `oms.headway` 写入连接。

这两个文件必须通过服务器密钥或公司配置流程提供，不进入压缩包和镜像。

## 构建与小批验证

```bash
cd /opt/trace
docker-compose build
docker-compose run --rm trace --days 60 --limit 1 --summary-only
docker-compose run --rm trace --days 60 --limit 1 --summary-only --persist
```

第一条只查询不写库；确认正常后，第二条才写入测试 `oms.headway`。

## 安装 systemd 定时任务

```bash
cd /opt/trace
bash deploy/install-systemd.sh
```

默认每天凌晨 2 点触发；服务器停机错过后会在恢复时补跑。安装脚本只注册 timer 并设为开机启用，不会立即启动。首次安装会创建安全默认值 `TRACE_LIMIT=1`，可先手动验证：

```bash
systemctl start trace.service
systemctl status trace.service --no-pager
journalctl -u trace.service -n 100 --no-pager
```

确认 1 条正常后，改为 20 条再执行一次：

```bash
sed -i 's/^TRACE_LIMIT=.*/TRACE_LIMIT=20/' /etc/sysconfig/trace
grep '^TRACE_' /etc/sysconfig/trace
systemctl start trace.service
```

两轮验证完成后，把 `TRACE_LIMIT` 改为 `0`（不限制数量），再启动定时器：

```bash
sed -i 's/^TRACE_LIMIT=.*/TRACE_LIMIT=0/' /etc/sysconfig/trace
grep '^TRACE_' /etc/sysconfig/trace
systemctl start trace.timer
systemctl list-timers trace.timer --no-pager
```

如果启动 timer 时当天凌晨 2 点已经过去，`Persistent=true` 可能立即补跑一次，这是预期行为。

修改 timer 时间后执行：

```bash
systemctl daemon-reload
systemctl restart trace.timer
```
