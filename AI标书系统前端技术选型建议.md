# AI 标书系统前端技术选型建议

## 1. 项目定位

本项目为 **企业单机部署版 AI 标书系统**，第一版重点实现以下核心闭环：

```text
资料入库 → 招标文件上传 → 招标文件解析 → 标书目录生成 → 分章节生成 → 在线编辑 → Word 导出 → 历史记录留存
```

第一版不做 SaaS、多租户、登录注册、在线支付、复杂权限和多人协作。

前端设计目标：

- 页面干净、整洁、专业
- 操作路径清晰，适合非技术人员使用
- 支持企业本地化 / 私有化部署
- 支持后续从单机版平滑升级到企业版 / SaaS 版
- 便于 AI 编程工具理解、生成和维护代码

## 2. 推荐技术栈

### 2.1 最终推荐组合

```text
React 18
Vite
TypeScript
Ant Design 5
Tailwind CSS
React Router
TanStack Query
Zustand
TipTap
lucide-react
```

## 3. 技术选型说明

### 3.1 React 18

用于构建前端应用主体。

选择原因：

- 生态成熟
- AI 编程工具支持好
- 组件化开发清晰
- 后续扩展 AI 助手、编辑器、知识库管理都比较方便

### 3.2 Vite

用于前端构建和开发服务。

选择原因：

- 启动快
- 构建简单
- 配置轻量
- 适合企业内网单机部署
- 打包后可直接交给 Nginx 托管

不建议第一版使用 Next.js。

原因：

- 当前系统不是 SEO 型网站
- 不需要服务端渲染
- 不需要复杂路由预渲染
- 单机部署下 Vite 更简单直接

### 3.3 TypeScript

全项目使用 TypeScript。

选择原因：

- 便于维护业务模型
- 减少接口字段错误
- 方便多人协作
- 方便 AI 工具理解类型结构
- 后续升级企业版时更稳

### 3.4 Ant Design 5

作为主要企业级 UI 组件库。

主要用于：

- 表格
- 表单
- 弹窗
- 文件上传
- Tabs
- Drawer
- Dropdown
- Pagination
- Message
- Modal
- Steps
- Progress

选择原因：

- 企业后台场景成熟
- 中文资料丰富
- 上传、表格、表单组件完善
- 适合知识库、资信库、产品库、历史记录等管理页面
- 普通开发人员容易接手

注意：

- Ant Design 默认风格偏传统，首页、AI 助手等页面可结合 Tailwind 做视觉优化。

### 3.5 Tailwind CSS

用于自定义页面视觉。

主要用于：

- 首页卡片布局
- AI 助手浮窗
- 顶部 Banner
- 统计卡片
- 快捷入口
- 自定义按钮样式
- 响应式布局微调

选择原因：

- 样式调整灵活
- 适合做现代 AI 产品视觉
- 和 Ant Design 可以互补
- 便于 AI 生成高质量页面代码

使用原则：

- Ant Design 负责复杂业务组件
- Tailwind 负责页面布局和视觉美化
- 避免过度覆盖 Ant Design 组件内部样式

### 3.6 React Router

用于前端路由。

推荐路由结构：

```text
/
首页

/knowledge
企业知识库

/qualification
企业资信库

/products
企业产品库

/history
历史记录

/history/:id
任务详情

/projects/new
新建标书

/projects/:id/editor
标书编辑器

/settings
系统设置
```

### 3.7 TanStack Query

用于服务端状态管理和 API 请求缓存。

适用场景：

- 知识库文件列表
- 资信库文件列表
- 产品列表
- 历史任务列表
- 任务详情
- 招标解析状态
- 章节生成状态
- Word 导出状态
- AI 助手历史消息
- 生成任务轮询

选择原因：

- 适合大量接口请求
- 支持缓存、重试、轮询
- 适合长任务状态查询
- 减少手写 loading/error 状态逻辑

任务轮询示例场景：

```text
创建生成任务 → 返回 taskId → 前端每 2 秒查询任务状态 → 状态完成后刷新页面数据
```

