# AI 标书系统 - AI 集成视角下的编辑器选型方案

> 背景：当前系统使用 ONLYOFFICE Document Server 作为在线编辑器，但 AI 生成的 Markdown 内容与 ONLYOFFICE 的 DOCX 编辑之间存在转换损耗和体验断层。本文从 AI 集成角度重新审视编辑器选型。

---

## 一、当前 AI 集成的痛点

```
AI生成(Markdown) → python-docx转DOCX → ONLYOFFICE编辑
       ↓                    ↓                    ↓
    流式体验好          格式损耗+延迟          渲染问题+AI功能缺失
```

| 痛点 | 具体表现 | 影响 |
|------|---------|------|
| **流式断层** | AI 生成 Markdown 后，需等 python-docx 转换完成才能在 ONLYOFFICE 预览 | 用户等待时间长，无法实时看到 AI 输出 |
| **格式损耗** | python-docx 转换复杂 Markdown 时，表格/列表/嵌套格式可能丢失 | 标书格式不一致 |
| **AI 功能缺失** | 无法在 ONLYOFFICE 中选中文字让 AI 润色、续写、改写 | AI 与编辑器割裂 |
| **双向同步难** | ONLYOFFICE 编辑后的内容难以回写到 bid_sections 表（需反向解析 DOCX） | 数据不一致 |

---

## 二、AI 集成能力对比矩阵

| 维度 | ONLYOFFICE | Collabora | 纯前端编辑器(Tiptap 等) |
|------|-----------|-----------|----------------------|
| **流式内容渲染** | ★★ 需通过 API 逐段插入 | ★★ WOPI 协议限制 | ★★★★★ 直接 DOM 操作 |
| **AI 辅助编辑 API** | ★★★★ Plugin API 成熟 | ★★★ WOPI 可扩展 | ★★★★★ 完全可控 |
| **选中文字 AI 操作** | ★★★★ 支持但需开发插件 | ★★ 需 WOPI 扩展 | ★★★★★ 原生支持 |
| **Markdown 兼容** | ★★ 需转 DOCX | ★★ 需转 DOCX | ★★★★★ 原生支持 |
| **格式保真** | ★★★★ | ★★★★★ | ★★★ 需额外工作 |
| **部署复杂度** | ★★ Docker 重 | ★ Docker 更重 | ★★★★★ 纯静态 |
| **协同编辑** | ★★★★★ 原生支持 | ★★★★ WOPI 支持 | ★★★ 需 Yjs 等方案 |

---

## 三、推荐方案：双编辑器架构

### 核心思路

根据使用场景提供两种编辑模式：
- **AI 编辑模式**（Tiptap）：AI 生成阶段，Markdown 原生渲染，流式体验最佳
- **终稿编辑模式**（ONLYOFFICE）：格式调整阶段，Word 格式保真，打印导出

```
┌─────────────────────────────────────────────────────────────────┐
│                        BidEditorPage                            │
│  ┌──────────────────┐    ┌──────────────────┐                  │
│  │  AI 编辑模式      │    │  终稿编辑模式     │                  │
│  │  (Tiptap/MDX)    │    │  (ONLYOFFICE)    │                  │
│  │                  │    │                  │                  │
│  │  • Markdown 原生 │    │  • Word 格式保真  │                  │
│  │  • 流式渲染      │    │  • 页眉页脚      │                  │
│  │  • AI 续写/润色  │    │  • 打印导出      │                  │
│  │  • 实时协作      │    │  • 协同编辑      │                  │
│  └────────┬─────────┘    └────────┬─────────┘                  │
│           │                       │                             │
│           └───────────┬───────────┘                             │
│                       ▼                                         │
│              bid_sections 表 (Markdown 格式)                     │
│                       │                                         │
│                       ▼                                         │
│              python-docx → .docx (终稿导出)                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 四、方案详细设计

### 4.1 AI 编辑模式（Tiptap + Markdown）

**技术栈**：Tiptap + ProseMirror + markdown-it

**核心优势**：
- AI 生成的 Markdown 直接渲染，无需转换
- 流式内容实时追加，体验流畅
- 可深度集成 AI 功能（续写、润色、改写）

#### AI 功能集成示例

```typescript
// Tiptap AI 扩展示例
const AIExtension = Extension.create({
  name: 'aiAssistant',

  addCommands() {
    return {
      // 选中文字后 AI 润色
      polishSelection: () => ({ commands }) => {
        const { from, to } = editor.state.selection;
        const text = editor.state.doc.textBetween(from, to);
        // 调用后端 AI API
        streamPolish(text).then(stream => {
          // 流式替换选中内容
        });
      },

      // AI 续写
      continueWriting: () => ({ commands }) => {
        const context = editor.getText();
        streamContinue(context).then(stream => {
          // 在光标位置流式插入
        });
      }
    };
  }
});
```

#### 流式渲染

```typescript
// SSE 直接写入 Tiptap
const handleAIStream = (chapterId: string) => {
  const eventSource = new EventSource(`/api/sections/${chapterId}/stream`);

  eventSource.onmessage = (event) => {
    const { content } = JSON.parse(event.data);
    // 直接追加到编辑器，无需转换
    editor.commands.insertContent(content);
  };
};
```

### 4.2 终稿编辑模式（ONLYOFFICE）

保留 ONLYOFFICE 用于：
- 最终格式调整（页眉页脚、页码）
- 打印预览和 PDF 导出
- 多人协同审阅

### 4.3 数据流设计

```
                    AI 编辑模式(Tiptap)          终稿模式(ONLYOFFICE)
                           │                          │
                           ▼                          ▼
