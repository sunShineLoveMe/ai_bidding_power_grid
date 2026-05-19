# 章节大纲生成

> 相关代码：`backend/ai/chapter_planner.py`、`backend/ai/bid_writing_plan.py`

## 章节大纲生成

### 生成机制：两阶段流式输出

章节大纲生成采用**两阶段流式**设计，通过 SSE 接口 `GET /api/bidding/interpretations/{project_id}/bid-outline/stream` 实时推送进度。

```
第一阶段（秒级，立即展示）
  _build_rule_outline()
  → 基于硬编码骨架 + 招标解读数据（要求/评分/风险）关键词匹配
  → 立即推送规则版章节给前端，用户可以看到初始目录

第二阶段（10-30 秒，在 SSE 流内同步完成）
  _generate_outline_from_ai_or_rule()
  → 调用 LLM，结合招标评分项 + 企业知识库生成精细化大纲
  → 完成后推送 refined 事件，前端自动刷新为 AI 版章节
  → 若 AI 版章节数少于规则版，保留规则版（防止退化）
```

规则版骨架是用户可见流程的第一道兜底，不能因为 AI 解读报告中的单个字段结构异常而中断。后端会对以下输入做类型防御：

- `requirements`、`scoringItems`、`risks`：只使用结构化对象，忽略字符串等非结构化脏数据。
- `ai_report.material_checklist`：兼容 `["营业执照"]` 字符串列表和 `[{material, category}]` 对象列表，统一转换为材料对象后再参与章节匹配。

这样即使大模型返回的材料清单字段不稳定，流式大纲也应至少生成规则版目录，避免流程卡在“生成分册大纲”。

### 大纲落库可靠性

流式接口在推送完规则版章节后，会把最终大纲写入 `bid_analysis.project_meta.bid_outline`，并同步替换 `bid_sections`。这一步不能采用“删除后逐条插入”的弱事务方式，否则网络中断或重复 SSE 连接会造成目录写入一半、随后被另一个请求删除，前端表现为“生成分册大纲失败”。

当前实现由 `replace_bid_sections_from_outline()` 统一处理：

- 同一 `project_id` 使用进程内锁串行执行，避免首页自动流程、编辑器自动生成和后台 AI 精修同时删写同一项目章节。
- 写入前为每个章节预生成 UUID，子章节 `parent_id` 直接指向同批次内的父章节 ID，避免逐条插入时依赖数据库返回父 ID。
- `bid_sections` 采用删除旧数据后分批插入，单批默认 50 条，减少 Supabase/PostgREST 请求次数。
- 删除和批量插入作为一个整体使用 `_with_supabase_write_retry()` 重试；若 Supabase HTTP/2 出现 `Server disconnected`、`RemoteProtocolError` 等临时网络问题，会重置客户端并重新执行完整替换。

因此清库并不能解决这类错误，根因通常是大纲落库阶段的网络抖动或并发写入竞态；修复点应放在后端章节持久化层，而不是让用户反复删除项目。

SSE 事件类型：

| 事件 | 含义 |
| --- | --- |
| `start` | 开始生成 |
| `meta` | 推送大纲元信息（分册结构、预计章节数） |
| `stage` | 阶段提示（展开子章节、AI 精细化中等） |
| `chapter` | 单个章节数据（`phase: quick` 或 `phase: refined`） |
| `refined` | AI 精细化完成，前端清空规则版章节并重新填充 AI 版 |
| `done` | 全部完成，携带最终大纲 |

### AI 大纲生成：结合招标文件 + 企业知识库

`_build_prompt()` 在调用 LLM 前会注入三类动态信息：

**1. 招标文件结构化数据**

- 评分项（按分类分组，每项必须有对应章节响应）
- 要求条款（资格/商务/技术/文件格式）
- 风险项（高风险/废标项必须有专项章节）
- AI 深度解读报告（项目摘要、材料清单、文件计划）

**2. 企业私有知识库上下文**（`_fetch_knowledge_context()`）

大纲生成前会自动检索企业知识库，抽取两类信息注入 Prompt：

```
RAG 文档片段（标准话术、施工方案、政策法规）
  → 用于指导章节内容方向和写作依据

企业资产库摘要（资质证书、产品图、业绩证明）
  → has_qualification_assets → 资格文件分册为每类资质单独设章
  → has_product_assets       → 技术标为每类产品设专项技术参数章节
  → has_case_assets          → 资格文件设"类似项目业绩"章节
```

**3. 章节数量规则（动态计算）**

```python
min_chapters = max(
    25,                      # 绝对下限
    scoring_count * 2,       # 每个评分项平均 2 个章节
    requirement_count // 3,  # 每 3 个要求条款对应 1 个章节
)
min_chapters = min(min_chapters, 80)  # 上限 80
```

强制规则（写入 Prompt）：
- 每个评分项必须有至少一个对应章节，不得合并到笼统章节
- 每个高风险/废标项必须有专项章节响应
- 技术标"施工组织设计"必须展开到三级（总体部署、进度计划、质量控制、安全管理、环保文明施工、资源配置、关键工序专项方案等）
- 资格文件分册必须为每类资质/证书/人员/业绩单独设章，不得合并为一个"资格材料"章节
- 企业产品库有资产时，技术标必须为主要产品/设备设置专项技术参数响应章节

### 章节大纲数量与字数分配的关系

章节数量直接影响每章分配到的目标字数。章节太少会导致单章目标字数过高（超出模型单次输出能力），从而出现实际字数远低于目标的情况。

| 场景 | 章节数 | 技术标目标字数 | 单章平均字数 | 可达性 |
| --- | ---: | ---: | ---: | --- |
| 规则版骨架（旧） | ~25 | 56,000 | ~4,500 | 部分章节超出模型能力 |
| AI 精细化版（新） | 40-60 | 56,000 | ~1,200 | 每章可达 |

后端接口：

```text
GET  /api/bidding/interpretations/{project_id}/bid-outline/stream   # SSE 流式生成（推荐）
POST /api/bidding/interpretations/{project_id}/bid-outline           # 同步生成
```

核心代码：

| 文件 | 说明 |
| --- | --- |
| `backend/ai/chapter_planner.py` | 两阶段大纲生成、`_fetch_knowledge_context()`、`_build_prompt()`、SSE 流式推送 |
| `backend/ai/bid_writing_plan.py` | 单章写作计划推导（重要性、字数区间、策略） |
