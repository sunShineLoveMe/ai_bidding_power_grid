# 电网行业标书系统：多租户改造调研报告

> 对象：从现有水利单租户系统 → 电网行业 AI 标书系统的迁移与多租户规划
> 时间：2026-05
> 范围：租户模型、表结构、迁移节奏、阿里云部署可扩展性、系统易用性
> 目标客户：给电网公司（国网/南网/地方电网）投标的**设备供应商 / 工程承包商 / 服务商**
> 租户模型：**一个企业 = 一个账号**，简单直接

---

## 1. 结论先行

- **多租户模型**：**一个企业一个账号**，注册即用，登录即进入自己的数据空间。不做多人协作、不做 RBAC、不做成员管理。
- **知识库隔离**：每个企业账号拥有独立的知识库，数据通过 `enterprise_id` 字段严格隔离。
- **实施节奏**：推荐 **两期走，不一步到位 SaaS**：
  - **一期（建议 6～8 周）**：基于当前系统做 **"行业参数化单租户版"**，产出电网单租户产品，同时把代码中的"水利"硬编码抽成"行业 Profile"。
  - **二期（建议 8～10 周）**：在一期干净的行业参数化基础上加 **enterprise_id 全链路**、注册登录、对象存储隔离、阿里云部署，交付 SaaS。
- **阿里云部署目标架构**：RDS PostgreSQL + pgvector / OSS / ECS / DashScope。见第 6 节。

---

## 2. 当前系统现状盘点

### 2.1 数据表租户化现状

| 表 | 主键 | 是否带 enterprise 字段 | 备注 |
| --- | --- | --- | --- |
| `bid_projects` | id | ❌ 无 | 项目级隔离不存在 |
| `bid_sections` | id, project_id | ❌ 仅靠 project_id 间接 | 通过 project 外键级联 |
| `knowledge_documents` | id | ❌ 无 | **企业知识库所有企业共享** |
| `knowledge_assets` | id | ❌ 无（有 `industry` 字段，默认 "水利行业"） | 同上 |
| `document_chunks` | id, document_id | ❌ 无 | 向量检索全库扫描 |
| `app_users` | id, fingerprint_id | ❌ 无 | 单机版浏览器指纹，非真实账号 |
| `onlyoffice_documents` | id, document_key | ❌ 仅关联 project_id | |
| `bid_export_tasks` / `bid_generation_tasks` | id, project_id | ❌ 仅关联 project_id | |

**关键判断**：当前表结构是**纯单租户**。所有"企业知识库"的资产在同一个 Supabase bucket `knowledge-assets` 下的同一个命名空间里，没有任何强隔离。

### 2.2 业务硬编码现状

- `backend/core/config.py` 的 `DEFAULT_SETTINGS` 里写死了水利企业画像 7 字段。
- `runtime_settings.json` 是**全局单实例文件**，没有 per-enterprise 概念。
- 硬编码"水利"关键词分布在 10 个文件、18+ 个注入点（详见附录）。

### 2.3 知识库内容绑定

`rag_seed/`、`tender_references/`、`assets/` 下的种子数据全是水利语料。**电网行业需要一套完全不同的种子库**。

### 2.4 存储与上传

- 上传目录 `uploads/` 是单目录，没有按企业分层
- Supabase Storage `knowledge-assets` bucket 路径是 `{document_id}/{filename}`
- 导出输出 `outputs/` 同样单目录

---

## 3. 多租户模型设计

### 模型：一个企业 = 一个账号

```
enterprises (企业账号表)
  ├── id (uuid, PK)
  ├── name (企业名称)
  ├── phone / email (登录凭证)
  ├── password_hash
  ├── industry_key (water / power_grid)
  ├── enterprise_profile (jsonb, 企业画像 7 字段)
  ├── status (active / suspended)
  ├── created_at
  └── updated_at

所有业务表加 enterprise_id：
  bid_projects.enterprise_id → enterprises.id
  knowledge_documents.enterprise_id → enterprises.id
  knowledge_assets.enterprise_id → enterprises.id
  document_chunks 通过 knowledge_documents 间接隔离
  bid_sections 通过 bid_projects 间接隔离
  bid_export_tasks / bid_generation_tasks 通过 bid_projects 间接隔离
```