bid_sections.content ◀──── Markdown ──────▶ python-docx 转 DOCX
    (Markdown 格式)         原生读写              单向转换
```

**关键设计决策**：
- `bid_sections.content` 始终存储 Markdown 格式
- Tiptap 直接读写 Markdown
- ONLYOFFICE 仅在终稿时单向生成 DOCX
- ONLYOFFICE 编辑后的内容不回写到 bid_sections（避免格式冲突）

---

## 五、实施路线图

| 阶段 | 任务 | 优先级 | 预计工作量 |
|------|------|--------|-----------|
| **P0** | Tiptap 编辑器基础集成 | 高 | 3 天 |
| **P0** | Markdown 渲染和编辑 | 高 | 2 天 |
| **P1** | AI 续写功能（选中文字/光标位置） | 高 | 2 天 |
| **P1** | AI 润色/改写功能 | 高 | 2 天 |
| **P2** | 流式内容实时渲染优化 | 中 | 1 天 |
| **P2** | 双编辑器模式切换 UI | 中 | 1 天 |
| **P3** | AI 格式建议（标题层级、列表格式等） | 低 | 2 天 |
| **P3** | 协作编辑（Yjs 集成） | 低 | 3 天 |

---

## 六、技术选型建议

### 纯前端编辑器选型

| 方案 | 推荐度 | 理由 |
|------|--------|------|
| **Tiptap** | ⭐⭐⭐⭐⭐ | ProseMirror 封装，Markdown 支持好，扩展性强，社区活跃 |
| Slate | ⭐⭐⭐⭐ | React 原生，但 Markdown 支持需额外工作 |
| Milkdown | ⭐⭐⭐⭐ | 专为 Markdown 设计，但生态较小 |
| ByteMD | ⭐⭐⭐ | 轻量，但扩展性不足 |

**推荐 Tiptap**，理由：
1. 原生支持 Markdown（通过 `@tiptap/extension-markdown`）
2. 扩展性极强，可自定义 AI 功能
3. 协作编辑支持成熟（Yjs 集成）
4. 社区活跃，文档完善

---

## 七、与现有方案的兼容性

**不破坏现有工作流**：
- `bid_sections.content` 存储格式不变（Markdown）
- AI 生成流程不变（SSE 流式）
- ONLYOFFICE 保留为终稿编辑模式
- python-docx 转换逻辑复用

**渐进式迁移**：
1. 先在 BidEditorPage 中增加"AI 编辑"标签页
2. 用户可自由切换两种模式
3. 根据使用数据决定是否将 AI 编辑设为默认

---

## 八、总结

从 AI 集成角度，**纯前端编辑器（Tiptap）是最佳选择**，原因：

1. **消除转换损耗**：Markdown 直接渲染，无需 python-docx 转换
2. **流式体验最佳**：AI 生成内容实时显示，无延迟
3. **AI 功能深度集成**：续写、润色、改写等功能可原生实现
4. **部署简单**：纯静态资源，无需 Docker

**推荐采用双编辑器架构**：
- **Tiptap**：AI 生成和日常编辑（主模式）
- **ONLYOFFICE**：终稿格式调整和打印导出（辅助模式）

这样既保留了 ONLYOFFICE 的格式保真优势，又获得了最佳的 AI 集成体验。

---

## 附录：与原方案对比

| 维度 | 原方案 A（优化 ONLYOFFICE） | 新方案（双编辑器架构） |
|------|---------------------------|----------------------|
| AI 流式体验 | ★★ 需转换后预览 | ★★★★★ 实时渲染 |
| AI 辅助编辑 | ★★★ 需开发插件 | ★★★★★ 原生支持 |
| 格式保真 | ★★★★ | ★★★★（终稿仍用 ONLYOFFICE） |
| 部署复杂度 | ★★ 需 Docker | ★★★★ 主模式纯静态 |
| 开发工作量 | ★★★ 中等 | ★★★ 中等（分阶段） |
| 迁移风险 | ★★★★★ 低 | ★★★★ 渐进式，风险可控 |
