# Project Agent Instructions

## 飞书文档导入 Skill

当用户要求将本项目生成的 Markdown 文档同步、发布、上传、归档到飞书时，使用以下 Skill：

- Skill 路径：.agents/skills/feishu-doc-import/
- 默认文档目录：feishu/docs/
- 目标知识库：AI标书系统-国家电网
- 知识库地址：https://acn03r8l9jgi.feishu.cn/wiki/space/7646261306835635128

## 当前稳定链路

V1 只执行：

本地 Markdown → lark-cli drive +import → 飞书 Docx 云文档 URL

不要自动移动到知识库。导入成功后，由用户手动移动到知识库。

## 执行命令

当用户说“同步到飞书”“发布到飞书”“上传到飞书知识库”时，优先执行：

```bash
.agents/skills/feishu-doc-import/scripts/import-to-feishu-docx.sh "<markdown文件路径>" "<标题>"
