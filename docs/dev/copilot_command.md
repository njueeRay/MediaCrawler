# GitHub Copilot Chat 常用命令速查

> 本文梳理 VS Code 中 GitHub Copilot 的常用斜杠命令、上下文引用、键盘快捷键、@参与者、
> 代码补全技巧及工作区外代码引用方式。适用于 Copilot Chat（含 Agent 模式）。
> 最后更新：2026-02-09

---

## 1. 斜杠命令（Slash Commands）

在聊天输入框键入 `/` 即可唤出。

| 命令 | 作用 | 典型用法 |
| --- | --- | --- |
| `/explain` | 解释选中代码或整个文件 | `/explain 这段正则做了什么` |
| `/fix` | 诊断并修复代码问题 | `/fix TypeError: 'NoneType' is not iterable` |
| `/tests` | 为选中代码或文件生成测试用例 | `/tests 用 pytest 为 #file 生成测试` |
| `/doc` | 生成/补全文档注释（docstring 等） | `/doc 为这个类加上中文 docstring` |
| `/optimize` | 优化代码性能或可读性 | `/optimize 减少这段循环的时间复杂度` |
| `/new` | 从零生成新项目/文件骨架 | `/new 创建一个 FastAPI + SQLAlchemy 项目` |
| `/newNotebook` | 创建新 Jupyter Notebook | `/newNotebook 数据清洗 demo` |
| `/clear` | 清空当前对话历史 | `/clear` |
| `/help` | 查看可用命令列表 | `/help` |
| `/search` | 在工作区中搜索代码 | `/search 找到所有调用 login() 的地方` |
| `/startDebugging` | 生成 launch.json 并启动调试 | `/startDebugging 调试 main.py` |
| `/setupTests` | 配置测试框架 | `/setupTests 配置 pytest` |
| `/runTask` | 创建并运行 VS Code Task | `/runTask 执行 build` |

---

## 2. 上下文引用（# 变量）

在输入框键入 `#` 会弹出候选列表，选择后自动注入上下文。

| 语法 | 作用 | 示例 |
| --- | --- | --- |
| `#selection` | 编辑器中当前选中的文本 | `解释 #selection` |
| `#file:路径` | 指定文件（支持模糊搜索） | `总结 #file:main.py` |
| `#editor` | 当前编辑器可见区域 | `检查 #editor 是否有潜在问题` |
| `#workspace` | 整个工作区（语义搜索） | `#workspace 中哪些地方用了 Redis` |
| `#codebase` | 类似 #workspace 的语义索引 | `#codebase 里有没有数据库迁移逻辑` |
| `#problems` | 问题面板中的错误/警告 | `/fix #problems` |
| `#terminal` | 终端最近的输出 | `解释 #terminal 的报错` |
| `#terminalLastCommand` | 终端最后一条命令 | `这条命令做了什么 #terminalLastCommand` |
| `#terminalSelection` | 终端当前选中文本 | `解释 #terminalSelection` |
| `#sym:符号名` | 引用代码符号（函数/类/变量） | `解释 #sym:AbstractCrawler` |
| `#changes` / `#git diff` | 当前 Git 暂存/未暂存变更 | `review #changes` |
| `#testFailure` | 最近一次测试失败信息 | `/fix #testFailure` |
| `#fetch:URL` | 抓取网页内容注入上下文 | `总结 #fetch:https://example.com/api-docs` |
| `#thread` | 引用当前对话的历史消息 | `结合 #thread 继续优化` |

**附加挂载方式：**

- **拖拽文件**到聊天框 → 自动作为附件引用
- **回形针图标** 📎 → 手动添加文件/文件夹作为上下文
- **图片附件** → 支持拖拽图片，Copilot 可识别截图内容

---

## 3. @参与者（Chat Participants）

在输入框键入 `@` 切换对话对象，不同参与者擅长不同领域。

| 参与者 | 作用 | 典型用法 |
| --- | --- | --- |
| `@workspace` | 工作区感知，回答项目结构与代码问题 | `@workspace 这个项目的入口文件是哪个` |
| `@vscode` | VS Code 设置与功能相关 | `@vscode 如何修改终端字体大小` |
| `@terminal` | 生成/解释终端命令 | `@terminal 如何用 git 撤销最近一次提交` |
| `@github` | GitHub 仓库/Issue/PR 相关 | `@github 搜索这个仓库里的 open issues` |