### 3.8 Zustand

用于轻量全局状态管理。

适用状态：

- 当前侧边栏折叠状态
- 当前系统配置缓存
- 当前标书任务 ID
- 当前编辑章节 ID
- AI 助手窗口打开 / 关闭状态
- AI 助手当前会话状态
- 当前页面上下文

选择原因：

- 比 Redux 简单
- 代码少
- 学习成本低
- 适合中小型后台系统

### 3.9 TipTap

用于标书章节在线编辑器。

适用场景：

- 标书正文编辑
- 按章节编辑内容
- 标题层级
- 段落
- 列表
- 表格
- 图片
- 引用内容
- AI 改写 / 扩写 / 精简

选择原因：

- 基于 ProseMirror，扩展性强
- 比普通 textarea 更适合长文档
- 后续可以扩展 AI 编辑能力
- 适合做“左侧目录 + 中间正文 + 右侧 AI 助手”的编辑器页面

第一版建议：

```text
TipTap 负责章节编辑
后端负责 Word 文档生成
用户最终下载 Word 继续精修
```

暂不建议第一版直接集成 OnlyOffice。

### 3.10 lucide-react

用于图标。

适用场景：

- 左侧菜单图标
- 首页功能卡片图标
- AI 助手图标
- 上传、导出、设置等操作图标

选择原因：

- 风格干净
- 适合现代 AI 产品
- 和 Tailwind 搭配自然
- 视觉比传统后台图标更轻

## 4. 不建议第一版使用的技术

### 4.1 不建议 Next.js

原因：

- 当前项目不依赖 SEO
- 不需要 SSR
- 不需要复杂服务端能力
- 企业单机部署下会增加复杂度

除非后续要做面向公网的 SaaS 官网、营销页、知识文章、招标资讯抓取展示等，再考虑 Next.js。

### 4.2 不建议 Redux

原因：

- 状态管理需求不复杂
- Zustand 足够
- Redux 模板代码偏多
- 第一版会增加开发负担

### 4.3 不建议一开始集成 OnlyOffice

原因：

- 部署复杂
- 资源占用较高
- 和文档生成链路耦合较重
- 第一版核心目标是生成可编辑 Word，不是在线完整替代 Word

后续企业版可以考虑：

```text
AI 生成内容 → 导出 Word → OnlyOffice 在线精修 → 最终下载
```

### 4.4 不建议第一版做微前端

原因：

- 当前模块数量有限
- 团队规模不大时没有必要
- 会增加部署和调试复杂度

## 5. 页面结构建议

第一版前端包含以下页面。

### 5.1 首页

路径：

```text
/
```

主要内容：

- 顶部 Banner
- 智能标书主入口
- 基础工具
- 最近任务
- 知识库状态
- 右下角 AI 助手入口

核心功能：

- 上传招标文件生成标书
- 按目录生成技术标
- 生成商务响应材料
- 查看最近任务
- 打开 AI 助手

### 5.2 企业知识库

路径：

```text
/knowledge
```

主要功能：

- 上传企业资料
- 文件列表
- 分类管理
- 文件解析状态
- 知识库索引状态
- 查看文件
- 删除文件
- 重新解析

基础分类：

```text
企业介绍
历史标书
项目案例
标准话术
行业资料
其他资料
```

### 5.3 企业资信库

路径：

```text
/qualification
```

主要功能：

- 上传资信文件
- 维护资信分类
- 维护证书编号
- 维护发证机构
- 维护有效期
- 有效期状态提示
- 查看文件
- 删除文件
- 重新解析

基础分类：

```text
基础证照
资质证书
人员证书
财务资料
项目业绩
授权模板
其他资信
```

### 5.4 企业产品库

路径：

```text
/products
```

主要功能：

- 产品列表
- 新增产品
- 编辑产品
- 删除产品
- 产品资料上传
- 产品能力标签
- 产品详情查看

产品基础字段：

```text
产品名称
产品简称
产品类型
产品版本
产品简介
适用行业
核心功能
技术架构
部署方式
兼容环境
备注
```

