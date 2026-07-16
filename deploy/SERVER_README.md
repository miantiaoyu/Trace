# Trace 服务器运行包

本目录只包含 Trace 运行、Docker 构建和 XXL-JOB 调度所需文件，不包含测试、设计文档、调研报告、Git 元数据、本地日志或数据库密码。

## 准备配置

在 `docker-compose.yml` 同级目录单独放置：

- `prod-db.yml`：阿里正式 ERP 只读连接。
- `test-db.yml`：内网测试 `oms.headway` 写入连接。

这两个文件必须通过服务器密钥或公司配置流程提供，不进入压缩包和镜像。

## 构建与验证

```bash
docker-compose build
docker-compose run --rm trace --days 60 --limit 1 --summary-only
```

## XXL-JOB

XXL-JOB `SHELL` 任务调用：

```bash
/opt/trace/deploy/xxl-job/trace-test.sh
```

默认 wrapper 查询最近 60 天、不限数量并写入 `oms.headway`。正式调度前先使用 `--limit 1` 或 `--limit 20` 小批验证。
