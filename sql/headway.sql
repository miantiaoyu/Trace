-- 头程追踪当前快照表
-- 目标数据库：oms
-- 每个 environment + consolidation_no 只保留一条最新快照。

CREATE TABLE IF NOT EXISTS `oms`.`headway` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '头程追踪记录自增主键',
    `environment` VARCHAR(16) NOT NULL COMMENT '数据所属环境，当前联调固定为 test',
    `consolidation_no` VARCHAR(64) NOT NULL COMMENT 'ERP 拼柜号，同一环境下的业务唯一标识',
    `erp_order_count` INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '该拼柜号关联的 ERP 订单或来源记录数',
    `erp_shipping_company` VARCHAR(128) NOT NULL COMMENT 'ERP 中的船司原始值',
    `carrier_code` VARCHAR(32) NOT NULL COMMENT '归一化船司代码，例如 HMM、MAERSK',
    `container_no` VARCHAR(32) NOT NULL COMMENT '清理空白并转大写后的 ISO 6346 柜号',
    `erp_update_time` DATETIME NULL COMMENT 'ERP 来源记录的最新更新时间',
    `erp_create_time` DATETIME NULL COMMENT 'ERP 来源记录的创建时间',

    `departure_time` DATETIME NULL COMMENT '头程实际出发时间，不保存预计出发时间',
    `origin_port` VARCHAR(255) NULL COMMENT '头程起运港',
    `destination_port` VARCHAR(255) NULL COMMENT '最终卸船港，不是中转港或交付仓库',
    `destination_eta` DATETIME NULL COMMENT '预计到达最终卸船港的时间',
    `current_event_time` DATETIME NULL COMMENT '当前运输状态对应的事件时间',
    `current_status` VARCHAR(255) NULL COMMENT '归一化后的当前运输状态',
    `current_location` VARCHAR(255) NULL COMMENT '当前所在地点、码头或场站',
    `current_mode` VARCHAR(64) NULL COMMENT '当前事件的运输方式，例如 Vessel、Truck、Rail',
    `vessel_name` VARCHAR(255) NULL COMMENT '当前或下一相关船名',
    `voyage` VARCHAR(64) NULL COMMENT '当前或下一相关航次',
    `imo` VARCHAR(32) NULL COMMENT '国际海事组织船舶编号',
    `is_arrived_destination` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已在最终卸船港实际卸船：0 否，1 是',
    `destination_arrived_at` DATETIME NULL COMMENT '在最终卸船港实际卸船的时间',
    `destination_arrival_evidence` VARCHAR(255) NULL COMMENT '判定已在最终卸船港卸船的官网事件或状态依据',

    `query_status` VARCHAR(32) NOT NULL DEFAULT 'pending' COMMENT '最近查询状态，例如 success、partial_success、query_failed',
    `query_route` VARCHAR(128) NULL COMMENT '最近查询实际使用的船司适配路线',
    `last_queried_at` DATETIME NULL COMMENT '最近一次尝试查询船司官网的时间',
    `last_success_at` DATETIME NULL COMMENT '最近一次取得船司原始数据的时间',
    `next_query_at` DATETIME NULL COMMENT '下一次允许或计划查询的时间',
    `last_attempts` INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '最近一轮查询的尝试次数',
    `last_error_type` VARCHAR(128) NULL COMMENT '最近一次查询失败的错误类型',
    `last_error_message` TEXT NULL COMMENT '最近一次查询失败的脱敏错误摘要',
    `raw_response_json` JSON NULL COMMENT '最近一次成功取得的船司原始响应 JSON',
    `normalized_schema_version` VARCHAR(16) NULL COMMENT '归一化摘要的数据契约版本',
    `coverage_json` JSON NULL COMMENT '归一化字段覆盖情况 JSON，例如 ETA、船舶、当前位置',

    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '本条头程记录首次创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '本条头程记录最近更新时间',

    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_headway_environment_pg` (`environment`, `consolidation_no`),
    KEY `idx_headway_pending` (`environment`, `is_arrived_destination`, `next_query_at`),
    KEY `idx_headway_carrier_pending` (`environment`, `carrier_code`, `is_arrived_destination`),
    KEY `idx_headway_container` (`environment`, `container_no`),
    KEY `idx_headway_status_time` (`environment`, `query_status`, `last_queried_at`)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_unicode_ci
  COMMENT = '头程船运轨迹当前快照，每个环境和拼柜号保留一条记录';
