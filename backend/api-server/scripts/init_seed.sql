CREATE DATABASE IF NOT EXISTS nexusclaw CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE nexusclaw;

CREATE TABLE IF NOT EXISTS projects (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  project_key VARCHAR(64) NOT NULL UNIQUE,
  name VARCHAR(128) NOT NULL,
  description TEXT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS project_persona (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  project_id BIGINT NOT NULL UNIQUE,
  assistant_name VARCHAR(64) NOT NULL DEFAULT 'NexusClaw',
  assistant_role VARCHAR(128) NOT NULL DEFAULT '稅務問答助手',
  system_prompt TEXT NULL,
  style_rules TEXT NULL,
  opening_text TEXT NULL,
  recommended_questions TEXT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

INSERT INTO projects (project_key, name, description, status)
VALUES ('nexusclaw', 'NexusClaw', '政务知识问答平台', 'active')
ON DUPLICATE KEY UPDATE name = VALUES(name), description = VALUES(description), status = VALUES(status);