**设计原则**：

1. **注册即用**：企业填写手机号/邮箱 + 密码 + 企业名称，注册完直接进入工作台
2. **登录即隔离**：后端从 JWT 取出 `enterprise_id`，所有查询自动带 `WHERE enterprise_id = ?`
3. **不做多人协作**：一个企业一套登录凭证，企业内部谁用谁登录，系统不管
4. **不做 RBAC**：没有角色、没有权限分级、没有成员邀请
5. **知识库完全隔离**：A 企业的知识库资产、向量检索结果对 B 企业完全不可见

**优点**：

- 实现简单，只需要一张 `enterprises` 表 + 业务表加 `enterprise_id` 列
- 用户心智简单：注册 → 登录 → 用，没有"选企业""切换企业"的概念
- 数据边界清晰：一个账号 = 一家企业 = 一份数据
- 后期如果需要多人协作，可以在 `enterprises` 下面加 `members` 表，不影响现有结构

**后期扩展预留**：

- 如果未来需要多人协作，只需加一张 `enterprise_members` 表，把登录凭证从 `enterprises` 表拆到 `accounts` 表，现有 `enterprise_id` 隔离逻辑完全不用动
- 如果未来需要代理机构管理多家企业，同样只需加关系表

---

## 4. 实施节奏：一步到位 SaaS vs 分两期

### 选项 1：一步到位 SaaS（不推荐）

**工作项**：

1. 新增 `enterprises` 表 + 注册登录
2. 所有业务表增加 `enterprise_id` 字段 + 回填
3. 所有 API 加 enterprise 中间件
4. 所有业务代码层加 enterprise 过滤
5. 重写认证层（JWT）
6. Storage 按 enterprise 分层
7. 知识库按 enterprise 隔离，pgvector 检索加 enterprise 过滤
8. 硬编码"水利"统一抽成行业 profile
9. 前端加注册/登录页面
10. 迁移到阿里云：RDS、OSS、ECS、域名、备案
11. 做电网行业 prompt / 种子库

**问题**：

- 11 项耦合工作一起上线，任何一处出 bug 都拖垮进度
- 首个电网客户需要的是**可用的电网标书产品**，不是 SaaS 平台
- 行业 prompt 没验证过就上多租户，出问题难定位是行业问题还是隔离问题

### 选项 2：两期走（推荐）

#### 一期（6～8 周）：行业参数化单租户版，交付首个电网客户

**目标**：在不引入 enterprise_id 的前提下，让系统能配成"电网版"交付。

**核心工作**：

1. **行业 Profile 抽象**（**最重要**）：
   - 新增 `backend/core/industry.py`，定义 `IndustryProfile` 数据结构
   - 包含：`industry_key`、`expert_persona`、`domain_keywords`、`chapter_query_prefix`、`compliance_domain_clause`、`default_enterprise_profile`、`rag_system_prompt`、`out_of_scope_reply`
   - 配置文件放 `config/industry_profiles/{water.json, power_grid.json}`
   - `runtime_settings.json` 加 `industry_key` 字段切换行业
   - 代码里 10 个文件 18+ 处硬编码"水利"全部改成 profile 调用
2. **企业画像 per-project 化**：从全局 runtime_settings 挪到 `bid_projects.metadata.enterprise_profile`，为二期 enterprise 化铺路
3. **知识库 industry 字段强化**：`knowledge_documents` 补 `industry` 字段，RAG 检索按 `industry_key` 过滤
4. **电网行业内容建设**：电网 prompt 调优 + 电网种子库 + 电网图片资产样张
5. **交付**：打包给首个电网客户做单租户部署