### 5.5 历史记录

路径：

```text
/history
```

主要功能：

- 标书任务列表
- 按状态筛选
- 查看任务详情
- 继续生成
- 编辑标书
- 重新生成
- 导出 Word
- 删除任务

任务状态：

```text
待解析
解析中
解析完成
目录已生成
生成中
待编辑
已完成
已导出
生成失败
```

### 5.6 任务详情页

路径：

```text
/history/:id
```

主要内容：

- 项目基础信息
- 招标文件
- 招标解析结果
- 评分标准
- 废标风险项
- 标书目录
- 章节生成状态
- 导出记录

### 5.7 新建标书页面

路径：

```text
/projects/new
```

流程：

```text
上传招标文件
→ AI 解析招标文件
→ 生成标书目录
→ 用户确认目录
→ 分章节生成
→ 进入编辑器
→ 检查
→ 导出 Word
```

建议使用 Steps 组件呈现流程。

### 5.8 标书编辑器页面

路径：

```text
/projects/:id/editor
```

推荐布局：

```text
左侧：章节目录
中间：章节正文编辑器
右侧：AI 辅助操作 / 资料引用 / 检查结果
```

基础能力：

- 切换章节
- 编辑正文
- 保存章节
- 重新生成当前章节
- 扩写当前章节
- 精简当前章节
- 改成正式标书语言
- 查看评分项覆盖情况
- 导出 Word

### 5.9 系统设置

路径：

```text
/settings
```

主要功能：

- 模型配置
- API 地址配置
- API Key 配置
- 本地模型配置
- 文件存储路径配置
- 向量库路径配置
- Word 模板配置
- 数据备份与恢复

## 6. 首页设计要求

首页视觉风格：

- 简洁
- 清爽
- 企业级
- 低学习成本
- 卡片式布局
- 强调主操作入口

首页必须包含：

```text
AI 标书工作台
智能标书
基础工具
最近任务
知识库状态
AI 助手
```

### 6.1 顶部 Header

左侧：

```text
AI标书系统
```

右侧：

```text
系统设置
v0.1 单机版
```

不得出现：

```text
登录
注册
邀请好友
账号中心
```

### 6.2 左侧菜单

只保留 5 个：

```text
主页
企业知识库
企业资信库
企业产品库
历史记录
```

不得出现：

```text
特色专区
查标讯
邀请好友
AI工具
智能方案
项目申报
```

### 6.3 主 Banner

文案：

```text
AI 标书工作台
企业单机部署版 · 本地知识库驱动 · 分章节生成 · Word 导出
帮助企业快速完成资料入库、招标解析、标书生成与导出，适合非技术人员直接使用。
```

### 6.4 智能标书卡片

标题：

```text
智能标书
```

说明：

```text
上传招标文件，结合企业知识库、资信库、产品库，生成可编辑的标书初稿
```

按钮：

```text
上传招标文件生成标书
按目录生成技术标
生成商务响应材料
```

其中“上传招标文件生成标书”为主按钮。

### 6.5 基础工具

只保留 4 个：

```text
招标文件解读
评分项检查
废标项检查
Word 导出
```

说明文案：

```text
招标文件解读：提取项目基础信息、技术要求、商务要求、评分标准
评分项检查：识别评分标准，检查内容覆盖情况
废标项检查：提示强制项与潜在废标风险
Word 导出：按固定模板导出可编辑 Word 文档
```

### 6.6 最近任务

字段：

```text
项目名称
招标单位
创建时间
当前状态
操作
```

示例数据：

```text
智慧园区管理平台建设项目 | 某某科技园 | 2026-04-21 | 待编辑 | 查看
医疗信息化系统升级项目 | 某某医院 | 2026-04-20 | 生成中 | 继续
智慧停车平台项目 | 某某城投公司 | 2026-04-19 | 已导出 | 查看
能源管理系统采购项目 | 某某能源集团 | 2026-04-18 | 解析完成 | 生成
```

