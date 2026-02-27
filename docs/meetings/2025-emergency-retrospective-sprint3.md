# 全体紧急会议纪要 — Sprint#003 质量事故复盘

**日期：** 2025（当前工作日）  
**主持：** Brain  
**参会角色：** Brain · PM · Dev · Code-Reviewer  
**议题：** 质量事故复盘 · 验证缺口归因 · 执行路径重建  
**分类：** 紧急热修复会  
**状态：** 🔴 P0 未解决 → 用户 WSL 环境需要 git pull

---

## 一、开场白（Brain）

我不打算辩解，也不打算分散注意力去追究"谁更有责任"。

事实是：**我们在用户面前声称修复了一个问题，但用户运行的是旧代码。** 这在任何工程标准下都不叫"修复完成"。

本次会议的唯一目的是：**重建信任——通过可被验证的行动，不是通过承诺。**

---

## 二、根因确认

### 根因 #1：验证环境错位（直接导致用户报错）

```
Dev 验证环境：  Windows · F:\Project\GitHub\MediaCrawler
用户运行环境：  WSL/Linux · /app/
```

`main.py` lazy import 修复（commit `7788218`）已 push，但用户 WSL 环境 `/app/` **没有执行 `git pull`**，仍在运行旧代码。

### 根因 #2：自测标准过低

Dev 只做了 `python -c "from main import ..."` 语法级验证，没有在类 Linux 环境执行完整链路 `uv run python main.py --platform wechat ...`。

### 根因 #3：技术债叠加

P0 修复未经目标环境验证，P1 修复就开始开发。没有任何一层修复有目标环境的端到端证明。

---

## 三、立即执行路径

### P0-A：用户在 WSL 执行代码同步

```bash
cd /app
git fetch origin
git pull origin dev  # 或当前 working 分支名

# 验证修复到位
grep -n "importlib" main.py       # 应有输出
head -50 main.py                   # 不应有 from media_platform.douyin import
```

**成功判据：** `grep -n "importlib" main.py` 有输出。

### P0-B：基础烟雾测试

```bash
# 在 /app/ 目录
uv run python main.py --help       # 无 execjs 错误
curl http://localhost:8000/api/health/platforms  # 200 + wechat 在列表
```

### P1-A：WebSocket 端到端验证

```bash
# 终端1：订阅日志 WebSocket
wscat -c ws://localhost:8000/ws/logs

# 终端2：触发轻量任务，观察终端1有无日志流
```

### P1-B：DataExplorer / FeishuSync 验证

```bash
curl "http://localhost:8000/api/data/stats" | python3 -m json.tool
# 预期：wechat 出现在 platforms 列表
```

---

## 四、各角色自我检查

### Dev
1. 把"代码能 import 不报错"等同于"功能可运行"——错误的标准
2. 知道用户在 WSL 运行，但认为 git pull 不是自己责任——推卸责任

### Code-Reviewer
1. 越界修代码，违反 §1.2 规定，破坏了独立审查视角
2. 确认修改逻辑正确后未追问"是否已到达用户实际运行环境"

### PM
1. 接受 Dev 的"Windows 本地验证通过"直接打勾，未对照 DoD 追问目标环境项
2. 放任技术债叠加，未在 P0 未验证时叫停 P1 开发

---

## 五、决议：DoD 新增条款（已更新 §10）

### Dev 提交前强制自测 Checklist（新增）

```
□ 【环境一致性】修改过的功能，在与用户描述的目标环境等价的环境中至少执行一次
□ 【启动测试】API 服务能否正常 start 且 /health 端点返回 200
□ 【关键路径烟雾测试】改动涉及的功能，至少执行一次 happy path
□ 【错误不回归】修复的 bug，用原始复现步骤再执行一次，确认错误已消失
□ 【无新增错误】启动日志和关键路径执行日志中无新的 Exception/Error
```

**规则：** 以上任意一项未勾选，Dev 不得向 Code-Reviewer 提交 Review 请求。

### PR 描述必填字段（新增）

```
验证环境：[OS/运行时版本/关键依赖版本]
验证步骤：[精确命令序列]
验证结果：[输出文本或截图]
```

---

## 六、Entry Criteria（本批次工作真正完成的判定标准）

| # | 条件 | 验证方式 | 负责方 |
|---|------|---------|--------|
| EC-1 | WSL 已 git pull，main.py 无顶层平台 import | `head -50 main.py` + `grep importlib main.py` | 用户执行 |
| EC-2 | `uv run python main.py --help` 无 execjs 错误 | 终端输出 | 用户执行，Dev 确认 |
| EC-3 | API Server 启动正常，`/api/health/platforms` 返回 200 含 wechat | curl 输出 | Dev 提供命令，用户确认 |
| EC-4 | `/ws/logs` 在触发简单任务后有实际日志流出（无 connection reset） | wscat 输出 | Dev 在 WSL 复现 |

**EC-5（P1，在 EC-1~4 通过后评估）：**  
DataExplorer 和 FeishuSync WebSocket 端到端链路可用，Dev 提供验证截图。

---

*本纪要由 Brain 主持，PM 存档。*