**验收标准**：电网客户能正常跑完 招标解读 → 大纲 → 正文 → 合规 → 导出 全流程。

#### 二期（8～10 周）：多租户 + 阿里云 SaaS

**前提**：一期行业 profile 已跑通；首客户已交付。

**核心工作**：

1. **企业账号表**：
   - 建 `enterprises` 表（id / name / phone / email / password_hash / industry_key / enterprise_profile / status）
   - 注册接口：手机号 + 验证码 + 企业名称 + 密码
   - 登录接口：手机号/邮箱 + 密码 → 返回 JWT（payload 含 enterprise_id）
2. **所有业务表加 `enterprise_id`**：
   - `bid_projects`、`knowledge_documents`、`knowledge_assets` 加 `enterprise_id uuid not null` + 索引 + FK
   - `document_chunks` 通过 `knowledge_documents.enterprise_id` 间接隔离（检索 RPC 加 join 或冗余字段）
   - 其余表（bid_sections / export_tasks / generation_tasks）通过 `bid_projects.enterprise_id` 间接隔离
   - 回填脚本：老数据打到"默认企业"
3. **API 中间件**：
   - 每个请求从 JWT 取 `enterprise_id`
   - 注入到所有 DB 查询的 WHERE 条件
   - 无 token 或 token 过期返回 401
4. **对象存储按企业隔离**：
   - Supabase Storage → 阿里云 OSS
   - 路径改为 `{enterprise_id}/{document_id}/{filename}`
5. **pgvector 检索带 enterprise 过滤**：
   - `match_knowledge_assets` / `match_document_chunks` RPC 加 `filter_enterprise_id` 参数
   - 或在 `document_chunks` 表冗余 `enterprise_id` 字段（推荐，避免 join 影响向量检索性能）
6. **前端**：
   - 新增注册页、登录页
   - 登录后直接进入工作台（不需要"选企业"步骤）
   - 设置页加"企业信息"编辑（企业名称、画像 7 字段）
7. **阿里云部署**：RDS + pgvector、OSS、ECS、SLB、域名、HTTPS、ICP 备案
8. **计费准备**：`ai_usage_tracking` 加 `enterprise_id`，按企业统计用量

**验收标准**：多家企业在同一套 SaaS 实例上注册使用，数据严格隔离；pgvector 检索不会把 A 企业的资产召回给 B 企业。

### 节奏建议

```
Week 0-2   ─ 一期行业 Profile 抽象 + 企业画像 per-project
Week 2-5   ─ 一期电网 prompt / 种子库建设
Week 5-7   ─ 一期首个电网客户联调 + 上线
Week 7-8   ─ 一期验收 & 复盘
  【一期交付里程碑：电网单租户部署】
Week 8-11  ─ 二期 enterprises 表 + 注册登录 + enterprise_id 全链路
Week 11-14 ─ 二期 Storage/pgvector 隔离 + 前端登录注册
Week 14-17 ─ 二期阿里云迁移 + SaaS 上线
  【二期交付里程碑：电网行业多租户 SaaS】
```

---

## 5. 为什么不推荐"一步到位"

1. **风险集中爆发**：新行业 + 多租户 + 新部署环境三件事合在一起，出问题难定位
2. **首客户价值错位**：首客户买的是"能用的电网标书系统"，不是 SaaS 平台
3. **行业抽象没验证过**：先做租户再做行业抽象，等于在不稳的地基上盖二楼
4. **阿里云迁移有独立工作量**：Supabase → RDS+OSS 本身 2～3 周，和多租户混在一起出问题难排查

分两期的好处：
- 一期把首客户变现，有正反馈
- 一期沉淀的"行业 profile"二期直接复用
- 二期边界清楚：隔离 + 账号 + 阿里云

---

## 6. 阿里云部署目标架构

