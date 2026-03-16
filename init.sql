-- K8s 发版平台数据库初始化脚本
-- 此脚本仅在 MySQL 首次启动时执行，用于创建表结构
-- 数据初始化请使用 backend/init_data.py

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id INTEGER NOT NULL AUTO_INCREMENT,
    username VARCHAR(64) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(128) NOT NULL,
    real_name VARCHAR(64),
    `role` ENUM('ADMIN','DEVELOPER','VIEWER','APPROVER'),
    status INTEGER,
    last_login_at DATETIME,
    created_at TIMESTAMP NULL DEFAULT (now()),
    updated_at TIMESTAMP NULL DEFAULT (now()),
    is_superuser BOOL DEFAULT FALSE,
    org_id INTEGER NULL,
    mfa_enabled BOOL DEFAULT FALSE,
    PRIMARY KEY (id),
    UNIQUE (email)
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 集群表
CREATE TABLE IF NOT EXISTS clusters (
    id INTEGER NOT NULL AUTO_INCREMENT,
    name VARCHAR(64) NOT NULL,
    display_name VARCHAR(128),
    api_server VARCHAR(255) NOT NULL,
    kubeconfig_encrypted TEXT,
    sa_token_encrypted TEXT,
    ca_cert TEXT,
    status INTEGER,
    description VARCHAR(255),
    created_at TIMESTAMP NULL DEFAULT (now()),
    updated_at TIMESTAMP NULL DEFAULT (now()),
    PRIMARY KEY (id),
    UNIQUE KEY ix_clusters_name (name)
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 命名空间表
CREATE TABLE IF NOT EXISTS namespaces (
    id INTEGER NOT NULL AUTO_INCREMENT,
    cluster_id INTEGER NOT NULL,
    name VARCHAR(64) NOT NULL,
    display_name VARCHAR(128),
    env_type ENUM('DEV','TEST','STAGING','PROD') NOT NULL,
    status INTEGER,
    description VARCHAR(255),
    created_at TIMESTAMP NULL DEFAULT (now()),
    updated_at TIMESTAMP NULL DEFAULT (now()),
    PRIMARY KEY (id),
    FOREIGN KEY(cluster_id) REFERENCES clusters (id) ON DELETE CASCADE
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 服务表
CREATE TABLE IF NOT EXISTS services (
    id INTEGER NOT NULL AUTO_INCREMENT,
    namespace_id INTEGER NOT NULL,
    name VARCHAR(64) NOT NULL,
    display_name VARCHAR(128),
    type ENUM('DEPLOYMENT','STATEFULSET'),
    deploy_name VARCHAR(128) NOT NULL,
    container_name VARCHAR(128),
    harbor_project VARCHAR(64),
    harbor_repo VARCHAR(128),
    current_image VARCHAR(255),
    port INTEGER,
    replicas INTEGER,
    resource_limits JSON,
    health_check_path VARCHAR(128),
    status INTEGER,
    description VARCHAR(255),
    created_at TIMESTAMP NULL DEFAULT (now()),
    updated_at TIMESTAMP NULL DEFAULT (now()),
    PRIMARY KEY (id),
    FOREIGN KEY(namespace_id) REFERENCES namespaces (id) ON DELETE CASCADE
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 发布记录表
CREATE TABLE IF NOT EXISTS release_records (
    id INTEGER NOT NULL AUTO_INCREMENT,
    service_id INTEGER NOT NULL,
    operator_id INTEGER NOT NULL,
    image_tag VARCHAR(128) NOT NULL,
    image_full_path VARCHAR(255),
    previous_image VARCHAR(255),
    status ENUM('PENDING','APPROVING','RUNNING','SUCCESS','FAILED','ROLLED_BACK'),
    strategy ENUM('ROLLING','RECREATE','CANARY'),
    message TEXT,
    pod_status JSON,
    logs TEXT,
    rollback_to INTEGER,
    approved_by INTEGER,
    approved_at DATETIME,
    started_at DATETIME,
    completed_at DATETIME,
    created_at TIMESTAMP NULL DEFAULT (now()),
    validity_period INTEGER NOT NULL DEFAULT 0,
    validity_start_at DATETIME,
    validity_end_at DATETIME,
    parent_release_id INTEGER,
    is_repeated INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    FOREIGN KEY(service_id) REFERENCES services (id),
    FOREIGN KEY(operator_id) REFERENCES users (id),
    FOREIGN KEY(rollback_to) REFERENCES release_records (id),
    FOREIGN KEY(approved_by) REFERENCES users (id),
    FOREIGN KEY(parent_release_id) REFERENCES release_records (id)
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 角色表
CREATE TABLE IF NOT EXISTS roles (
    id INTEGER NOT NULL AUTO_INCREMENT,
    name VARCHAR(64) NOT NULL,
    code VARCHAR(64) NOT NULL,
    description TEXT,
    role_type ENUM('SYSTEM','CUSTOM'),
    status INTEGER,
    created_at TIMESTAMP NULL DEFAULT (now()),
    updated_at TIMESTAMP NULL DEFAULT (now()),
    PRIMARY KEY (id),
    UNIQUE (code)
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 角色组表
CREATE TABLE IF NOT EXISTS role_groups (
    id INTEGER NOT NULL AUTO_INCREMENT,
    name VARCHAR(64) NOT NULL,
    code VARCHAR(64) NOT NULL,
    description TEXT,
    parent_id INTEGER,
    status INTEGER,
    created_at TIMESTAMP NULL DEFAULT (now()),
    updated_at TIMESTAMP NULL DEFAULT (now()),
    PRIMARY KEY (id),
    UNIQUE (code),
    FOREIGN KEY(parent_id) REFERENCES role_groups (id) ON DELETE SET NULL
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 权限表
CREATE TABLE IF NOT EXISTS permissions (
    id INTEGER NOT NULL AUTO_INCREMENT,
    user_id INTEGER NOT NULL,
    cluster_id INTEGER,
    namespace_id INTEGER,
    `role` ENUM('ADMIN','DEVELOPER','VIEWER','OPERATOR') NOT NULL,
    created_at TIMESTAMP NULL DEFAULT (now()),
    PRIMARY KEY (id),
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY(cluster_id) REFERENCES clusters (id) ON DELETE CASCADE,
    FOREIGN KEY(namespace_id) REFERENCES namespaces (id) ON DELETE CASCADE
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 审计日志表
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER NOT NULL AUTO_INCREMENT,
    user_id INTEGER,
    username VARCHAR(64),
    action VARCHAR(32) NOT NULL,
    resource_type VARCHAR(32) NOT NULL,
    resource_id INTEGER,
    resource_name VARCHAR(128),
    detail JSON,
    ip_addr VARCHAR(64),
    user_agent VARCHAR(255),
    created_at TIMESTAMP NULL DEFAULT (now()),
    PRIMARY KEY (id)
) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
