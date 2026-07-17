# 数据库配置模板

本目录只提供无密码模板。实际部署时，请在 `/opt/trace` 单独放置：

- `prod-db.yml`：正式 ERP 只读配置。
- `test-db.yml`：测试 `oms.headway` 写入配置。
- `prod-oms.yml`：正式 `oms` 写入配置模板，正式上线审批通过后再填写。
- 其他目标库可以使用任意文件名，通过 `deploy/run-trace.sh --target-config <文件>` 指定。

真实配置不进入 Git、Docker 镜像或服务器发布包。
