# 技能上架流程规范

> 生效日期：2026-10-19。本文是"把技能上架到线上站点"的唯一标准流程。
> 线上站点：`http://81.70.101.100/`（Ubuntu 自部署，Nginx 80 → Gunicorn 5555）。

## 0. 上架的定义

**上架 = 技能出现在线上站点的列表与搜索结果中，且能通过详情页正常查看。**

唯一判据是线上站点可搜可看。以下行为都**不是**上架：

- ❌ 提交到外部技能市场 / 候选清单（`candidates.json`、`skillstore-submissions.json`、ClawHub 发现等只是素材来源）
- ❌ 推送到 GitHub 仓库（GitHub 只是代码托管，线上站不会自动同步）
- ❌ 依赖 Render 演示站（`skills-manager.onrender.com` 已暂停，不作为上架目标）

## 1. 两条上架路径

| 路径 | 适用场景 | 技能落点 | 生效方式 |
|------|----------|----------|----------|
| **A. 捆绑技能**（正式上架） | 面向全部访客的公共技能库 | 仓库 `data/all-skills/<分类目录>/<技能名>/SKILL.md` | 随服务器发布更新生效 |
| **B. 站内导入 / 发布 API** | 单个登录用户的私有技能 | 服务器 `shared/data/user-imports/<uid>/<name>/` | 即时生效，无需发版 |

路径 B 通过网页「导入自定义 Skill」（手动 / AI / GitHub）或 `POST /api/registry/publish` 完成，自带质检门禁，不走 git。**正式的公共技能一律走路径 A**，下文为路径 A 的完整 SOP。

## 2. 路径 A：捆绑技能上架 SOP

### 第 1 步：准备技能文件

- 位置：`data/all-skills/<分类目录>/<技能名>/SKILL.md`（允许子目录嵌套，扫描按 `SKILL.md` 递归）
- 技能目录名：英文 kebab-case，须与 SKILL.md frontmatter 的 `name` 一致
- 分类目录：参照 `web/db.py` 的 `CATEGORIES_EMOJI`（如 `design-skills`、`dev-workflow-skills`、`qa-testing-skills`、`user-imports`）
- 格式模板：仓库根目录 `SKILL.md` 模板（`SKILL_TEMPLATE.md`），必填 `name` 与 `description`（语义检索与触发依赖 description）
- 参考资料放技能目录的 `references/` 子目录，打包下载时会一并携带

### 第 2 步：质检门禁（不通过不上架）

```bash
python cli/validate-skills.py --strict
```

- 存在 ERROR 即失败，必须清零后才能进入下一步
- 与库里已有技能同名 / 高度重复 → 先去重（`cli/dedupe-skills.py`），不允许带重复上架

### 第 3 步：本地验证

```bash
python cli/build_skills_index.py   # 重建本地索引
./sm search "<技能关键词>"          # 能搜到新技能
```

### 第 4 步：提交入库

```bash
git add data/all-skills/<分类目录>/<技能名>/
git commit -m "feat(skills): 上架 <技能名>"
git push origin main
```

- 不要提交 `data/skills.db`（.gitignore 已排除，确认无误即可）
- 若顺带改了代码，技能与代码分开提交

### 第 5 步：服务器发布（新 release + 原子切换）

在能 SSH 到 `ubuntu@81.70.101.100` 的机器执行（`<TS>` 用 `date -u +%Y%m%dT%H%M%SZ`）：

```bash
# 1) 上传代码与捆绑技能到新发布目录
ssh ubuntu@81.70.101.100 "mkdir -p /opt/skills-manager/releases/<TS>"
rsync -a --exclude .git --exclude 'data/skills.db' \
      ./ ubuntu@81.70.101.100:/opt/skills-manager/releases/<TS>/

# 2) data / packages 链接到共享目录（保留数据库、用户导入、AI 配置）
ssh ubuntu@81.70.101.100 "cd /opt/skills-manager/releases/<TS> \
  && ln -sfn /opt/skills-manager/shared/data data \
  && ln -sfn /opt/skills-manager/shared/packages packages"

# 3) 原子切换 current 并重启（服务启动时自动从文件重建索引）
ssh ubuntu@81.70.101.100 "ln -sfn /opt/skills-manager/releases/<TS> /opt/skills-manager/current.tmp \
  && mv -Tf /opt/skills-manager/current.tmp /opt/skills-manager/current \
  && sudo systemctl restart skills-manager"
```

要点：

- `data` 是指向 `shared/data` 的软链，因此捆绑技能实际写入 `shared/data/all-skills/`，与持久化数据同处一地
- 旧 release 目录保留不删，用于回滚
- 服务器只重启 `skills-manager`，Nginx 无需动

### 第 6 步：线上验证（缺一不可）

```bash
curl -fsS http://81.70.101.100/api/stats | head -c 400      # 技能总数 +1
curl -fsS "http://81.70.101.100/api/search?q=<关键词>"       # 能搜到新技能
```

再在浏览器打开 `http://81.70.101.100/`，用界面搜索确认列表、详情、打包下载三者正常。**三项全过才算上架完成。**

### 第 7 步：回滚（验证失败时）

```bash
ssh ubuntu@81.70.101.100 "ln -sfn /opt/skills-manager/releases/<旧TS> /opt/skills-manager/current.tmp \
  && mv -Tf /opt/skills-manager/current.tmp /opt/skills-manager/current \
  && sudo systemctl restart skills-manager"
```

## 3. 路径 B：站内发布 API（单技能快速上架）

`POST /api/registry/publish`（需登录账号且具备 `skill_import` 权限）：

- 必填：`name`、`description`、`content`；可选 `category`（默认 `user-imports`）、`version`、`author`、`tags`、`platforms`
- 门禁与导入闸门同源：规范校验 ERROR、高风险信任档案、声明与行为不符一律 422 拒收，**不支持绕过**
- 同名技能已存在时需显式传 `overwrite=true`
- 成功后立即可在 `/api/registry/user:<uid>/<name>.json` 与站内搜索中访问
- 适用：个人技能、临时技能；要变成公共技能时，把文件挪入 `data/all-skills/` 走路径 A

## 4. 上架记录

每次路径 A 上架完成后，在 `DEVLOG.md` 顶部追加一条：日期、技能名、服务器 release 时间戳、线上验证结果。路径 B 不要求记录。