| 组件 | 现状（Supabase） | 阿里云对应 | 备注 |
| --- | --- | --- | --- |
| 关系数据库 | Supabase PostgreSQL 15 | **RDS PostgreSQL 15** + pgvector 插件 | 2C4G 起步 |
| 向量检索 | pgvector | pgvector on RDS | 初期够用，量大再迁 AnalyticDB |
| 对象存储 | Supabase Storage | **OSS** + 私有 Bucket | 路径 `{enterprise_id}/...` |
| 身份认证 | 无（浏览器指纹） | 自建 JWT（手机号 + 密码） | 简单够用 |
| 计算 | 本地 Flask + Vite | **ECS + Nginx** | 初期 ECS 简单 |
| LLM | DeepSeek + DashScope | 保持不变 | DashScope 本身就是阿里云服务 |
| OnlyOffice | 本地容器 | ECS 上自建 | |
| 文件解析 | 本地 MinerU | 同上部署到 ECS | |
| 日志/监控 | 无 | **SLS + ARMS** | 按 enterprise_id 打标 |

**关键点**：

- **SaaS 与私有部署并存**：大客户可能要求私有部署。系统设计上保持 `single_tenant` 模式开关——关闭注册登录，直接进入工作台，和一期产物一致。
- **数据合规**：客户的招标文件、报价含商业敏感信息，存储选国内节点。
- **隔离策略**：应用层中间件为主（从 JWT 取 enterprise_id，注入所有查询），DB 层 RLS 为辅（兜底防漏）。

---

## 7. 二期表结构设计（简化版）

```sql
-- 企业账号表（一个企业 = 一个账号）
create table enterprises (
  id uuid primary key default gen_random_uuid(),
  name text not null,                    -- 企业名称
  phone text unique,                     -- 手机号（登录凭证）
  email text unique,                     -- 邮箱（备用登录凭证）
  password_hash text not null,           -- bcrypt 哈希
  industry_key text not null default 'power_grid',  -- 行业
  enterprise_profile jsonb not null default '{}',   -- 企业画像 7 字段
  status text not null default 'active', -- active / suspended
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- bid_projects 加 enterprise_id
alter table bid_projects
  add column enterprise_id uuid not null references enterprises(id) on delete cascade;
create index idx_bid_projects_enterprise on bid_projects(enterprise_id);

-- knowledge_documents 加 enterprise_id
alter table knowledge_documents
  add column enterprise_id uuid not null references enterprises(id) on delete cascade;
create index idx_knowledge_documents_enterprise on knowledge_documents(enterprise_id);

-- knowledge_assets 加 enterprise_id
alter table knowledge_assets
  add column enterprise_id uuid not null references enterprises(id) on delete cascade;
create index idx_knowledge_assets_enterprise on knowledge_assets(enterprise_id);

-- document_chunks 冗余 enterprise_id（避免向量检索 join）
alter table document_chunks
  add column enterprise_id uuid references enterprises(id) on delete cascade;
create index idx_document_chunks_enterprise on document_chunks(enterprise_id);

-- ai_usage_tracking 加 enterprise_id
alter table ai_usage_tracking
  add column enterprise_id uuid references enterprises(id) on delete set null;
create index idx_ai_usage_tracking_enterprise on ai_usage_tracking(enterprise_id);
```

**向量检索 RPC 改造**：

```sql
-- match_document_chunks 加 enterprise 过滤
create or replace function match_document_chunks(
  query_embedding vector(1024),
  match_count int default 8,
  filter_enterprise_id uuid default null
)
returns table (...) as $$
  select ...
  from document_chunks dc
  where dc.embedding is not null
    and (filter_enterprise_id is null or dc.enterprise_id = filter_enterprise_id)
  order by dc.embedding <=> query_embedding
  limit match_count;
$$;
```

---

## 8. 风险与应对

