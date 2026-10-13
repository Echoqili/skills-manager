# 外部服务实测（2026-10-13）

## DeepSeek

使用用户提供的 API 密钥，从实际 Ubuntu 部署服务器发起 HTTPS 请求：

- 模型列表接口返回 200，可用模型为 `deepseek-flash`、`deepseek-v4-pro`。
- 通过当前发布中的 `call_ai_api` 调用 `deepseek-flash`，简短测试返回 `OK`。
- 测试使用临时隔离数据库，没有改动线上用户表或管理员配置。
- 密钥通过 SSH 标准输入传入服务器进程，仅在测试进程内存中使用，没有写入本文件、仓库、服务器环境文件或用户 AI 配置。

这验证了服务器到 DeepSeek 的网络、密钥权限、模型可用性以及网站现有兼容接口客户端。未保存为站点默认 AI，未触发实际 Skill 生成。

接口地址和模型名称参考 DeepSeek 官方说明：https://api-docs.deepseek.com/ ，并以本次模型列表响应确认。

## 邮件

只读检查服务器环境文件：SMTP_HOST、SMTP_PORT、SMTP_USER、SMTP_FROM 均为空，SMTP_PASS 未配置，EMAIL_VERIFY=0。因此目前没有站点发信邮箱，也未实测发信。

继续配置需用户提供发信邮箱地址、SMTP 服务商与授权码。可通过本地文件路径提供授权码，避免将正文写入仓库。

### QQ 邮箱配置与真实发信完成

用户提供 QQ SMTP 参数后，先通过 `smtp.qq.com:465` 的 SSL 认证。首次实际发码返回 500；定位发现 `_IPv4SMTP_SSL._get_socket` 只建立 TCP 连接，没有使用 SSL 上下文包装套接字，导致 465 端口握手超时。

新增 3 项 SMTP 回归：465 返回 TLS 套接字并传入主机名、TLS 失败关闭原始套接字、587 保留 STARTTLS 前的普通连接。修复前两项失败，修复后三项通过；后端 unittest 全部 50 项通过。

仅部署 `deploy/ubuntu/smtp-tls.patch` 到 `20261013T151555Z-smtp-tls`，复制当时实际线上发布 `20261013T151356Z-roles`，保留其余线上改动。新版本服务及健康检查正常。

服务器最终配置：

- SMTP 主机：`smtp.qq.com`，SSL 端口 `465`。
- 发信账号与 From：`1809385446@qq.com`。
- 邮箱验证已开启：`EMAIL_VERIFY=1`；验证码调试打印关闭。
- 授权码仅保存在服务器 `/etc/skills-manager.env`，权限 0600，不写入仓库。
- 配置备份：`/opt/skills-manager/backups/env-before-mail-20261013T151651Z.env`。

通过真实网站发码接口向上述邮箱发送一封注册验证码，HTTP 200、success=true，QQ SMTP 接受邮件。验证码有效期 10 分钟；实际收件箱投递需由邮箱用户查看确认。重复使用滑块令牌及错误邮箱参数均返回 400；没有创建账号或改变用户审批状态。

## 账号审批

此前隔离后端的审批和账号状态检查通过，本次没有提交真实用户审批或修改真实账号。