---

## 4. 对话模式（Chat Modes）

VS Code Copilot Chat 支持多种模式，点击聊天框顶部切换：

| 模式 | 说明 | 适用场景 |
| --- | --- | --- |
| **Ask** | 只回答问题，不修改文件 | 了解代码、学习 API、提问 |
| **Edit** | 直接编辑工作区中的文件 | 重构、小范围修改 |
| **Agent** | 自主规划 + 调用工具 + 执行终端命令 + 编辑文件 | 复杂多步骤任务 |

Agent 模式下 Copilot 可以：
- 自动运行终端命令
- 搜索/读写文件
- 管理 todo 清单
- 调用 MCP 工具
- 启动调试/构建任务

---

## 5. 键盘快捷键

| 快捷键 (Windows/Linux) | 快捷键 (Mac) | 功能 |
| --- | --- | --- |
| `Ctrl+I` | `Cmd+I` | 打开 Inline Chat（行内聊天） |
| `Ctrl+Shift+I` | `Cmd+Shift+I` | 打开/聚焦 Copilot Chat 面板 |
| `Ctrl+L` | `Cmd+L` | 打开 Chat 面板并新建对话 |
| `Ctrl+Enter` | `Cmd+Enter` | Inline Chat 中直接应用建议 |
| `Escape` | `Escape` | 关闭 Inline Chat / 取消当前操作 |
| `Tab` | `Tab` | 接受代码补全建议 |
| `Escape` | `Escape` | 拒绝代码补全建议 |
| `Alt+]` / `Alt+[` | `Option+]` / `Option+[` | 在多个补全建议之间切换 |
| `Ctrl+→` | `Cmd+→` | 逐词接受补全（部分采纳） |
| `Ctrl+Shift+Enter` | `Cmd+Shift+Enter` | Inline Chat 中将建议插入(而非替换) |
| `Ctrl+Alt+I` | `Ctrl+Cmd+I` | 快速在编辑器/Chat 面板之间切换 |

---

## 6. Inline Chat（行内聊天）常用操作

在编辑器中 `Ctrl+I` 唤起，直接在代码上方/下方出现输入框。

| 操作 | 说明 |
| --- | --- |
| 选中代码 → `Ctrl+I` | 针对选中代码进行行内提问或修改 |
| 不选中 → `Ctrl+I` | 在光标位置生成代码 |
| 输入 `/doc` | 行内直接补全 docstring |
| 输入 `/fix` | 行内修复当前代码 |
| 输入 `/tests` | 行内生成测试 |
| 点击 ✓ / `Ctrl+Enter` | 接受修改 |
| 点击 ✗ / `Escape` | 拒绝修改 |
| 点击 ↻ | 重新生成 |

---

## 7. 代码补全（Completions）技巧

Copilot 在编辑器中的"灰色建议文字"是实时补全功能。

| 技巧 | 说明 |
| --- | --- |
| 写好函数签名 + docstring → 回车 | Copilot 根据签名和注释自动补全函数体 |
| 写注释描述意图 → 回车 | 按注释意图生成代码 |
| `Tab` 接受 / `Esc` 拒绝 | 基本操作 |
| `Alt+]` / `Alt+[` | 多个建议间切换 |
| `Ctrl+→` 逐词采纳 | 只接受建议的前几个 token |
| 在文件顶部写好 import 和类型注解 | 大幅提升补全质量 |
| 打开相关文件作为"邻居 Tab" | Copilot 会参考已打开的文件 |

> **邻居 Tab 效应**：Copilot 会参考当前打开的其他编辑器 Tab 来提升补全质量。
> 如果你希望 Copilot 参照某段代码风格，把那个文件打开即可。

---

## 8. 右键菜单 & 命令面板

### 编辑器右键菜单

右键选中代码后可看到 Copilot 子菜单：

- **Copilot → Explain This** — 解释选中代码
- **Copilot → Fix This** — 修复选中代码
- **Copilot → Generate Docs** — 生成文档
- **Copilot → Generate Tests** — 生成测试

### 命令面板（`Ctrl+Shift+P`）

搜索 `Copilot` 可找到：