### 6.7 知识库状态

统计项：

```text
企业知识库文件数 128
企业资信库文件数 46
企业产品库资料数 32
历史任务数 18
```

## 7. AI 助手设计要求

首页右下角保留 AI 助手入口。

### 7.1 浮动按钮

位置：

```text
页面右下角
```

按钮文案：

```text
AI 助手
```

样式：

- 圆角胶囊按钮
- 蓝紫色渐变或主色按钮
- 带机器人 / 对话图标
- 不遮挡主操作区域

### 7.2 展开后的聊天面板

面板标题：

```text
AI 标书助手
```

状态：

```text
在线
```

欢迎语：

```text
你好，我是 AI 标书助手。可解答系统使用、标书编写、资料入库等问题。
```

快捷问题：

```text
如何开始生成标书？
企业知识库怎么用？
什么是评分项检查？
如何导出 Word？
```

示例用户问题：

```text
我第一次使用，应该先做什么？
```

示例 AI 回复：

```text
建议先完善企业知识库、资信库和产品库，然后上传招标文件，系统会自动解析并生成标书目录。
```

输入框 placeholder：

```text
请输入问题...
```

### 7.3 AI 助手第一版能力范围

第一版只做轻量问答：

```text
系统使用帮助
标书基础知识问答
资料入库引导
生成流程说明
常见问题解答
```

第一版暂不做：

```text
自动改写当前章节
自动读取全部项目上下文
复杂标书推理
跨任务分析
多人对话
```

后续可扩展为：

```text
基于当前页面上下文的智能问答
基于当前标书任务的智能建议
基于知识库的企业内部问答
基于章节内容的改写 / 扩写 / 精简
```

## 8. API 请求建议

### 8.1 API Client

建议统一封装：

```text
src/api/client.ts
```

推荐使用：

```text
axios
```

或：

```text
fetch + 自定义封装
```

基础能力：

- baseURL 配置
- 统一错误处理
- 请求超时
- 文件上传
- 文件下载
- 流式响应支持

### 8.2 推荐 API 模块

```text
src/api/knowledge.ts
src/api/qualification.ts
src/api/product.ts
src/api/bidProject.ts
src/api/assistant.ts
src/api/system.ts
```

## 9. 前端目录结构建议

```text
src
├── api
│   ├── client.ts
│   ├── knowledge.ts
│   ├── qualification.ts
│   ├── product.ts
│   ├── bidProject.ts
│   ├── assistant.ts
│   └── system.ts
│
├── assets
│
├── components
│   ├── layout
│   │   ├── AppLayout.tsx
│   │   ├── Sidebar.tsx
│   │   └── Header.tsx
│   │
│   ├── assistant
│   │   ├── AIAssistantWidget.tsx
│   │   ├── AssistantButton.tsx
│   │   ├── AssistantPanel.tsx
│   │   ├── MessageList.tsx
│   │   └── MessageInput.tsx
│   │
│   ├── upload
│   │   └── FileUploadPanel.tsx
│   │
│   ├── editor
│   │   ├── BidEditor.tsx
│   │   ├── SectionTree.tsx
│   │   └── EditorToolbar.tsx
│   │
│   └── common
│       ├── StatusBadge.tsx
│       ├── EmptyState.tsx
│       └── PageHeader.tsx
│
├── pages
│   ├── Home
│   │   ├── index.tsx
│   │   ├── HeroBanner.tsx
│   │   ├── SmartBidCard.tsx
│   │   ├── BasicTools.tsx
│   │   ├── RecentTasks.tsx
│   │   └── KnowledgeStats.tsx
│   │
│   ├── KnowledgeBase
│   │   └── index.tsx
│   │
│   ├── QualificationBase
│   │   └── index.tsx
│   │
│   ├── ProductBase
│   │   └── index.tsx
│   │
│   ├── History
│   │   ├── index.tsx
│   │   └── Detail.tsx
│   │
│   ├── NewBidProject
│   │   └── index.tsx
│   │
│   ├── BidEditor
│   │   └── index.tsx
│   │
│   └── Settings
│       └── index.tsx
│
├── stores
│   ├── appStore.ts
│   ├── assistantStore.ts
│   └── bidProjectStore.ts
│
├── types
│   ├── knowledge.ts
│   ├── qualification.ts
│   ├── product.ts
│   ├── bid.ts
│   ├── assistant.ts
│   └── system.ts
│
├── utils
│   ├── format.ts
│   ├── file.ts
│   └── constants.ts
│
├── router.tsx
├── main.tsx
└── index.css
```

