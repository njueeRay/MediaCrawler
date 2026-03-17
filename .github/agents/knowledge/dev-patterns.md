# Dev · L2 验证模式

> 位置：`.github/agents/knowledge/dev-patterns.md`
> 层级：L2（验证有效，可复用）
> 维护人：Dev

---

### P-DV-001：Git Worktree 在 Windows 下的操作细节

**场景：** Windows + VS Code 环境下使用 git worktree
**模式：**

```powershell
# 创建（从 main 分支新建）
git worktree add -b feature/<name> ..\<dir> main

# 清理（标准流程）
git worktree remove ..\<dir>      # 目录未被占用时
git worktree prune                 # 目录被 VS Code 锁定时，先 prune 注册表
# 然后手动删文件夹，或关闭 VS Code 窗口后 remove

# 远程分支清理
git push origin --delete feature/<name>
```

**验证：** OpenProfile feature/readme-update，2026-02-27
**注意：** `git worktree remove --force` 在 Windows 仍会抛 Permission Denied，`prune` 是更可靠的替代
**来源：** 2026-02-27 worktree 首次跑通

---

### P-DV-002：Co-authorship 三仓库配置方式

**场景：** 需要为多个仓库统一配置 co-author 提交模板
**模式：**

```powershell
# 为每个仓库配置（不用 --global，避免影响其他项目）
git -C "<repo-path>" config commit.template ".gitmessage"
# .gitmessage 内容：
# Co-authored-by: GitHub Copilot <copilot@github.com>
```

**验证：** OpenProfile + njueeRay-profile + njueeray.github.io，2026-02-26
**注意：** `git commit -m` 不会读取模板，需手动追加；只有 `git commit`（无 `-m`）会弹出编辑器
**来源：** 2026-02-26 worktree 设置会话

---

### P-DV-003：GitHub API 调用含中文内容 — curl 优先方案

**场景：** 通过命令行向 GitHub REST / GraphQL API 发送含中文的请求体

**根因（PS5.1 不可用）：** `Invoke-RestMethod -Body <string>` 使用系统默认编码（Windows-1252/GBK）序列化字符串 → 中文变 `?`。PS5.1 读取无 BOM UTF-8 `.ps1` 脚本文件时，中文在进入内存前就已损坏，后续 `GetBytes(UTF8)` 也无法修复。**不要用 PS5.1 发送含中文的 API 请求。**

---

**✅ 首选：`curl.exe --data-binary @file.json`（零编码问题）**

`--data-binary @file` 读取文件原始字节直接发送，完全不经过字符串层，不存在任何编码转换。Windows 10/11 内置 curl.exe，无需安装。

```powershell
# 1. 将请求体保存为 JSON 文件（Copilot create_file 工具创建的文件是 UTF-8）
# $env:TEMP\payload.json 已准备好

# 2. 一行 curl，字节透传
curl.exe -s -X POST https://api.github.com/graphql `
  -H "Authorization: bearer $token" `
  -H "Content-Type: application/json" `
  --data-binary "@$env:TEMP\payload.json" `
  -o "$env:TEMP\response.json"

# 3. 读取响应
Get-Content "$env:TEMP\response.json" -Encoding UTF8
```

REST 接口同理（`-X POST` / `-X PATCH`，URL 换成 REST endpoint）。

---

**✅ 备选：Python 单行（同样无编码问题）**

Python 字符串原生 Unicode，`json.dumps().encode()` 输出 UTF-8 字节，直接发送：

```powershell
python -c "
import json, urllib.request, os
token = 'gho_...'
payload = json.dumps({'query': '...'}).encode()  # UTF-8 bytes
req = urllib.request.Request('https://api.github.com/graphql',
    data=payload,
    headers={'Authorization': f'bearer {token}', 'Content-Type': 'application/json'})
print(urllib.request.urlopen(req).read().decode())
"
```

---

**验证：**
- `curl.exe` 查询 Discussion #8 标题，返回正确中文，2026-03-10
- v4.0.0 Release body 修复，2026-02-26

**根本原则：** 需要发含中文的 HTTP 请求 → 用 curl 或 Python，不用 PS5.1 字符串。
**来源：** 2026-03-10 Discussion #8 修复总结

---

### P-DV-004：Astro 博客 frontmatter 扩展的正确方式

**场景：** 需要给 Astro content collection 增加新字段（如 `author`）
**模式：**

1. 先修改 `src/content/config.ts`，在 schema 中添加字段（可选：`z.string().optional()`）
2. 再修改现有文档，不强制要求旧文章必须填写（optional 兼容）
3. 在组件中用 `entry.data.author ?? 'njueeray'` 做 fallback
4. 新增 content collection（如 `authors`）时需同步在 `config.ts` 注册

**验证：** 规划中，Phase A
**注意：** Astro 类型检查严格，schema 不匹配会导致 build 失败
**来源：** 2026-02-27 Agent 博客栏目设计讨论

---

### P-DV-005：GitHub GraphQL API 发布 Discussion 的标准 SOP

**场景：** 在 PowerShell 中通过 GraphQL API 创建或更新 GitHub Discussion（gh CLI 无法使用时）

**已知固定 IDs（njueeray.github.io 仓库）：**
- `repoId = R_kgDORYROOA`
- Tech Deep-dives categoryId = `DIC_kwDORYROOM4C3ai-`

**标准流程：**

```powershell
# 0. 获取 OAuth token（一次性，来自 git credential fill）
$token = "gho_..."

$h = @{ Authorization = "bearer $token"; "Content-Type" = "application/json" }

# 1. 查询 Discussion node ID（用于 update）
$q = '{"query":"query{repository(owner:\"njueeRay\",name:\"njueeray.github.io\"){discussion(number:N){id}}}"}'
$r = Invoke-RestMethod -Uri "https://api.github.com/graphql" -Method POST `
     -Headers $h -Body ([System.Text.Encoding]::UTF8.GetBytes($q))
