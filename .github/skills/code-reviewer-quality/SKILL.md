```skill
---
name: code-reviewer-quality
version: "1.0.0"
description: 七维度质量门禁，输出结构化审查报告至 docs/reviews/，只读专家不修改被审查文件。
triggers:
  - "代码审查"
  - "code review"
  - "质量检查"
  - "审查"
  - "review"
  - "LGTM"
  - "质量报告"
  - "门禁"
examples:
  - input: "发布前请代码审查这次变更"
    output: "Code Reviewer 按七维度逐项检查 → 输出 APPROVED/APPROVED WITH NOTES/NEEDS REVISION 报告至 docs/reviews/"
  - input: "检查这篇博文的发布质量"
    output: "Code Reviewer 从内容准确性、链接有效性、Markdown 格式、SEO 字段完整性四维审查"
constraints:
  - 只输出报告，不直接修改被审查文件
  - Minor 及以上版本发布前必须完成审查
  - 不做架构决策，只诊断问题
reference: .github/agents/code-reviewer.agent.md
---
```
