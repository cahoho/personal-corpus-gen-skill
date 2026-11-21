# Personal Corpus

一个用于构建 Obsidian 个人语料库的 AI Skill。它从用户授权的 AI 聊天记录中提炼个人认知、经历和偏好，形成可以持续维护的知识网络，帮助不同 AI 在获得访问权限后更好地理解用户。

## 核心思路

- **语料库与 Skill 分离**：Skill 负责整理和调用，个人语料保存在用户自己的 Obsidian Vault 中。
- **记忆而非聊天备份**：不大量保存对话原文，只保留提炼后的内容和少量必要原句。
- **记录来源与时间**：区分用户陈述、观察和推断，保留必要的来源与时间信息。
- **构建知识网络**：使用 Markdown、Obsidian 双向链接和 MOC 组织人物、主题、事件与项目。
- **跨 AI 使用**：不限定 AI 平台；使用前需由用户赋予相应文件访问能力。

## Skill 架构

```text
personal-corpus/
├── SKILL.md                 # 入口、核心规则和工作流程
├── references/              # 语料库规范、导入、检索与维护指南
├── assets/templates/        # Obsidian Vault 和笔记模板
└── scripts/                 # DeepSeek JSON 只读检查工具及测试
```

## 生成的语料库架构

```text
Personal Corpus/
├── 00 Start Here.md         # 入口与使用边界
├── 00 Inbox/                # 非敏感的待确认内容
├── 01 System/
│   ├── SCHEMA.md            # 库结构与字段约定
│   └── Templates/           # 可选笔记模板
├── 02 Self/
│   ├── Identity.md          # 自我认同、价值观与长期倾向
│   ├── Profile.md           # 个人基本信息
│   ├── Privacy & Boundaries.md  # 隐私与访问规则
│   └── How to Work With Me.md  # 沟通与协作偏好
├── 03 Topics/               # 持续关注的主题与人物
├── 04 Events/               # 重要事件与变化
├── 05 Projects/             # 项目及其进展
├── 06 MOCs/                 # 语料库导航
├── 07 Privacy/              # 经确认保留的关键隐私
├── 90 Sources/              # 来源批次与定位信息
└── 99 Archive/              # 可选的历史归档
```

目录和笔记按需创建，实际内容由用户授权的资料决定。

## 当前状态与隐私说明

目前优先适配 DeepSeek JSON 导出格式；辅助工具尚未经过真实导出文件验证，也不会自动完成语义提取、写库、去重或断点续跑。

`07 Privacy/` 位于同一 Vault 中，按规则仅在当前任务确有必要且用户明确同意时访问。**文件夹和 MOC 并不是加密或权限控制**；拥有文件访问权限的工具、插件或同步服务仍可能读取其中内容。
