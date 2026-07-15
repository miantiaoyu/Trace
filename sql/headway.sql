-- 头程追踪当前快照表
-- 目标数据库：oms
-- 每个 environment + consolidation_no 只保留一条最新快照。

CREATE TABLE IF NOT EXISTS `oms`.`headway` (
    `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `environment` VARCHAR(16) NOT NULL,
    `consolidation_no` VARCHAR(64) NOT NULL,
    `erp_order_count` INT UNSIGNED NOT NULL DEFAULT 0,
    `erp_shipping_company` VARCHAR(128) NOT NULL,
    `carrier_code` VARCHAR(32) NOT NULL,
    `container_no` VARCHAR(32) NOT NULL,
    `erp_update_time` DATETIME NULL,
    `erp_create_time` DATETIME NULL,

    `departure_time` DATETIME NULL,
    `origin_port` VARCHAR(255) NULL,
    `destination_port` VARCHAR(255) NULL,
    `destination_eta` DATETIME NULL,
    `current_event_time` DATETIME NULL,
    `current_status` VARCHAR(255) NULL,
    `current_location` VARCHAR(255) NULL,
    `current_mode` VARCHAR(64) NULL,
    `vessel_name` VARCHAR(255) NULL,
    `voyage` VARCHAR(64) NULL,
    `imo` VARCHAR(32) NULL,
    `is_arrived_destination` TINYINT(1) NOT NULL DEFAULT 0,
    `destination_arrived_at` DATETIME NULL,
    `destination_arrival_evidence` VARCHAR(255) NULL,

    `query_status` VARCHAR(32) NOT NULL DEFAULT 'pending',
    `query_route` VARCHAR(128) NULL,
    `last_queried_at` DATETIME NULL,
    `last_success_at` DATETIME NULL,
    `next_query_at` DATETIME NULL,
    `last_attempts` INT UNSIGNED NOT NULL DEFAULT 0,
    `last_error_type` VARCHAR(128) NULL,
    `last_error_message` TEXT NULL,
    `raw_response_json` JSON NULL,
    `normalized_schema_version` VARCHAR(16) NULL,
    `coverage_json` JSON NULL,

    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_headway_environment_pg` (`environment`, `consolidation_no`),
    KEY `idx_headway_pending` (`environment`, `is_arrived_destination`, `next_query_at`),
    KEY `idx_headway_carrier_pending` (`environment`, `carrier_code`, `is_arrived_destination`),
    KEY `idx_headway_container` (`environment`, `container_no`),
    KEY `idx_headway_status_time` (`environment`, `query_status`, `last_queried_at`)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;
