---
name: china-enterprise-env-setup
description: >
  国企/MCP 服务器部署模板。包含国产化环境配置（麒麟/统信 UOS）、
  数据库适配（达梦/人大金仓）、内网穿透等。
applicable-regions: [CN]
user-invocable: true
---

# China Enterprise Env Setup - 国企环境配置

国产化环境、数据库、中间件的完整配置指南。

## 国产操作系统支持

### 麒麟 Kylin V10

```bash
# 系统信息
cat /etc/kylin-release
# Kylin V10 SP1

# 基础依赖安装
sudo apt install gcc g++ make cmake
sudo apt install python3-dev python3-pip
sudo apt install postgresql-client redis-tools

# 国产中间件
sudo apt install kylin-nfs kylin-samba
```

### 统信 UOS

```bash
# 系统信息
cat /etc/os-release
# UOS 20 SP1

# 容器支持
sudo apt install containerd.io docker.io
sudo systemctl enable docker

# 加速器配置
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json <<EOF
{
  "registry-mirrors": [
    "https://dockerhub.azk8s.cn",
    "https://registry.docker-cn.com"
  ],
  "insecure-registries": ["your-private-registry.cn"]
}
EOF
```

## 国产数据库适配

### 达梦 DM8

```typescript
// 达梦数据库连接配置
interface DMConfig {
  host: string;
  port: number;      // 默认 5236
  username: string;
  password: string;
  schema: string;     // 默认 SYSDBA
  encrypt: boolean;   // 启用加密传输
}

const dmConfig: DMConfig = {
  host: process.env.DM_HOST || 'localhost',
  port: parseInt(process.env.DM_PORT || '5236'),
  username: process.env.DM_USER || 'SYSDBA',
  password: process.env.DM_PASSWORD,
  schema: process.env.DM_SCHEMA || 'SYSDBA',
  encrypt: true,
};

// TypeORM 配置示例
const dataSource = new DataSource({
  type: 'other',
  driver: require('dm-node'),
  host: dmConfig.host,
  port: dmConfig.port,
  username: dmConfig.username,
  password: dmConfig.password,
  database: dmConfig.schema,
  entities: ['src/**/*.entity{.ts,.js}'],
  synchronize: false, // 生产环境必须关闭
  logging: process.env.NODE_ENV === 'development',
});
```

### 人大金仓 KingbaseES

```typescript
// 人大金仓连接配置
interface KingbaseConfig {
  host: string;
  port: number;      // 默认 54321
  database: string;
  username: string;
  password: string;
}

const kingbaseConfig: KingbaseConfig = {
  host: process.env.KB_HOST || 'localhost',
  port: parseInt(process.env.KB_PORT || '54321'),
  database: process.env.KB_DATABASE || 'TESTDB',
  username: process.env.KB_USER || 'SYSTEM',
  password: process.env.KB_PASSWORD,
};

// PostgreSQL 兼容模式
const dataSource = new DataSource({
  type: 'postgres', // 人大金仓兼容 PostgreSQL 协议
  host: kingbaseConfig.host,
  port: kingbaseConfig.port,
  database: kingbaseConfig.database,
  username: kingbaseConfig.username,
  password: kingbaseConfig.password,
});
```

### 华为 GaussDB

```typescript
// GaussDB 连接配置
interface GaussDBConfig {
  host: string;
  port: number;      // 默认 1888
  database: string;
  username: string;
  password: string;
  ssl: boolean;
  ca: string;        // SSL 证书
}

const gaussDBConfig: GaussDBConfig = {
  host: process.env.GAUSSDB_HOST,
  port: parseInt(process.env.GAUSSDB_PORT || '1888'),
  database: process.env.GAUSSDB_DATABASE,
  username: process.env.GAUSSDB_USER,
  password: process.env.GAUSSDB_PASSWORD,
  ssl: true,
  ca: fs.readFileSync('/path/to/gaussdb-ca.pem'),
};

// Node.js 连接
import { Client } from 'pg';

const client = new Client({
  host: gaussDBConfig.host,
  port: gaussDBConfig.port,
  database: gaussDBConfig.database,
  user: gaussDBConfig.username,
  password: gaussDBConfig.password,
  ssl: {
    ca: gaussDBConfig.ca,
  },
});
```

## 国产中间件

### 东方通 TongWeb

