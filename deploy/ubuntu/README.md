# Ubuntu 部署

运行目录 `/opt/skills-manager/current` 指向当前发布；源代码位于 `releases/`，持久化数据库、用户技能与配置位于 `shared/data/`，打包结果位于 `shared/packages/`。虚拟环境位于 `/opt/skills-manager/venv`。

`skills-manager.service` 使用单 Gunicorn 进程和 8 个线程，保持进程内任务状态一致。Nginx 使用 80 端口反向代理，Gunicorn 只监听回环地址。

云安全组与云防火墙需要允许入站 TCP 80。若服务器本机 `curl http://127.0.0.1/api/stats` 正常，而公网请求没有进入 Nginx 访问日志，应先检查云端入站规则。

Gunicorn 26 的控制目录 `/opt/skills-manager/.gunicorn` 需要服务用户可写，首次部署使用 `sudo install -d -m 0700 -o skills-manager -g skills-manager /opt/skills-manager/.gunicorn` 创建。

`/etc/skills-manager.env` 由首次部署生成，权限为 0600，保存固定会话密钥。仅 IP 访问时使用 HTTP 与 `SESSION_COOKIE_SECURE=0`；配置域名与 TLS 后改为 `1`。

初次启动前设置随机 `ADMIN_APPROVAL_KEY`，并核实数据库里的审批密钥已经替换公开默认值。现有数据库中的密钥优先于环境变量；仅修改环境文件不能覆盖已播种的默认值。首次网站管理员通过数据库初始化创建，`ADMIN_USER` / `ADMIN_PASS` 在当前代码中没有实际播种逻辑。

运维命令：

```bash
sudo systemctl status skills-manager nginx
sudo journalctl -u skills-manager -n 100 --no-pager
sudo systemctl restart skills-manager
curl -fsS http://127.0.0.1/api/stats
```

首次部署创建网站管理员，服务器 SSH 密码不会存入部署文件。网站 AI 服务在登录后的「智能设置」中配置；SMTP 未配置时关闭邮件验证码，注册账号仍需管理员审批。

## 独立后台入口

本轮后台入口方案使用现有 Nginx 转发 `/admin` 到 `/admin/approvals`。`/admin/` 和 `/api/admin/` 均使用相同的独立 Basic Auth 账号认证，普通系统页面继续公开浏览。

新版站点配置要求服务器存在 `/etc/nginx/snippets/skills-manager-admin-proxy.conf` 和 `/etc/nginx/skills-manager-admin.htpasswd`。前者由部署过程生成，包含服务端代理密钥及转发配置，权限为 0600；后者保存专用账号密码的 SHA-512 crypt 哈希，由 Nginx 工作用户读取，权限为 root:www-data 0640。不要将这两个文件提交到仓库。

环境文件设置 `ADMIN_PROXY_AUTH=1`。应用管理接口只信任 Nginx 注入的服务端密钥；主系统登录会话不授予后台权限。后台写请求带 `X-Admin-Request: 1`，浏览器不接触代理密钥。Nginx 使用认证账号记录后台操作人，并清空转发给应用的 Authorization。

后台账号采用随机用户名和 32 字符密码，密码包含大小写字母、数字和符号。登录后台时使用浏览器弹出的账号密码验证框；通过验证后直接进入审批台。

启用此配置前，先生成认证文件、同步代理密钥并备份数据库和原 Nginx 配置，执行 `nginx -t` 后再重载。当前站点为 HTTP，自动验证管理员凭据仅通过服务器本机执行。

后续更新代码时保留 `shared/`、虚拟环境和环境文件。上传最新运行代码与捆绑技能到新发布目录，将 `data` 和 `packages` 链接到共享目录，通过临时软链接原子切换 `current` 后重启服务。保留旧发布目录以便回滚。数据库若涉及版本迁移，切换前使用 SQLite 的 backup API 创建独立备份。

## 角色与动态认证（2026-10-13）

现行后台使用 Nginx auth_request 与数据库动态认证。普通管理员入口 /admin，独立超级管理员管理页 /super-admin。

环境需要 ADMIN_PROXY_AUTH=1、ADMIN_DYNAMIC_AUTH=1。服务器生成 0600 认证片段 skills-manager-auth-request.conf 与 skills-manager-admin-proxy.conf，向内部认证接口注入私有代理密钥，并转发已验证用户名的 Base64 值。公网无法访问内部认证地址。普通系统清空客户端提交的身份头。

首次部署调用 roles.seed_super_admin(db, username, password)，初始化用户名为用户指定的 superAdmin，密码通过 SSH stdin 输入。已存在超级管理员时保留其密码，后续部署不重新播种。超级管理员及晋升、密码重置后的管理员首次登录必须改密码。

空权限数组代表无权限，管理员业务功能按权限配置执行。隐藏设置保存到账号，后端继续检查权限。静态 htpasswd 不再决定后台身份，账号角色和启用状态直接从数据库读取。

部署前备份数据库、环境和 Nginx 配置，等待新配置生效后检查访问控制；失败时回滚。
