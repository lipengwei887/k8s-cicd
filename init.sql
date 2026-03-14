-- K8s 发版平台数据库初始化脚本
-- 执行前请确保已创建数据库: CREATE DATABASE k8s_release DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 用户表
CREATE TABLE users (
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
    is_superuser BOOL,
    PRIMARY KEY (id),
    UNIQUE (email)
);

-- 集群表
CREATE TABLE clusters (
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
    PRIMARY KEY (id)
);

-- 命名空间表
CREATE TABLE namespaces (
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
);

-- 服务表
CREATE TABLE services (
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
);

-- 发布记录表
CREATE TABLE release_records (
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
);

-- 角色表
CREATE TABLE roles (
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
);

-- 角色组表
CREATE TABLE role_groups (
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
);

-- 权限表
CREATE TABLE permissions (
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
);

-- 审计日志表
CREATE TABLE audit_logs (
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
);

-- 插入默认管理员用户 (密码: Pass#1234)
INSERT INTO users (username, password_hash, email, real_name, `role`, status, is_superuser) VALUES
('lipengwei', '$2b$12$hIAuN2qP.s.wEvjZAyuWceDAFyOJgYHkX0NNumnBoqLXiCmBKwSx2', 'lipengwei@example.com', '管理员', 'ADMIN', 1, 1);

-- 插入默认角色
INSERT INTO roles (name, code, description, role_type, status) VALUES
('超级管理员', 'superadmin', '系统超级管理员', 'SYSTEM', 1),
('管理员', 'admin', '系统管理员', 'SYSTEM', 1),
('开发者', 'developer', '开发人员', 'SYSTEM', 1),
('审批者', 'approver', '发布审批人员', 'SYSTEM', 1),
('观察者', 'viewer', '只读用户', 'SYSTEM', 1);
