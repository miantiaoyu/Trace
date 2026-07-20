# Trace 服务器运行包

本目录只包含 Trace 运行、Docker 构建和 systemd 定时调度所需文件，不包含测试、设计文档、调研报告、Git 元数据、本地日志或数据库密码。

## 准备配置

默认测试运行时，在 `/opt/trace` 单独放置：

- `prod-db.yml`：阿里正式 ERP 只读连接。
- `test-db.yml`：内网测试 `oms.headway` 写入连接。

这两个文件必须通过服务器密钥或公司配置流程提供，不进入压缩包和镜像。

正式写库时，仍保留 `prod-db.yml` 作为正式 ERP 只读配置，并额外放置审批后的 `prod-oms.yml`；将 `/etc/sysconfig/trace` 的 `TRACE_TARGET_CONFIG` 改为 `./prod-oms.yml` 即可，不需要改代码或重建镜像。

发布包中的 `config/*.yml.example` 是无密码模板。默认文件名无需设置变量；如果要指定其他写入库配置，可直接执行：

```bash
bash deploy/run-trace.sh --target-config prod-oms.yml
```

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

全量任务会按船司分组并复用浏览器会话。默认间隔为普通 HTTP 30 秒、DOM 浏览器 60 秒、完整浏览器 90 秒、万海/HMM 120 秒，因此运行数小时属于正常现象；不要为了提速启动并发任务。任务锁会阻止上一轮未结束时再次运行。

如果启动 timer 时当天凌晨 2 点已经过去，`Persistent=true` 可能立即补跑一次，这是预期行为。

修改 timer 时间后执行：

```bash
systemctl daemon-reload
systemctl restart trace.timer
```