## 10. 核心类型建议

### 10.1 标书任务

```ts
export type BidProjectStatus =
  | 'pending_parse'
  | 'parsing'
  | 'parsed'
  | 'outline_generated'
  | 'generating'
  | 'editing'
  | 'completed'
  | 'exported'
  | 'failed';

export interface BidProject {
  id: string;
  projectName: string;
  tenderUnit?: string;
  bidType: 'technical' | 'business' | 'full' | 'other';
  status: BidProjectStatus;
  createdAt: string;
  updatedAt: string;
  exportCount: number;
}
```

### 10.2 知识库文件

```ts
export type FileParseStatus =
  | 'not_parsed'
  | 'parsing'
  | 'parsed'
  | 'parse_failed';

export type FileIndexStatus =
  | 'not_indexed'
  | 'indexed'
  | 'index_failed';

export interface KnowledgeFile {
  id: string;
  fileName: string;
  fileType: string;
  category: string;
  parseStatus: FileParseStatus;
  indexStatus: FileIndexStatus;
  uploadedAt: string;
  remark?: string;
}
```

### 10.3 企业资信文件

```ts
export interface QualificationFile {
  id: string;
  fileName: string;
  category: string;
  certificateNo?: string;
  issuer?: string;
  validFrom?: string;
  validTo?: string;
  parseStatus: FileParseStatus;
  uploadedAt: string;
  remark?: string;
}
```

### 10.4 企业产品

```ts
export interface Product {
  id: string;
  name: string;
  shortName?: string;
  type?: string;
  version?: string;
  description?: string;
  industries?: string[];
  coreFeatures?: string[];
  architecture?: string;
  deploymentMode?: string;
  compatibleEnvironment?: string;
  capabilityTags?: string[];
  createdAt: string;
  updatedAt: string;
}
```

### 10.5 AI 助手消息

```ts
export interface AssistantMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  createdAt: string;
  loading?: boolean;
}
```

## 11. 长任务交互建议

标书生成、招标解析、Word 导出都属于长任务。

前端不应等待单个接口同步返回完整结果。

推荐流程：

```text
1. 用户点击生成
2. 前端调用创建任务接口
3. 后端返回 taskId
4. 前端进入任务进度页
5. 前端轮询任务状态
6. 任务完成后刷新章节内容
```

推荐第一版使用：

```text
TanStack Query polling
```

后续可升级：

```text
SSE
WebSocket
```

## 12. AI 文本流式输出建议

AI 助手和章节生成建议后续支持流式输出。

第一版优先级：

```text
AI 助手：建议支持 SSE 流式输出
章节生成：可以先用任务轮询
```

SSE 适合：

```text
用户提问 → 后端调用模型 → 前端逐字显示
```

优点：

- 实现比 WebSocket 简单
- 适合单向文本输出
- 部署复杂度低

## 13. 文件上传建议

上传组件要求：

- 支持拖拽上传
- 支持多文件上传
- 显示上传进度
- 显示上传失败
- 支持重新上传
- 支持文件类型限制
- 支持文件大小限制

第一版支持格式：

```text
.docx
.pdf
.xlsx
.txt
.md
```

优先支持：

```text
.docx
.pdf
```

## 14. Word 导出建议

第一版前端只负责触发导出和下载。

流程：

```text
用户点击导出 Word
→ 前端请求导出接口
→ 后端生成 Word 文件
→ 前端显示导出中
→ 导出完成后提供下载链接
```

