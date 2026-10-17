-- book-system-boot 建表与演示数据
-- 演示账号：demo / demo123（密码为 MD5，仅用于本地跑通）
CREATE DATABASE IF NOT EXISTS book_system
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE book_system;

DROP TABLE IF EXISTS `book`;
CREATE TABLE `book` (
                        `bid` int NOT NULL AUTO_INCREMENT COMMENT '图书ID',
                        `uid` int NOT NULL COMMENT '所属用户ID',
                        `title` varchar(100) NOT NULL COMMENT '书名',
                        `author` varchar(50) NOT NULL COMMENT '作者',
                        `price` decimal(10,2) NOT NULL DEFAULT '0.00' COMMENT '价格',
                        `status` int NOT NULL DEFAULT '0' COMMENT '阅读状态: 0未读, 1已读',
                        PRIMARY KEY (`bid`),
                        KEY `idx_uid` (`uid`),
                        KEY `idx_title` (`title`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='图书表';

DROP TABLE IF EXISTS `sys_user`;
CREATE TABLE `sys_user` (
                            `uid` int NOT NULL AUTO_INCREMENT COMMENT '用户ID',
                            `username` varchar(50) NOT NULL COMMENT '用户名',
                            `user_pwd` varchar(50) NOT NULL COMMENT '密码(MD5加密)',
                            PRIMARY KEY (`uid`),
                            UNIQUE KEY `uk_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='系统用户表';

INSERT INTO `sys_user` VALUES (1,'demo','62cc2d8b4bf2d8728120d052163a77df');
INSERT INTO `book` VALUES
                       (1,1,'深入理解Java虚拟机','周志明',109.00,0),
                       (2,1,'MySQL是怎样运行的','小孩子4919',99.50,1),
                       (3,1,'代码整洁之道','Robert C. Martin',79.00,0);