```xml
<!-- tongweb.xml 配置 -->
<Server port="8005" shutdown="SHUTDOWN">
  <Service name="Catalina">
    <Connector port="8080"
               protocol="HTTP/1.1"
               maxThreads="200"
               minSpareThreads="10"
               enableLookups="false"
               URIEncoding="UTF-8"/>

    <Engine name="Catalina" defaultHost="localhost">
      <Realm className="org.apache.catalina.realm.DataSourceRealm"
             dataSourceName="jdbc/OracleDS"/>

      <Host name="localhost" appBase="webapps" unpackWARs="true">
        <Valve className="org.apache.catalina.valves.AccessLogValve"
               directory="logs"
               pattern="%h %l %u %t '%r' %s %b"/>
      </Host>
    </Engine>
  </Service>
</Server>
```

### 宝兰德 BES

```yaml
# bes-proxy.yaml
server:
  port: 8080
  cors:
    enabled: true
    origins:
      - "https://your-domain.cn"
    methods: [GET, POST, PUT, DELETE]

database:
  pool:
    min: 5
    max: 50
    acquireTimeout: 30000

cache:
  type: redis
  host: localhost
  port: 6379
  password: ${REDIS_PASSWORD}
```

## 内网穿透方案

### frp (花生壳替代)

```ini
# frps.ini (服务端)
[common]
bind_port = 7000
dashboard_port = 7500
token = your-secure-token
vhost_http_port = 80
vhost_https_port = 443

# HTTP 路由
subdomain_host = your-domain.cn

[web]
type = http
local_ip = 192.168.1.100
local_port = 8080
subdomain = app

[db]
type = tcp
local_ip = 192.168.1.101
local_port = 5432
remote_port = 15433
```

```ini
# frpc.ini (客户端)
[common]
server_addr = your-frp-server.cn
server_port = 7000
token = your-secure-token

[web]
type = http
local_ip = 127.0.0.1
local_port = 8080
subdomain = app
custom_domains = app.your-domain.cn

[ssh]
type = tcp
local_ip = 127.0.0.1
local_port = 22
remote_port = 6000
```

### 钉钉/企业微信内网穿透

```bash
# 使用钉钉穿透工具
./dingtalk-tunnel -proto=http -tunnel-server=wss://tunnel.dingtalk.com -tunnel-token=xxx

# 使用企业微信穿透
./wecom-tunnel -proto=http -tunnel-server=wss://tunnel.work.weixin.qq.com -tunnel-token=xxx
```

## 安全配置

### 等保 2.0 合规

```yaml
# security-baseline.yaml
# 等保2.0 基础配置要求

authentication:
  method: multi_factor
  mfa:
    - sms
    - hardware_token
  password_policy:
    min_length: 12
    require_uppercase: true
    require_lowercase: true
    require_numbers: true
    require_special: true
    expiry_days: 90

audit:
  enabled: true
  retention_days: 180
  log_types:
    - login
    - logout
    - data_access
    - data_modification
    - admin_action

encryption:
  data_at_rest:
    algorithm: SM4
  data_in_transit:
    algorithm: TLS1.2
    cipher_suites:
      - TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256
      - TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
```

### 防火墙规则

```bash
# iptables 基础规则 (CentOS/Kylin)
sudo systemctl enable firewalld
sudo firewall-cmd --zone=public --add-service=ssh --permanent
sudo firewall-cmd --zone=public --add-service=http --permanent
sudo firewall-cmd --zone=public --add-service=https --permanent
sudo firewall-cmd --reload

# 只允许特定 IP 访问管理后台
sudo firewall-cmd --zone=public --add-rich-rule='rule family="ipv4" source address="10.0.0.0/8" port port="8080" protocol="tcp" accept' --permanent
```

## 部署检查清单

| 检查项 | 要求 | 状态 |
|--------|------|------|
| 操作系统 | 麒麟 V10 / 统信 UOS / 红旗 / 中标麒麟 | ⬜ |
| 数据库 | 达梦 / 人大金仓 / GaussDB / OceanBase | ⬜ |
| 中间件 | 东方通 / 宝兰德 / 金蝶 | ⬜ |
| JDK 版本 | JDK 8 / JDK 11 (国产龙芯/飞腾适配版) | ⬜ |
| SSL 证书 | 国密 SM2 证书 | ⬜ |
| 日志审计 | 180 天保留 | ⬜ |
| 备份策略 | 每日全量 + 增量 | ⬜ |

## 常用端口

| 服务 | 端口 | 说明 |
|------|------|------|
| SSH | 22 | 安全加固后 |
| HTTP | 80/8080 |  |
| HTTPS | 443/8443 |  |
| 数据库 | 5432/5236/1888 | PostgreSQL/达梦/GaussDB |
| Redis | 6379 | 集群模式 |
| Kafka | 9092 |  |
| Zookeeper | 2181 |  |
| Nacos | 8848 | 注册配置中心 |
| Sentinel | 8080 | 流量控制 |
