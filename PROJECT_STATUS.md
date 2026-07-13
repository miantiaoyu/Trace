# 项目状态

## 项目定位

Trace 当前是一个用于验证船司 Track & Trace API 的最小探测工具。第一版只做三件事：读取公司只读库中的船司和柜号，调用试点船司的官方追踪 API，打印原始 JSON 返回。

## 当前功能

- 新增 `crawler_lab/browser_dom_probe.py`：通过官方 URL 参数读取 COSCO 与 ONE 的结构化 DOM 事件表，并校验柜号回显和页面结果契约。
- 新增 `PROJECT_EXPERIENCE.md`，维护船司路径发现、DOM Provider 容错和排查结论。
- 已验证 SM Line（SML）公开柜号查询：通过临时 `JSESSIONID` 会话可获取状态、船期和轨迹明细原始 JSON。
- 新增 `crawler_lab/sm_line_probe.py`，按官网页面定义的会话和请求顺序进行低频查询。
- 已验证阳明海运（YML）官网公开查询接口：可用柜号直接获取原始 JSON，无需 API 凭证。
- 新增 `crawler_lab/yang_ming_probe.py`，调用
  `https://www.yangming.com/api/CargoTracking/GetTracking` 并打印 `ctStatusInfo` 和
  `dcsaStatusInfo` 原始返回。

- 支持从根目录 `prod-db.yml` 读取公司只读库连接配置。
- 支持从 `trobs.po_cabinet_combination` 读取最近更新的试点船司柜号。
- 支持试点船司字段归一化：
  - Maersk：`MSK`、`MSK 马士基`、`MSK马士基`、`MSK 马士基 BCO`、`MSK 马士基 NVO`
  - CMA CGM：`CMA`、`CMA 达飞`、`CMA达飞`
  - MSC：`MSC`、`MSC 地中海`、`MSC地中海`
- 支持命令行手动传入柜号，跳过数据库取样本。
- 支持 Maersk、CMA CGM、MSC 三家 Provider 骨架。
- 缺少 API 凭证时会明确提示，不爬网页、不伪造返回、不写数据库。
- 新增 `crawler_lab/` 实验目录，用于验证爬虫和网页自动化路线。
- 已验证维运网公开页面可用纯 HTTP 读取，并能从前端 JS 中抽取接口线索。
- 已验证维运网公开 API 可返回船司来源表、柜号格式识别结果和船司官网跳转链接。

## 技术栈与运行方式

- Python 命令行工具。
- 运行依赖：`PyMySQL`。
- 测试使用 Python 标准库 `unittest`。
- 目标运行环境：用户本机 Conda `py312` 环境。

## 关键目录/文件

- `trace_api_probe/`：命令行工具源码。
- `crawler_lab/`：爬虫与网页自动化实验脚本。
- `tests/`：单元测试。
- `requirements.txt`：运行依赖。
- `.gitignore`：忽略本地敏感配置和 Python 缓存。
- `prod-db.yml`：本地只读数据库配置文件，必须只读使用，不提交。

## 当前限制

- 当前没有船司 API 凭证，因此还不能看到真实 API 返回。
- API 地址和认证头已做成可配置；拿到船司凭证后可能仍需按官方开通信息微调环境变量。
- 第一版不做可视化、不落库、不保存 JSON 文件、不解析或标准化 API 返回。
- 第一版只支持 Maersk、CMA CGM、MSC 三家试点。
- 维运网目前只验证到“识别/跳转链接生成”，未直接返回集装箱轨迹事件。

## 已知风险

- 官方船司 API 的实际认证方式可能因开通账号而异。
- 当前实现不会抓取船司网页，未开通 API 的船司不会有返回。
- `prod-db.yml` 包含敏感信息，应只保留在本地并由 `.gitignore` 排除。

## 给下一个模型的快速上下文

运行前先安装依赖，然后使用 `python -m trace_api_probe --carrier MAERSK` 这类命令验证。没有 API 凭证时，命令会先从只读库取到柜号，然后在调用 API 前停止并提示缺少的环境变量。