| 风险 | 严重度 | 应对 |
| --- | --- | --- |
| 行业 profile 抽象不全，二期还要补硬编码 | 中 | 一期完成后 grep 扫描，形成基线清单 |
| 电网业务复杂度高于预估 | 高 | 一期先拿到 3～5 份真实电网招标文件验证 |
| 二期迁移 Supabase → RDS，RPC 语法差异 | 中 | 提前在 RDS 上验证 match_* 函数 |
| 多租户 pgvector 检索性能下降 | 中 | document_chunks 冗余 enterprise_id + 复合索引 |
| 租户隔离疏漏导致数据串库 | **高** | 应用层中间件 + DB RLS 双层；上线前跨租户渗透测试 |
| 电网种子库收集不全 | 中 | 一期内容团队并行工作 |

---

## 9. 落地决定建议

1. **多租户模型**：**一个企业一个账号**，简单直接，不做多人协作和权限。
2. **实施节奏**：**分两期**。一期交付"电网单租户部署"，二期交付"电网行业多租户 SaaS + 阿里云"。
3. **一期最关键的动作**：把"水利"相关的 10+ 处硬编码抽象为**行业 Profile**。
4. **二期最关键的动作**：`enterprise_id` 全链路 + 注册登录 + OSS 按企业分层。
5. **产品形态**：长期保持"私有部署单租户"和"SaaS 多租户"双形态并存（`single_tenant` 模式开关）。

---

## 10. 一期、二期具体开发任务清单

### 一期

- [ ] 设计 `IndustryProfile` 数据结构，放 `backend/core/industry.py`
- [ ] 新增 `config/industry_profiles/water.json`、`power_grid.json`
- [ ] `runtime_settings.json` 增加 `industry_key` 字段
- [ ] 扫描并替换硬编码"水利"（10 个文件 18+ 处）
- [ ] 企业画像 7 字段从 runtime_settings 挪到 per-project
- [ ] `knowledge_documents` 表增加 `industry` 字段 + 索引
- [ ] RAG 检索 RPC 增加 `filter_industry` 参数
- [ ] 前端设置页加"行业选择"和"企业画像"表单
- [ ] 电网 prompt 调优 + 电网种子库建设 + 电网图片资产采集
- [ ] 首个电网客户联调验收

### 二期

- [ ] 建 `enterprises` 表
- [ ] 注册接口（手机号 + 验证码 + 企业名称 + 密码）
- [ ] 登录接口（手机号/邮箱 + 密码 → JWT）
- [ ] API 中间件：从 JWT 取 enterprise_id，注入所有查询
- [ ] `bid_projects` / `knowledge_documents` / `knowledge_assets` 加 `enterprise_id`
- [ ] `document_chunks` 冗余 `enterprise_id`
- [ ] 历史数据回填脚本
- [ ] pgvector RPC 加 enterprise 过滤
- [ ] 对象存储路径按 enterprise 分层（OSS）
- [ ] 前端注册页、登录页
- [ ] 前端设置页"企业信息"编辑
- [ ] Supabase → RDS + OSS 迁移
- [ ] 阿里云 ECS 部署、域名、HTTPS、ICP 备案
- [ ] `ai_usage_tracking` 加 `enterprise_id`，按企业统计用量
- [ ] `single_tenant` 模式开关（私有部署时关闭注册登录）
- [ ] **运营管理后台**（独立 `/admin` 路由，管理员账号登录）：
  - [ ] 企业账号列表（名称、手机号、注册时间、最近活跃、状态）
  - [ ] 停用/启用企业账号
  - [ ] 手动重置企业密码
  - [ ] 企业用量统计（AI 调用次数、Token 消耗、项目数）
  - [ ] 全局数据看板（总企业数、日活、总项目数、总 AI 用量/成本）
  - [ ] 查看某企业的项目列表（只读，排查问题用）
  - [ ] 公告/通知管理（系统维护、版本更新通知）

