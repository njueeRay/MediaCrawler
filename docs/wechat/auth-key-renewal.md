# WECHAT_AUTH_KEY 轮换操作手册

> **有效期**：Auth-Key 由 wechat-article-exporter 服务生成，约 **4 天**后过期。  
> 过期后微信爬取将 100% 失败（HTTP 401），需立即轮换。

---

## 一、如何判断 Auth-Key 已过期

以下任一情况出现时，请执行轮换：

| 信号 | 位置 |
|------|------|
| 爬虫日志出现 `401 Unauthorized` | `data/wechat/` 日志或 WebUI 执行日志 |
| `GET /api/health/platforms` 返回 `wechat: auth_invalid` | WebUI 健康检查页 |
| 距上次轮换已超过 **3 天** | 建议主动轮换，不要等到失效 |

---

## 二、获取新 Auth-Key

1. 打开浏览器，访问 wechat-article-exporter 服务（默认 `http://localhost:3000`）
2. 若已登录，点击右上角账户图标 → **重新登录**（强制刷新 token）
3. 登录成功后，打开浏览器 DevTools → **Application / Storage → Cookies**
4. 找到名为 `auth-key`（或 `token`，视 exporter 版本而定）的 Cookie 值，复制整个 Value
   - 典型格式：`Bearer eyJhbG...`（JWT）或纯字符串
5. 也可直接在 wechat-article-exporter 界面的"设置"页面找到 Auth-Key 展示框

> **提示**：exporter 启动时会在控制台打印 `X-Auth-Key: <value>`，可直接复制。

---

## 三、手动轮换步骤

### 方式 A — 修改 .env 文件（推荐）

```bash
# 1. 打开 .env（项目根目录）
nano f:/Project/GitHub/MediaCrawler/.env  # Windows 下用记事本或 VS Code

# 2. 找到并修改
WECHAT_AUTH_KEY=<新的 auth-key>

# 3. 重启 WebUI 服务（让 Python 重新 import config）
# systemd 环境：
sudo systemctl restart mediacrawler-api.service

# uvicorn 直接启动时：
# 停止进程后重新运行: uv run uvicorn api.main:app --port 8080
```

### 方式 B — 使用辅助脚本（半自动）

```bash
# 传入新 key 执行脚本（Linux/macOS）
NEW_AUTH_KEY="your-new-key" bash scripts/renew_wechat_auth.sh

# 交互式（会提示输入）
bash scripts/renew_wechat_auth.sh
```

脚本会自动：
1. 备份现有 `.env`
2. 替换 `WECHAT_AUTH_KEY` 的值
3. 提示重启服务

---

## 四、自动化 Cron 提醒模板

由于 Auth-Key 需要手动从浏览器获取（无法自动化），建议用 cron **每 3 天发一次提醒**，  
而不是自动轮换（自动化会绕过微信的登录验证）。

### Linux/macOS crontab

```cron
# 每 3 天上午 9:00 发送邮件提醒
0 9 */3 * * /usr/bin/mail -s "[MediaCrawler] WECHAT_AUTH_KEY 需要轮换" your@email.com < /dev/null

# 或者调用脚本检测并写日志
0 9 */3 * * /path/to/MediaCrawler/scripts/check_wechat_auth.sh >> /var/log/mediacrawler-auth.log 2>&1
```

### 添加 crontab（Linux）

```bash
crontab -e
# 将上面的 cron 行粘贴进去，保存退出
```

### systemd timer（推荐，替代 cron）

```ini
# /etc/systemd/system/wechat-auth-reminder.timer
[Unit]
Description=Remind to renew WECHAT_AUTH_KEY every 3 days
After=network.target

[Timer]
OnCalendar=*-*-* 09:00:00
RandomizedDelaySec=600
Persistent=true
# 每 3 天触发一次（从服务启用之日起计算）
OnUnitActiveSec=3d

[Install]
WantedBy=timers.target
```

```ini
# /etc/systemd/system/wechat-auth-reminder.service
[Unit]
Description=WECHAT_AUTH_KEY Renewal Reminder

[Service]
Type=oneshot
ExecStart=/usr/bin/mail -s "[MediaCrawler] 请轮换 WECHAT_AUTH_KEY" root
User=nobody
```

启用 timer：
```bash
sudo systemctl enable --now wechat-auth-reminder.timer
```

---

## 五、检测脚本说明

`scripts/check_wechat_auth.sh` 通过调用健康检查接口判断当前 Key 是否仍有效，  
输出人类可读的状态报告：

```bash
bash scripts/check_wechat_auth.sh
# 输出示例（Key 有效）：
# [2026-03-05 09:00:01] WECHAT_AUTH_KEY 状态: OK（上次更新: 2026-03-03）
#
# 输出示例（Key 已失效）：
# [2026-03-05 09:00:01] ⚠️  WECHAT_AUTH_KEY 已过期，请立即轮换！
# [2026-03-05 09:00:01]    执行: NEW_AUTH_KEY="<新 key>" bash scripts/renew_wechat_auth.sh
```

---

## 六、轮换后验证

```bash
# 调用微信健康检查接口
curl -s http://localhost:8080/api/health/platforms | python -m json.tool | grep wechat

# 预期输出
# "wechat": {"status": "ok", "auth": "valid"}

# 或在 WebUI 健康检查页面点击「重新检测」
```

---

## 常见问题

**Q：为什么不能自动轮换？**  
A：Auth-Key 需要用户在浏览器中手动登录微信公众平台，无法通过脚本绕过。这是微信的安全机制。

**Q：轮换频率多高合适？**  
A：建议在过期前 1 天（即第 3 天）主动轮换，避免凌晨任务跑到一半 Key 失效。

**Q：多套环境（本地 + 服务器）如何管理？**  
A：每套环境的 wechat-article-exporter 需要独立登录，Auth-Key 各不相同。建议为每个环境维护独立的 `.env` 文件。

**Q：`.env` 文件在哪里？**  
A：项目根目录下 `.env`（未提交到 Git）。如不存在，参考 `scripts/wechat_feishu_workflow.env.example` 创建。
