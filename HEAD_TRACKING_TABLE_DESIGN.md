# 头程追踪表设计草案

本文描述 `oms.headway` 的数据模型和查询流程；建表 SQL 位于 `sql/headway.sql`。

## 设计目标

- 以 ERP 人工生成且不重复的拼柜号（`PG+日期...`）为一个追踪对象，同一拼柜号下多个订单只查询一次。
- 保存船司本次成功查询得到的最新原始 JSON。
- 将业务最关心的字段提升为可直接筛选、排序和统计的列。
- 能区分新订单、尚未到达最终目的地的待追踪记录和已完成记录。
- 官网查询失败或解析失败时保留上一份有效业务快照，不用错误结果覆盖好数据。

## 记录粒度和身份

一行代表一个拼柜号的“当前追踪快照”。数据来自 `trobs.po_cabinet_combination`：

| 业务含义 | 来源字段 | 目标字段建议 |
| --- | --- | --- |
| 拼柜号 | `cabinet_combination_number` | `consolidation_no` |
| 船司原始值 | `shipping_company` | `erp_shipping_company` |
| 规范化船司 | 查询归一化结果 | `carrier_code` |
| 柜号 | `cabinet_no` | `container_no` |
| ERP 更新时间 | `update_time` | `erp_update_time` |
| ERP 创建时间 | `create_time` | `erp_create_time` |

建议唯一约束使用 `(environment, consolidation_no)`。同一拼柜号下的 ERP 行必须具有一致的柜号和船司；如果出现一个拼柜号对应多个柜号或多个船司，应作为 ERP 数据异常隔离，不能任意选择一条查询。

## 建议字段

### 标识和来源

| 字段 | 类型方向 | 说明 |
| --- | --- | --- |
| `id` | BIGINT 主键 | 头程追踪表自身主键 |
| `environment` | VARCHAR | `test` 或 `prod`，防止环境数据混用 |
| `consolidation_no` | VARCHAR | 拼柜号，头程记录的业务唯一标识 |
| `erp_order_count` | INT | 当前拼柜号关联的 ERP 订单/来源记录数量 |
| `erp_shipping_company` | VARCHAR | ERP 原始船司值，便于回溯 |
| `carrier_code` | VARCHAR | 统一船司代码，例如 `HMM`、`MAERSK` |
| `container_no` | VARCHAR | 清理空白并大写后的柜号 |
| `erp_update_time` | DATETIME | ERP 来源记录更新时间 |
| `erp_create_time` | DATETIME | ERP 来源记录创建时间 |

### 统一业务快照

| 字段 | 类型方向 | 说明 |
| --- | --- | --- |
| `departure_time` | DATETIME | 实际出发时间；没有实际事件时保持为空，不保存预计出发时间 |
| `origin_port` | VARCHAR | 头程起运港 |
| `destination_port` | VARCHAR | 头程最终卸船港，不是转运港或交付仓库 |
| `destination_eta` | DATETIME | 最终卸船港预计到达时间 |
| `current_event_time` | DATETIME | 当前状态对应的事件时间 |
| `current_status` | VARCHAR | 当前运输状态 |
| `current_location` | VARCHAR | 当前地点、码头或场站 |
| `current_mode` | VARCHAR | `Vessel`、`Truck`、`Rail` 等 |
| `vessel_name` | VARCHAR | 当前或下一相关船名 |
| `voyage` | VARCHAR | 当前或下一相关航次 |
| `imo` | VARCHAR | IMO 船舶编号，来源没有时为空 |
| `is_arrived_destination` | TINYINT(1) | 是否已在最终卸船港实际卸船，核心筛选字段 |
| `destination_arrived_at` | DATETIME | 最终卸船港实际卸船时间 |
| `destination_arrival_evidence` | VARCHAR | 判定依据，例如官网状态文本或事件名称 |

`is_arrived_destination` 只有在来源返回“最终卸船港实际卸船”的明确证据时才置为 `1`。转运港卸船不能置为 `1`；只有 ETA、目的港字段或预计事件时也必须保持 `0`。提柜、仓库交付和还空箱属于卸船后的业务，不是本表完成条件。

### 查询状态和原始数据

| 字段 | 类型方向 | 说明 |
| --- | --- | --- |
| `query_status` | VARCHAR | `success`、`partial_success`、`query_failed`、`route_unavailable` 等 |
| `query_route` | VARCHAR | 实际使用的船司路线 |
| `last_queried_at` | DATETIME | 最近一次尝试时间 |
| `last_success_at` | DATETIME | 最近一次取得官网原始数据的时间 |
| `next_query_at` | DATETIME | 下一次允许/计划查询时间，支持限速和失败退避 |
| `last_attempts` | INT | 最近一次查询尝试次数 |
| `last_error_type` | VARCHAR | 最近一次失败类型 |
| `last_error_message` | VARCHAR/TEXT | 脱敏后的失败信息，不保存密码、Cookie 或完整响应 |
| `raw_response_json` | JSON | 最近一次成功取得的船司原始 JSON |
| `normalized_schema_version` | VARCHAR | 统一摘要契约版本，当前为 `1.2` |
| `coverage_json` | JSON | 当前摘要覆盖情况，例如是否有 ETA、船舶、当前位置 |
| `created_at` | DATETIME | 头程记录首次创建时间 |
| `updated_at` | DATETIME | 头程记录最后更新时间 |

`raw_response_json` 只保存最新一次成功原始返回；`query_failed` 不应清空上一份有效原始数据和业务快照。本轮不设计查询历史表。

## 查询流程

每轮任务建议分两组取数：

1. **新拼柜号**：ERP 按拼柜号聚合后，头程表中不存在该拼柜号。
2. **未到达待追踪**：头程表已存在，`is_arrived_destination = 0`，并且 `next_query_at` 为空或已到期。

已到达记录默认不再重复查询。任务应允许人工或特殊参数强制重查，但不能让普通定时任务因为 ERP 更新时间变化而无限重复已完成记录。

查询成功后更新统一字段、`raw_response_json`、状态和时间；查询失败只更新失败元数据和下次重试时间；原始数据已取得但归一化失败时保存原始 JSON，统一字段保留上一份有效值并标记 `partial_success`。

## 索引建议

- 唯一索引：`environment + consolidation_no`
- 待追踪索引：`environment + is_arrived_destination + next_query_at`
- 船司批量索引：`environment + carrier_code + is_arrived_destination`
- 柜号查询索引：`environment + container_no`
- 运维查询索引：`environment + query_status + last_queried_at`

## 已确认决策

- ERP 拼柜号字段为 `cabinet_combination_number`，且人工保证不重复。
- 一个拼柜号应对应一个物理柜号和一个船司；不一致时作为 ERP 数据异常隔离。
- 正式表名为 `oms.headway`。
- 出发时间只保存实际值，原始 JSON 只保留最新一次，目的地按最终卸船港定义。
