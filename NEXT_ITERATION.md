# 下一迭代计划

## 当前状态

项目功能开发暂时冻结。当前代码继续使用阿里正式 ERP 只读源和内网测试 `oms.headway` 写入目标；未经单独评审不切换正式结果库。

## 恢复项目时的前置条件

- 确认公司 Linux 测试服务器、镜像仓库、CI/CD 平台和 XXL-JOB executor 归属。
- 由公司流程提供服务器上的 `prod-db.yml` 与 `test-db.yml`，不将凭证写入镜像或 Git。
- 如需写入正式 `oms`，先完成数据库账号、字段、权限、保留周期和回滚方案评审。

## 上线前待办

1. 使用 `tools/build_server_bundle.ps1` 生成 `dist/trace-server.zip`，只上传服务器运行包。
2. 在测试服务器重建镜像，先用 `--limit 1`、再用 `--limit 20` 验证源库只读、测试库写入、浏览器和 Xvfb。
3. 在 XXL-JOB 使用 `deploy/xxl-job/trace-test.sh` 调度一次，核对退出码、任务锁、脱敏日志和 `headway` 更新。
4. 观测 HMM 120 秒等待与 60–75 秒重试退避的恢复率；万海仍受 Incapsula 影响时保持失败重查，不绕过访问控制。
5. 测试运行稳定后，再决定 XXL-JOB 执行频率、单轮 `limit` 和正式目标库发布时间。

## 验收标准

- 服务器发布包不包含测试、开发文档、历史报告、Git 元数据、日志或真实数据库配置。
- ERP 源表保持只读；`--persist` 只对目标 `oms.headway` 执行受控 upsert。
- `query_failed` 到期后优先重查，成功后更新原记录并清除旧错误。
- Linux + Xvfb 能无人值守运行 HMM，单柜超时或页面变化不中断后续柜号。
- Docker/XXL-JOB 日志不包含柜号、官网原始响应或数据库凭证。