---

## 11. 一期启动前：客户需提供的资料清单

一期的核心是"让系统能跑通电网行业全流程"，这依赖于电网行业的真实业务素材。以下资料需要客户在项目启动前或启动后 2 周内提供，否则会阻塞 prompt 调优和种子库建设。

### 11.1 必须提供（阻塞开发）

#### A. 电网招标文件样本（3～5 份）

| 序号 | 资料名称 | 用途 | 要求 |
| --- | --- | --- | --- |
| 1 | 国网/南网真实招标文件 PDF（完整版） | 验证招标解读流程、评分规则提取、分册拆分逻辑 | 至少 3 份不同品类（如输变电设备、电缆、施工服务），可脱敏但结构完整 |
| 2 | 招标文件中的评分标准/评分细则部分 | 训练评分项提取和章节映射 | 如果招标文件太大，可单独提供评分标准截取 |
| 3 | 招标文件中的资格审查条件部分 | 训练资格项提取和废标风险识别 | 同上 |

#### B. 中标标书样本（2～3 份）

| 序号 | 资料名称 | 用途 | 要求 |
| --- | --- | --- | --- |
| 4 | 客户企业历史中标标书（技术标部分） | 作为正文生成的参考范本，训练电网行业写作风格 | 可脱敏金额/人名，但章节结构和正文内容要完整 |
| 5 | 客户企业历史中标标书（商务标部分） | 同上 | 同上 |
| 6 | 客户企业历史中标标书（资格文件部分） | 了解电网行业资格文件的组成和格式 | 同上 |

#### C. 企业资质与画像信息

| 序号 | 资料名称 | 用途 | 要求 |
| --- | --- | --- | --- |
| 7 | 企业基本信息（名称、注册地、经营范围、主营业务） | 配置企业画像 7 字段 | 文字即可 |
| 8 | 企业资质证书清单（电力施工资质、承装承修承试许可证等级、ISO 体系证书等） | 知识库种子数据 + 资格文件生成 | 提供证书名称和等级即可，不需要原件扫描 |
| 9 | 企业核心业绩清单（近 3～5 年电网类中标项目） | 知识库种子数据 + 业绩章节生成 | 项目名称、合同金额、完成时间、甲方名称 |
| 10 | 主要人员信息（项目经理、技术负责人、安全员等的资质证书类型） | 人员配置章节生成 | 只需岗位 + 持证类型，不需要真实姓名 |

#### D. 标书模板与格式要求

| 序号 | 资料名称 | 用途 | 要求 |
| --- | --- | --- | --- |
| 11 | 客户常用的标书 Word 模板（.docx） | DOCX 导出时套用客户格式（页眉页脚、字体字号、封面样式） | 提供空白模板即可 |
| 12 | 电网招标文件中对投标文件格式的要求说明 | 确保导出格式合规（装订顺序、目录格式、页码要求等） | 从招标文件中截取相关段落 |

### 11.2 建议提供（提升效果，不阻塞开发）

#### E. 行业知识素材

| 序号 | 资料名称 | 用途 | 要求 |
| --- | --- | --- | --- |
| 13 | 电网行业常用标准/规范清单（如 DL/T、GB 系列） | RAG 知识库种子数据，正文引用标准时更准确 | 标准编号 + 标准名称列表即可 |
| 14 | 国网/南网供应商管理相关政策文件 | 了解电网招标特殊规则（如国网电子商务平台规则） | PDF 或截图 |
| 15 | 电网行业常见废标/否决投标情形汇总 | 合规检查和风险提示 | 如果客户有整理过最好，没有的话我们自行调研 |
| 16 | 客户企业的施工组织设计/技术方案范本 | 技术标正文生成的参考 | 任意一份历史项目的技术方案 |
| 17 | 客户企业的质量/安全/环保管理体系文件 | 管理体系章节生成的参考 | 体系手册或管理制度目录 |