前端需要展示：

- 导出状态
- 导出失败原因
- 导出文件下载
- 历史导出记录

## 15. 部署建议

企业单机版推荐部署方式：

```text
前端：Vite build 生成 dist
后端：Java / Python 提供 API
Nginx：托管前端静态文件，并代理 API
```

Nginx 路径示例：

```text
/              → 前端静态页面
/api           → 后端接口
/uploads       → 上传文件访问
/export        → 导出文件下载
```

## 16. UI 风格规范

### 16.1 整体风格

```text
干净
整洁
专业
少干扰
强引导
企业级
AI 产品感
```

### 16.2 颜色建议

主色：

```text
#2563EB
```

辅助紫色：

```text
#6D5DF6
```

背景色：

```text
#F7F9FC
```

卡片背景：

```text
#FFFFFF
```

边框色：

```text
#E5EAF3
```

正文色：

```text
#1F2937
```

辅助文字：

```text
#6B7280
```

### 16.3 布局建议

- 左侧固定菜单
- 顶部固定 Header
- 主内容区卡片化
- 页面最大宽度根据屏幕自适应
- 首页避免过多模块
- 主操作按钮必须明显
- 表格操作按钮保持简洁

## 17. 第一版前端开发优先级

### P0 必须完成

```text
基础布局 AppLayout
左侧菜单 Sidebar
顶部 Header
首页 Home
企业知识库列表与上传
企业资信库列表与上传
企业产品库列表与新增编辑
历史记录列表
新建标书流程
标书编辑器基础版
AI 助手浮窗
系统设置基础页面
```

### P1 尽量完成

```text
任务详情页
章节生成状态
评分项检查结果展示
废标项提示展示
Word 导出记录
资信有效期提示
产品能力标签
AI 助手流式输出
```

### P2 后续完成

```text
OnlyOffice 集成
复杂 Word 模板管理
多人协作
权限管理
SaaS 化
移动端适配
可视化统计
复杂审批流
```

## 18. 开发注意事项

### 18.1 不要把首页做复杂

首页只负责：

```text
入口
任务
状态
引导
```

不要塞入太多管理功能。

### 18.2 不要把 AI 助手做成主流程

AI 助手是辅助入口，不能替代核心流程。

核心流程仍然是：

```text
上传招标文件 → 解析 → 生成目录 → 分章节生成 → 编辑 → 导出
```

### 18.3 所有长任务都要有状态

包括：

```text
文件解析
知识库索引
招标文件解析
章节生成
Word 导出
```

页面上必须清晰展示：

```text
进行中
成功
失败
可重试
```

### 18.4 所有生成内容都要可编辑

AI 生成的标书内容不能只读。

用户必须可以：

```text
编辑
保存
重新生成
导出
```

### 18.5 第一版避免过度设计

不要做：

```text
多租户
复杂权限
微前端
复杂主题系统
复杂可视化报表
完整在线 Word 替代
```

## 19. 推荐启动命令

建议使用：

```bash
npm create vite@latest ai-bid-system-frontend -- --template react-ts
cd ai-bid-system-frontend
npm install
npm install antd @ant-design/icons lucide-react @tanstack/react-query zustand react-router-dom axios
npm install -D tailwindcss postcss autoprefixer
npm install @tiptap/react @tiptap/starter-kit @tiptap/extension-table @tiptap/extension-table-row @tiptap/extension-table-cell @tiptap/extension-table-header
```

初始化 Tailwind：

```bash
npx tailwindcss init -p
```

## 20. 最终建议

第一版前端应采用：

```text
React + Vite + TypeScript + Ant Design 5 + Tailwind CSS + TanStack Query + Zustand + TipTap
```

这套组合适合当前项目：

```text
企业单机部署
后台管理页面
文件上传
历史记录
知识库管理
AI 助手
分章节编辑
Word 导出
后续私有化部署
```

第一版重点不是堆功能，而是把核心链路做稳定：

```text
上传 → 解析 → 生成 → 编辑 → 导出 → 留痕
```
