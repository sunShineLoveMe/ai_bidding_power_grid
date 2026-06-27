# 2026-06-27 阿里云线上泰昌正式资产全流程浏览器回归

## 结论

阿里云测试环境 `http://8.160.187.226` 已完成真实 Chrome 链路回归，账号 `admin` 登录成功。企业知识库、企业产品库、企业资信库、知识库助手、6 类真实 `/api/knowledge/search/stream` 问答、技术标 DOCX 导出、商务标 DOCX 导出和下载文件 XML 审计均通过。

本轮重点检查的正式投标禁用表达在用户可见页面、真实问答输出和下载后的 DOCX 正文/页眉/页脚中均未命中：

```text
图示：、原图、页面_、asset_path、parsed_outputs、source_domain、target_library、
embedding、searchable_text、file_name、specs、taichang_、product_library、
qualification_library、/api/bidding/knowledge/assets
```

## 环境

| 项 | 值 |
| --- | --- |
| 线上地址 | `http://8.160.187.226` |
| 测试账号 | `admin` |
| 测试方式 | Chrome / Playwright 真实浏览器同源上下文 |
| 运行目录 | `docs/development/runs/run_20260627_aliyun_browser_full_regression/` |
| 后端健康检查 | `/api/health` 返回 `status=ok` |
| 备注 | `/api/health` 中 `branch/commit=unknown`，不影响功能验收；部署版本以服务器 `git log`、容器重建和线上行为为准 |

## 页面与问答回归

| 验证项 | 结果 |
| --- | --- |
| 登录页访问与登录 | PASS，`/api/users/login` 返回 200，用户 `admin` |
| 企业知识库页面 | PASS，截图 `02_knowledge_page.png`，禁用字段命中 0 |
| 企业产品库页面 | PASS，截图 `product_page.png`，禁用字段命中 0 |
| 企业资信库页面 | PASS，截图 `qualification_page.png`，禁用字段命中 0 |
| 知识库助手 CPVC 参数问答 | PASS，截图 `03_assistant_cpvc.png`，禁用字段命中 0 |
| CPVC 检验报告参数 stream | PASS，HTTP 200，禁用字段命中 0 |
| MPP 检验报告 stream | PASS，HTTP 200，禁用字段命中 0 |
| 生产制造能力 stream | PASS，HTTP 200，禁用字段命中 0 |
| 试验检测设备 stream | PASS，HTTP 200，禁用字段命中 0 |
| 资质证书 stream | PASS，HTTP 200，禁用字段命中 0 |
| 绿色低碳资料 stream | PASS，HTTP 200，禁用字段命中 0 |

原始浏览器回归记录：`summary.json`。

## DOCX 导出回归

真实项目：

```text
580b8c82-42c2-4a51-a0d2-17b60afa22b9
国家电网有限公司2026年西北、西藏区域第一次联合采购10kV电力电缆、架空绝缘导线协议库存公开招标采购项目
```

| 分册 | 任务 | 结果 |
| --- | --- | --- |
| 技术标 | `b42be69d-5ea1-4050-8b2d-629603a1eff8` | completed |
| 商务标 | `1acdcae6-8239-4f78-80c6-a5cd030285a3` | completed |

导出结果：

| 分册 | 文件 | 图片候选/插入/失败/跳过 | 字段刷新 | DOCX XML 禁用词 |
| --- | --- | ---: | --- | --- |
| 技术标 | `泰昌_SL265A_技术投标文件_20260627_图文.docx` | 26 / 24 / 0 / 2 | `refreshed`，`returncode=0` | 0 |
| 商务标 | `泰昌_SL265A_商务投标文件_20260627_图文.docx` | 24 / 24 / 0 / 0 | `refreshed`，`returncode=0` | 0 |

下载文件：

- `docs/development/runs/run_20260627_aliyun_browser_full_regression/aliyun_technical_export.docx`
- `docs/development/runs/run_20260627_aliyun_browser_full_regression/aliyun_business_export.docx`

文件级核验命令：

```bash
for f in docs/development/runs/run_20260627_aliyun_browser_full_regression/aliyun_*_export.docx; do
  unzip -p "$f" 'word/*.xml' 2>/dev/null \
    | rg -n '图示：|原图|页面_|asset_path|parsed_outputs|source_domain|target_library|embedding|searchable_text|file_name|specs|taichang_|product_library|qualification_library|/api/bidding/knowledge/assets' || true
done
```

输出为空，表示正文、页眉、页脚 XML 均未出现禁用表达。

## 边界说明

- 线上当前项目正式检查仍有 12 个阻断项，因此技术标和商务标导出模式均为 `draft`。这说明正式门禁正常工作，未因本次资产清理绕过客户确认项。
- 技术标任务 metadata 中 `image_conversion.captions.samples.source` 仍保留旧题注作为审计追溯；实际写入 DOCX 的 `caption` 已正式化为 `资料：MPP电缆保护管检验报告` 等中文表达。追溯字段只留在 metadata，不进入正式 Word 正文。
- 技术标导出任务提示当前招标包物料与泰昌 CPVC/MPP 资料不匹配，`T-000` 继续阻断正式导出，这是符合真实投标场景的风险控制。

## 结论

阿里云测试环境的泰昌正式资料资产中文化、RAG 问答展示、产品库/资信库页面展示和技术/商务分册 DOCX 图文导出主链路已通过真实浏览器回归。本轮问题可以在阿里云测试环境关闭；后续进入生产前仍需保留正式检查阻断项，不得把当前新疆 10kV 导线包作为泰昌 CPVC/MPP 正式投标成稿直接提交。