#### F. 图片与附件素材

| 序号 | 资料名称 | 用途 | 要求 |
| --- | --- | --- | --- |
| 18 | 企业主要产品/设备图片（输变电设备、电缆、施工机械等） | 知识库图片资产，正文配图 | JPG/PNG，每类 2～3 张代表性图片 |
| 19 | 企业资质证书扫描件（可脱敏） | 知识库图片资产，资格文件配图 | 可打马赛克遮挡敏感信息 |
| 20 | 企业历史项目现场照片 | 业绩展示配图 | 如有 |
| 21 | 企业组织架构图 | 项目管理机构章节配图 | 如有 |

#### G. 竞品与行业参考

| 序号 | 资料名称 | 用途 | 要求 |
| --- | --- | --- | --- |
| 22 | 客户目前使用的标书编制工具或流程说明 | 了解客户痛点，优化产品体验 | 口头沟通即可 |
| 23 | 客户认为写得好的竞争对手标书（如有） | 了解行业标杆水平 | 可选 |

### 11.3 资料提供时间节点

| 时间 | 需要到位的资料 | 阻塞的工作 |
| --- | --- | --- |
| 项目启动前 | 7（企业基本信息）、11（Word 模板） | 企业画像配置、导出模板适配 |
| 启动后 1 周内 | 1～3（招标文件样本）、12（格式要求） | 招标解读 prompt 调优、分册逻辑验证 |
| 启动后 2 周内 | 4～6（中标标书样本）、8～10（资质/业绩/人员） | 正文生成 prompt 调优、知识库种子建设 |
| 启动后 3 周内 | 13～21（行业知识 + 图片素材） | RAG 知识库丰富度、图文配图效果 |
| 联调阶段 | 22～23（竞品参考） | 体验优化 |

### 11.4 资料脱敏说明

- 招标文件：可保留原样（招标文件本身是公开信息）
- 中标标书：建议脱敏处理——替换真实金额为"XXX 万元"、替换人名为"张某某"、替换合同编号为"XXXX-XXX"，但**保留章节结构和正文逻辑**
- 资质证书：可打马赛克遮挡证书编号和法人签名，保留证书类型和等级可见
- 业绩清单：金额可模糊为区间（如"500～1000 万"），项目名称和甲方名称建议保留（用于训练行业语境）

---

## 附录："水利"硬编码清单（一期改造基线）

| 文件 | 行号 | 内容类型 | 建议做法 |
| --- | --- | --- | --- |
| `backend/ai/interpreter.py` | 62 / 197 / 252 | 系统提示词 | 替换为 `profile.expert_persona` |
| `backend/ai/section_writer.py` | 275 | 正文撰写 prompt | 同上 |
| `backend/ai/qwen_client.py` | 670 | 通用投标撰写 prompt | 同上 |
| `backend/ai/chapter_planner.py` | 111 / 603 | 检索 query + 章节规划 prompt | `profile.chapter_query_prefix` / `profile.expert_persona` |
| `backend/api/compliance.py` | 89 | 合规补强 prompt | `profile.compliance_domain_clause` |
| `backend/api/legacy.py` | 65 / 137 / 189 | pre/post analysis prompt | `profile.expert_persona` |
| `backend/api/knowledge.py` | 175 / 202 / 305 | RAG 关键词 + 超范围回复 | `profile.domain_keywords` / `profile.out_of_scope_reply` |
| `backend/api/routes.py` | 467 / 574 | asset caption / alt | `profile.asset_default_category` |
| `backend/api/assets.py` | 160 | industry 默认值 | `profile.industry_label` |
| `backend/rag/retrieval.py` | 257 | RAG 问答系统提示词 | `profile.rag_system_prompt` |
| `backend/core/config.py` | 48-55 | 企业画像默认值 | `profile.default_enterprise_profile` |

共计 **10 个文件 / 18+ 个注入点**。