| 命令 | 说明 |
| --- | --- |
| `GitHub Copilot: Open Chat` | 打开聊天面板 |
| `GitHub Copilot: Toggle Completions` | 启用/禁用代码补全 |
| `GitHub Copilot: Open Completions Panel` | 打开补全建议面板（查看所有建议） |
| `Copilot: Explain This` | 解释选中代码 |
| `Copilot: Fix This` | 修复选中代码 |
| `Copilot: Generate Commit Message` | 基于 staged changes 自动生成提交信息 |
| `Copilot: Review and Comment` | 对选中代码做 code review |

---

## 9. Git 集成

| 功能 | 操作 |
| --- | --- |
| **自动生成 Commit Message** | 在源代码管理面板，点击提交信息输入框右侧的 ✨ 图标 |
| **Review Changes** | `review #changes` 或 `review #git diff` |
| **PR 描述生成** | 在 GitHub PR 页面使用 Copilot 总结变更 |

---

## 10. 如何快捷引用工作区外的代码（重点）

Copilot Chat 默认只感知"工作区内"文件。引用外部代码有以下方式：

### 方案 A：多根工作区（最推荐，频繁引用时使用）

```
文件 → 将文件夹添加到工作区...
```

把外部代码目录加入后，`#file`、`#workspace`、`@workspace` 均可直接引用。

### 方案 B：临时打开文件 + 选中引用

1. 把外部文件拖拽到 VS Code 编辑器。
2. 选中代码片段 → 用 `#selection` 引用。
3. 或者直接在聊天框中拖入该文件作为附件。

适合偶尔引用小段代码。

### 方案 C：#fetch 抓取远程代码

```
#fetch:https://raw.githubusercontent.com/user/repo/main/file.py
```

可直接拉取 GitHub 上的原始文件内容作为上下文（需文件可公开访问）。

### 方案 D：粘贴代码片段

直接粘贴到聊天输入框，并说明来源。最直接但无法自动追踪文件上下文。

### 方案 E：使用 `@github` 引用其他仓库

```
@github 搜索 NanmiCoder/MediaCrawler 仓库中 login 相关代码
```

可以搜索 GitHub 上其他仓库的代码，无需克隆。

---

## 11. 实用技巧汇总

| 技巧 | 说明 |
| --- | --- |
| **精准上下文** | 先选中代码再提问，比全文引用效率高 |
| **分步提问** | 复杂任务拆成小步骤逐步完成 |
| **邻居 Tab** | 打开相关文件让 Copilot 作为参考 |
| **Agent 模式** | 复杂多步骤任务切换到 Agent 模式 |
| **`/clear` 重置** | 对话跑偏或上下文污染时清空重来 |
| **指定语言/框架** | 在提示中明确说 "用 Python / 用 asyncio" |
| **指定风格** | "按照 Google Style 写 docstring" |
| **提供示例** | 给一个输入输出样例，补全质量大幅提升 |
| **`.github/copilot-instructions.md`** | 项目级 Copilot 指令文件，全员共享提示词 |
| **`settings.json` 配置** | `github.copilot.chat.codeGeneration.instructions` 可配置全局指令 |

---

## 12. 常用组合速查

```text
# 修复报错
/fix #problems

# 为当前文件写测试
/tests 为 #file 生成 pytest 测试

# 解释选中代码
/explain #selection

# 为文件补全文档
/doc 为 #file 中所有函数补全 docstring

# 审查 Git 变更
review #changes 是否有逻辑问题

# 基于测试失败修复
/fix #testFailure

# 从网页获取 API 文档并生成代码
根据 #fetch:https://api.example.com/docs 生成调用代码

# 搜索工作区
@workspace 找到所有异步爬虫类

# 生成 commit message
在源代码管理面板点击 ✨ 图标
```

---

## 13. Copilot 配置参考

在 `settings.json` 中可调整：

```jsonc
{
  // 启用/禁用代码补全
  "github.copilot.enable": { "*": true },

  // Chat 代码生成指令（全局 system prompt）
  "github.copilot.chat.codeGeneration.instructions": [
    { "text": "始终使用中文注释" },
    { "text": "优先使用 async/await" }
  ],

  // 指定测试生成框架
  "github.copilot.chat.testGeneration.instructions": [
    { "text": "使用 pytest 和 pytest-asyncio" }
  ],

  // 代码审查指令
  "github.copilot.chat.reviewSelection.instructions": [
    { "text": "检查异常处理是否完整" }
  ]
}
```

项目级指令文件：`.github/copilot-instructions.md`，写入后对所有协作者生效。