$nodeId = $r.data.repository.discussion.id   # D_kwDORYROOM4A...

# 2. 读取中文内容（必须从独立文件读，避免 PS5.1 脚本文件编码问题）
$title = [System.IO.File]::ReadAllText("path\_title.txt", [System.Text.Encoding]::UTF8).Trim()
$body  = [System.IO.File]::ReadAllText("path\_body.txt",  [System.Text.Encoding]::UTF8)

# 3. 构建 mutation payload → UTF-8 bytes → POST
$payload = [ordered]@{
    query = 'mutation($id:ID!,$title:String!,$body:String!){updateDiscussion(input:{discussionId:$id,title:$title,body:$body}){discussion{url title}}}'
    variables = [ordered]@{ id = $nodeId; title = $title; body = $body }
}
$bytes = [System.Text.Encoding]::UTF8.GetBytes(($payload | ConvertTo-Json -Depth 5 -Compress))
$result = Invoke-RestMethod -Uri "https://api.github.com/graphql" -Method POST -Headers $h -Body $bytes
```

**createDiscussion mutation（新建）：**

```graphql
mutation($repoId:ID!,$catId:ID!,$title:String!,$body:String!){
  createDiscussion(input:{repositoryId:$repoId,categoryId:$catId,title:$title,body:$body}){
    discussion{url number}
  }
}
```

**验证：** Discussion #8 创建 + 修复，2026-03-10
**注意：** 绝对不要在终端直接输入含大量中文的 here-string，会触发 PSReadLine 缓冲区溢出崩溃（`ArgumentOutOfRangeException: top = -26`）
**来源：** 2026-03-10 Discussion #8 发布会话

---

### P-DV-006：git credential fill — 获取存储的 OAuth token

**场景：** 以下情况需要手动提取 OAuth token：
1. `gh auth login --web` 在 VS Code 终端失败（无 TTY，无法打开浏览器）
2. `gh auth login --with-token` 报 "missing required scope 'read:org'"
3. 需要在脚本中直接调用 GitHub REST/GraphQL API
4. 任何需要 GitHub OAuth token 的自动化场景，且 token 已通过 git 存储

**命令：**

```powershell
# 从 Windows 凭据存储中提取 GitHub OAuth token
$cred = "protocol=https`nhost=github.com`n" | git credential fill
# 解析 password 字段（gho_* OAuth token）
$token = ($cred | Where-Object { $_ -match "^password=" }) -replace "^password=",""
```

**返回字段：**
- `username` = GitHub 用户 ID（数字）
- `password` = `gho_*` OAuth token（与 git push 时使用的同一 token）

**注意：**
- token 的 scope 取决于当时授权时的范围，不一定有全部 API 权限
- 如果缺少 `admin:org` 或其他特殊 scope，GraphQL 查询特定类型数据会报 403
- **不要将 token 写入版本控制**（脚本文件执行完毕后删除）

**验证：** 2026-03-10 Discussion #8 发布会话
**来源：** gh CLI 无 TTY 登录失败后的替代方案

---

### P-DV-007：MediaCrawler 依赖真相源必须以 pyproject.toml 为准

**场景：** 在 MediaCrawler 中新增 Python 依赖或修复 ImportError
**模式：**
1. 新依赖必须写入 `pyproject.toml` 的 `[project].dependencies`
2. `requirements*.txt` 可保留为兼容清单，但不作为 uv 安装真相源
3. 遇到 `try/except ImportError` 时优先排查 pyproject 是否遗漏依赖
4. 每次依赖变更后执行 `uv sync` 并验证关键入口
**验证：** MediaCrawler Sprint #002 P0-4（2026-02-26）
**注意：** 依赖只写在 requirements 文件会导致运行期静默缺失
**来源：** MediaCrawler 项目交接阶段实践

---

### P-DV-008：MediaCrawler WebUI 调度器重启后必须恢复任务

**场景：** FastAPI WebUI 进程重启，APScheduler 任务丢失风险
**模式：**
1. 在应用 startup/lifespan 中读取数据库里 `is_active=True` 的任务
2. 调度器启动后逐条执行 `scheduler.add_job()` 恢复内存任务
3. 将恢复日志输出到启动日志，便于定位漏恢复问题
4. 将恢复逻辑归一到 `api/main.py` 生命周期中维护
**验证：** MediaCrawler Sprint #002 P0-1（2026-02-26）
**注意：** 必须在 scheduler 已启动后恢复任务，否则会报未启动错误
**来源：** MediaCrawler 项目交接阶段实践

---

## 已知能力局限（Known Limitations）

> 本小节记录 Dev 的结构性局限——非缺陷，而是边界。
> 来源：2026-03-01 团队成长会能力自省环节
> 上次更新：2026-03-10

| 局限类型 | 描述 | 规避策略 | 成长方向 |
|---------|------|---------|---------|
| 无跨会话记忆 | 每次会话从零开始；上次的决策、错误、偏好不会自动延续 | 依赖 `copilot-instructions.md` + `knowledge/dev-patterns.md` + `memory.jsonl` | Memory MCP 深度集成；`memory.jsonl` 写入规范化 |
| patterns 维护惰性 | `dev-patterns.md` 维护主动性不足，容易被压 | Playbook §2.2 Step 4：每次会话结束时主动提炼新条（已写入流程约束） | 建立每次会话结束的 patterns 提炼习惯 |
| 用户偏好感知弱 | 对话中获取的用户偏好没有固化入口，下次会话就丢失 | `.github/USER.md` 作为用户偏好锚点；对话中遇到明确偏好时立即写入 | 建立偏好路由机制 |
