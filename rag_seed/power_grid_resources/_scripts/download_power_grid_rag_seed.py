#!/usr/bin/env python3
"""Download and assemble a power-grid bidding RAG seed corpus.

The corpus focuses on public government, National Energy Administration,
State Grid, and public procurement/transaction sources. Public PDFs are kept
as-is; HTML pages are converted to lightweight Markdown for RAG ingestion.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import ssl
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover
    BeautifulSoup = None


ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


SOURCES = [
    {
        "category": "02_policy_regulations",
        "title": "中华人民共和国招标投标法",
        "url": "https://www.moe.gov.cn/jyb_xwfb/xw_zt/moe_357/s3581/moe_2698/moe_2825/tnull_53734.html",
        "source_org": "中华人民共和国教育部政府门户网站转载",
        "doc_type": "法律",
        "tags": "招标投标,上位法,招标,投标,开标,评标,中标",
    },
    {
        "category": "02_policy_regulations",
        "title": "中华人民共和国招标投标法实施条例",
        "url": "https://www.gov.cn/gongbao/content/2019/content_5468831.htm",
        "source_org": "中国政府网/国务院公报",
        "doc_type": "行政法规",
        "tags": "招标投标,资格预审,评标,否决投标,投诉处理",
    },
    {
        "category": "02_policy_regulations",
        "title": "必须招标的工程项目规定",
        "url": "https://www.ndrc.gov.cn/fzggw/jgsj/fgs/sjdt/201803/W020190910481507889431.pdf",
        "source_org": "国家发展改革委",
        "doc_type": "部门规章PDF",
        "tags": "必须招标,工程项目,规模标准,能源项目",
    },
    {
        "category": "02_policy_regulations",
        "title": "必须招标的基础设施和公用事业项目范围规定",
        "url": "https://www.ccgp.gov.cn/zcfg/bwfile/201806/t20180612_10082983.htm",
        "source_org": "中国政府采购网/国家发展改革委",
        "doc_type": "规范性文件",
        "tags": "必须招标,基础设施,公用事业,电力,新能源",
    },
    {
        "category": "02_policy_regulations",
        "title": "中华人民共和国电力法",
        "url": "https://www.yantai.gov.cn/api-gateway/jpaas-web-server/front/document/file-download?fileUrl=/cms_files/jcms1/web1/site/attach/0/af275af37e4743c18db3091daaa791e4.pdf",
        "source_org": "烟台市政府门户网站公开附件",
        "doc_type": "法律PDF",
        "tags": "电力建设,电力供应,电力设施保护,电力监督",
    },
    {
        "category": "02_policy_regulations",
        "title": "中华人民共和国能源法",
        "url": "https://www.nea.gov.cn/2024-11/09/c_1310787187.htm",
        "source_org": "国家能源局转载中国人大网",
        "doc_type": "法律",
        "tags": "能源,电力,新型能源体系,能源安全,绿色低碳",
    },
    {
        "category": "02_policy_regulations",
        "title": "电力建设工程施工安全监督管理办法",
        "url": "https://prpq.nea.gov.cn/uploads/file1/20180115/5a5c044624508.pdf",
        "source_org": "国家能源局电力可靠性管理和工程质量监督中心",
        "doc_type": "部门规章PDF",
        "tags": "电力建设,施工安全,招标文件,安全生产费用,分包管理",
    },
    {
        "category": "02_policy_regulations",
        "title": "电力建设工程质量监督管理暂行规定",
        "url": "https://zfxxgk.nea.gov.cn/2023-05/31/c_1310725750.htm",
        "source_org": "国家能源局",
        "doc_type": "规范性文件",
        "tags": "电力建设,质量监督,质监机构,工程质量",
    },
    {
        "category": "02_policy_regulations",
        "title": "电力建设工程备案管理规定",
        "url": "https://zfxxgk.nea.gov.cn/auto79/201307/t20130708_1650.htm",
        "source_org": "国家能源局",
        "doc_type": "规范性文件",
        "tags": "电力建设,备案,招标时间,招标文件编号,施工合同",
    },
    {
        "category": "02_policy_regulations",
        "title": "关于全面推行电力工程施工监理招投标工作的通知",
        "url": "https://www.nea.gov.cn/2012-01/04/c_131262641.htm",
        "source_org": "国家能源局",
        "doc_type": "行业招投标文件",
        "tags": "电力工程,施工招标,监理招标,招标文件内容,评标办法",
    },
    {
        "category": "02_policy_regulations",
        "title": "电力工程设计招标投标管理规定",
        "url": "https://www.nea.gov.cn/2011-11/22/c_131262644.htm",
        "source_org": "国家能源局",
        "doc_type": "行业招投标文件",
        "tags": "电力工程,设计招标,资格条件,评标办法,设计投标",
    },
    {
        "category": "03_standards_specs",
        "title": "电力建设工程现行管理文件及技术标准名录2019版",
        "url": "https://prpq.nea.gov.cn/uploads/file1/20240313/65f166e0071c3.pdf",
        "source_org": "国家能源局电力可靠性管理和工程质量监督中心",
        "doc_type": "标准目录PDF",
        "tags": "电力建设,技术标准,质量监督,施工管理,输变电,火电,水电",
    },
    {
        "category": "01_tender_documents",
        "title": "国网江苏苏州供电分公司授权物资竞争性谈判采购公告示例一",
        "url": "https://bid.js.sgcc.com.cn/hyzb/zxylFile/fd44f2d631ce4a7ab03016dc99f1acce/fd44f2d631ce4a7ab03016dc99f1acce.html",
        "source_org": "国网江苏省电力工程咨询有限公司地市采购代理平台",
        "doc_type": "国网采购公告",
        "tags": "国家电网,ECP2.0,竞争性谈判,供应商注册,CA证书,采购文件",
    },
    {
        "category": "01_tender_documents",
        "title": "国网江苏苏州供电分公司授权物资竞争性谈判采购公告示例二",
        "url": "https://bid.js.sgcc.com.cn/hyzb/zxylFile/fb8ca97ff9674fd4bd0ec92a571f8f71/fb8ca97ff9674fd4bd0ec92a571f8f71.html",
        "source_org": "国网江苏省电力工程咨询有限公司地市采购代理平台",
        "doc_type": "国网采购公告",
        "tags": "国家电网,物资采购,资格要求,供应商不良行为,信用中国,二轮报价",
    },
    {
        "category": "01_tender_documents",
        "title": "国网江苏集体企业采购公开竞争性谈判公告示例",
        "url": "https://bid.js.sgcc.com.cn/jtqyzb/zxylFile/80bd6d6ce74a4d22bffebd591d7db05d/80bd6d6ce74a4d22bffebd591d7db05d.html",
        "source_org": "江苏兴力工程管理有限公司集体企业采购代理系统",
        "doc_type": "国网采购公告",
        "tags": "国家电网,电工交易专区,ETP,采购公告,资格要求,应答文件",
    },
    {
        "category": "01_tender_documents",
        "title": "秭归磨坪35kV输变电工程竣工环境保护验收调查报告",
        "url": "https://www.hb.sgcc.com.cn/html/files/2023-02/16/20230216144537638129512.pdf",
        "source_org": "国网湖北省电力有限公司",
        "doc_type": "输变电工程公开报告PDF",
        "tags": "35kV,输变电工程,招投标管理,施工,监理,验收,环保",
    },
    {
        "category": "01_tender_documents",
        "title": "湖北咸宁赤壁500kV输变电工程竣工环境保护验收调查报告",
        "url": "https://www.hb.sgcc.com.cn/html/files/2025-01/13/20250113151349148768737.pdf",
        "source_org": "国网湖北省电力有限公司",
        "doc_type": "输变电工程公开报告PDF",
        "tags": "500kV,输变电工程,变电站,线路工程,环保验收,项目参建单位",
    },
    {
        "category": "01_tender_documents",
        "title": "襄阳谷城筑阳110kV输变电工程竣工环境保护验收调查报告",
        "url": "https://www.hb.sgcc.com.cn/html/files/2025-12/02/20251202103022845442783.pdf",
        "source_org": "国网湖北省电力有限公司",
        "doc_type": "输变电工程公开报告PDF",
        "tags": "110kV,输变电工程,变电站,线路工程,环保验收,固废管理",
    },
    {
        "category": "01_tender_documents",
        "title": "重庆国网招投标网站说明",
        "url": "https://www.cq.sgcc.com.cn/html/main/col44/2020-11/17/20201117162345027652716_1.html",
        "source_org": "国网重庆市电力公司",
        "doc_type": "国网招投标入口说明",
        "tags": "国家电网,招投标网站,设计,施工,监理,电能表,特高压,信息化",
    },
]


GENERATED_DOCS = {
    "03_standards_specs/power_grid_standards_catalog.md": """# 国网电力投标常用标准规范目录

> 说明：国家标准、行业标准和国网企业标准全文通常存在版权边界，本文件只整理名称、适用场景、投标引用方式和 RAG 入库建议，不收录来源不明或付费平台搬运的全文。

## 招标采购与合同合规

- 《中华人民共和国招标投标法》及《中华人民共和国招标投标法实施条例》：用于判断公开招标、邀请招标、资格预审、投标保证金、评标委员会、否决投标、投诉处理等基础合规。
- 《必须招标的工程项目规定》《必须招标的基础设施和公用事业项目范围规定》：电力、新能源等能源基础设施项目的必须招标范围与规模标准依据。
- 国家电网 ECP2.0 / 电工交易专区公开采购公告：用于学习国网采购公告结构、供应商注册、CA 证书、离线投标工具、二轮报价、资格审查、应答保证金等实际流程。

## 电力建设质量安全

- 《电力建设工程施工安全监督管理办法》：投标文件中安全生产体系、安全生产费用、分包管理、施工组织设计、专项方案、应急预案、监理安全职责的核心依据。
- 《电力建设工程质量监督管理暂行规定》：质量监督手续、质监机构、质量监督检查、整改闭环、质量监督报告等内容的依据。
- 《建设工程质量管理条例》《建设工程安全生产管理条例》：工程质量责任、安全生产责任、材料设备质量、施工单位和监理单位责任的上位法规。

## 输变电工程技术文件

- 《电力建设工程现行管理文件及技术标准名录》：作为技术标准检索入口，优先按输变电工程、变电工程、线路工程、电缆工程、通信自动化、监理监造、质量监督分类切片入库。
- GB/T 50326《建设工程项目管理规范》：施工组织、项目管理机构、进度质量成本安全环保协调。
- GB/T 50430《工程建设施工企业质量管理规范》：施工企业质量管理体系、材料设备采购、过程控制、检查验收。
- GB/T 50319《建设工程监理规范》及 DL/T 5434《电力建设工程监理规范》：监理规划、监理实施细则、旁站、见证、验收和资料管理。

## 国网企业技术体系引用

- 国家电网输变电工程通用设计、通用设备、标准工艺、典型设计、施工工艺示范手册等材料，投标中可作为“执行国网标准化建设要求、落实标准工艺和质量通病防治”的依据。
- 对企业标准 Q/GDW 等资料，建议只入库自有合法持有版本或官方公开目录；投标生成时优先引用标准名称、编号、适用范围和企业承诺，不输出大段标准原文。
""",
    "04_standard_phrases/power_grid_section_library.md": """# 国网电力投标章节库

## 资格响应

- 企业资质：电力工程施工总承包、输变电工程专业承包、承装（修、试）电力设施许可证、安全生产许可证、质量/环境/职业健康安全管理体系认证。
- 人员配置：项目经理、技术负责人、安全负责人、质量负责人、资料员、材料员、特种作业人员、电工、高处作业、起重指挥等岗位证书。
- 业绩证明：同电压等级或相近电压等级输变电工程、变电站工程、线路工程、电缆工程、配网工程、通信自动化工程合同、中标通知书、竣工验收或投运证明。

## 商务响应

- 投标有效期、投标保证金、履约担保、工期、质量标准、安全目标、缺陷责任期、付款条件和税率应逐项响应采购文件。
- 对国网采购公告中的 ECP2.0、ETP、CA 证书、电子应答文件、二轮报价、离线投标工具和澄清补遗要求，应在投标流程章节中明确专人负责、节点校验和备份机制。

## 技术响应

- 变电站土建：场地平整、基础施工、主体结构、设备基础、电缆沟、接地网、消防、给排水、道路围墙、站区绿化和文明施工。
- 变电电气安装：主变压器、GIS/HGIS、断路器、隔离开关、互感器、避雷器、母线、电缆敷设、二次接线、保护测控、通信自动化和整组调试。
- 输电线路：复测分坑、基础开挖浇筑、杆塔组立、架线放线、跨越施工、接地、附件安装、验收消缺。
- 配网/电缆：电缆沟排管、顶管拖管、电缆敷设、终端中间接头、试验调试、标识标牌和通道恢复。

## 质量安全环保

- 质量目标：满足国家、行业、国家电网及采购文件要求，分部分项工程验收合格，资料真实完整，具备投运和移交条件。
- 安全目标：杜绝人身伤亡、设备事故、火灾事故和重大交通事故，落实安全生产责任制、班前会、风险预控、旁站监督、隐患排查闭环。
- 环保水保：控制扬尘、噪声、固废、废油、废水和植被扰动，施工结束后完成场地恢复、通道清理、临时占地恢复和环保验收资料归档。
""",
    "04_standard_phrases/qualification_response_phrases.md": """# 国网电力投标资格响应标准话术

我单位具备独立法人资格，持有有效营业执照，并具备采购文件要求的电力工程施工总承包/输变电工程专业承包/承装（修、试）电力设施许可等资质。相关资质证书、安全生产许可证及体系认证均处于有效期内，业务范围能够覆盖本项目采购范围。

我单位近年承担过与本项目电压等级、工程类型和施工内容相近的输变电、配网、变电站、电缆或电力设施安装调试项目，具备电力工程组织实施、质量控制、安全风险管控、资料归档和投运配合经验。

拟派项目经理、技术负责人、安全负责人、质量负责人及主要管理人员均满足采购文件要求，具备相应执业资格、职称、岗位证书或安全生产考核合格证书。特种作业人员、电工、高处作业、起重作业等人员按规定持证上岗。

我单位未处于被责令停业、财产被接管冻结、破产状态，未被列入严重违法失信名单，未存在采购文件和国家电网供应商管理规则规定的暂停、取消或永久取消应答资格情形。
""",
    "04_standard_phrases/business_response_phrases.md": """# 国网电力投标商务响应标准话术

我单位已全面阅读采购公告、采购文件、技术规范书、合同条款、工程量清单、补遗澄清文件及国家电网电子商务平台相关操作要求，愿按采购文件规定的范围、质量、安全、工期、报价和合同条件完成全部工作内容。

我单位承诺按采购文件规定的投标有效期保持应答文件有效，在有效期内不撤销、不修改实质性内容，并按采购人和招标代理机构要求参加澄清、谈判、二轮报价、合同签订及履约准备工作。

我单位将安排专人负责 ECP2.0/ETP 平台报名、采购文件下载、电子钥匙和 CA 签章、离线投标工具编制、电子应答文件加密上传、解密、报价确认和平台通知跟踪，确保各节点按采购文件要求完成。

报价已综合考虑人工、材料、设备、机械、运输、安装、调试、试验、风险、安全文明施工、环保水保、税费、保险、资料移交及合同约定的全部费用。若国家税收政策调整，我单位将按合同约定和最新政策执行。
""",
    "04_standard_phrases/quality_safety_environment_phrases.md": """# 国网电力工程质量安全环保响应模板

## 质量管理

项目部建立以项目经理为第一责任人、技术负责人牵头、质量负责人全过程控制的质量管理体系。施工全过程执行设计文件、国家标准、行业标准、国家电网标准化工艺及采购文件技术规范要求，落实材料设备进场验收、隐蔽工程验收、工序交接、试验检测、缺陷整改和资料归档。

## 安全管理

项目实施坚持安全第一、预防为主、综合治理。开工前开展现场勘察和风险识别，编制施工组织设计、专项施工方案、施工安全措施和应急预案。对临近带电体、跨越架、起重吊装、深基坑、高处作业、动火作业、临时用电、电缆试验等风险点实行清单化管控。

## 环保水保

施工期间落实扬尘、噪声、固废、废油、废水和临时占地控制措施。线路工程严格控制施工便道和塔基作业面，减少植被扰动；变电站工程落实围挡、排水、沉淀、材料堆放和垃圾清运；完工后及时恢复场地并形成环保水保资料。

## 资料归档

质量、安全、技术、试验、设备、隐蔽验收、签证变更、会议纪要、影像记录、竣工图和投运移交资料与工程进度同步形成、同步审核、同步归档，确保资料完整、真实、可追溯。
""",
    "04_standard_phrases/bid_document_checklist.md": """# 国网电力投标文件合规检查清单

## 平台与文件

- 是否在 ECP2.0/ETP 或指定采购代理平台完成注册、报名、采购文件下载。
- CA 证书、电子签章、离线投标工具版本、加密上传、解密安排是否满足公告要求。
- 是否逐项核对采购公告、采购文件、技术规范书、补遗澄清、最高限价和报价轮次要求。

## 资格文件

- 营业执照、资质证书、安全生产许可证、承装（修、试）电力设施许可证是否有效。
- 企业业绩、人员资格、项目经理无在建承诺、社保、信用查询和供应商不良行为状态是否满足要求。
- 联合体、分包、代理商、制造商授权、检测报告、型式试验报告等特殊要求是否完整。

## 商务文件

- 投标函、报价表、报价明细、税率、不含税价、投标保证金、投标有效期、工期、质量、安全目标是否一致。
- 法定代表人身份证明、授权委托书、签字盖章、页码目录、文件格式和命名是否符合电子投标要求。

## 技术文件

- 施工组织设计是否覆盖项目概况、总体部署、进度计划、资源配置、主要施工方案、质量安全环保、调试试验、资料移交。
- 是否针对变电、线路、电缆、通信自动化、配网等专业内容分别响应技术规范书。
- 是否出现暗标禁止的单位名称、人员姓名、标识、业绩线索或其他可识别投标人身份的信息。

## 否决风险

- 逾期上传、未解密、未签章、报价超过限价、多个报价不一致、资格证书过期、业绩不满足、关键条款负偏离、供应商被暂停应答资格，均应作为高风险项提前检查。
""",
    "04_standard_phrases/power_grid_rag_ingestion_notes.md": """# 国网电力种子库入库建议

1. 优先导入 `04_standard_phrases`，这是可直接参与标书生成的自建话术和检查清单。
2. 再导入 `02_policy_regulations`，用于招投标合规、电力建设质量安全、必须招标范围和电力工程监管问答。
3. `03_standards_specs` 中的标准名录建议按专业和标准编号切片，作为“引用标准检索入口”，不要让模型输出大段标准原文。
4. `01_tender_documents` 中的国网采购公告适合学习 ECP/ETP 流程、资格条款、公告结构和否决风险；输变电公开报告适合补充项目参建角色、工程范围、环保验收和技术场景词汇。
5. PDF 建议先走 MinerU/OCR，保留页码、表格、章节层级；HTML/Markdown 可直接按标题层级切片。
""",
}


def slugify(title: str) -> str:
    digest = hashlib.sha1(title.encode("utf-8")).hexdigest()[:8]
    clean = re.sub(r"[\\/:*?\"<>|\s]+", "_", title).strip("_")
    return f"{clean[:42]}_{digest}"


def read_url(url: str, verify_ssl: bool = True) -> tuple[bytes, str]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    context = None if verify_ssl else ssl._create_unverified_context()
    with urlopen(request, timeout=45, context=context) as response:
        content_type = response.headers.get("Content-Type", "")
        return response.read(), content_type


def decode_html(raw: bytes) -> str:
    for encoding in ("utf-8", "gb18030", "gbk"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def html_to_markdown(html: str, title: str, url: str, source_org: str) -> str:
    if BeautifulSoup is None:
        text = re.sub(r"<[^>]+>", "\n", html)
    else:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        main = soup.find("article") or soup.find("main") or soup.find(id=re.compile("content|article|main", re.I)) or soup.body or soup
        lines: list[str] = []
        for node in main.find_all(["h1", "h2", "h3", "p", "li", "tr", "div"], recursive=True):
            text = " ".join(node.get_text(" ", strip=True).split())
            if not text or len(text) < 2:
                continue
            if node.name == "h1":
                lines.append(f"# {text}")
            elif node.name == "h2":
                lines.append(f"## {text}")
            elif node.name == "h3":
                lines.append(f"### {text}")
            elif node.name == "li":
                lines.append(f"- {text}")
            else:
                lines.append(text)
        text = "\n\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return "\n".join(
        [
            f"# {title}",
            "",
            f"- 来源：{source_org}",
            f"- 原始链接：{url}",
            f"- 采集时间：{datetime.now(timezone.utc).isoformat()}",
            "",
            text,
            "",
        ]
    )


def write_url_stub(path: Path, source: dict[str, str], error: str) -> str:
    content = "\n".join(
        [
            f"# {source['title']}",
            "",
            f"- 来源：{source['source_org']}",
            f"- 原始链接：{source['url']}",
            f"- 采集状态：下载失败，保留 URL 供人工复核",
            f"- 错误：{error}",
            "",
        ]
    )
    path.write_text(content, encoding="utf-8")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_dirs() -> None:
    for category in ["01_tender_documents", "02_policy_regulations", "03_standards_specs", "04_standard_phrases"]:
        category_dir = ROOT / category
        category_dir.mkdir(parents=True, exist_ok=True)
        for path in category_dir.iterdir():
            if not path.is_file():
                continue
            generated_by_indexed_download = re.match(r"^\d{2}_", path.name)
            generated_by_template = path.name in {Path(item).name for item in GENERATED_DOCS}
            if generated_by_indexed_download or generated_by_template:
                path.unlink()


def download_sources() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    now = datetime.now(timezone.utc).isoformat()
    for index, source in enumerate(SOURCES, start=1):
        category_dir = ROOT / source["category"]
        slug = slugify(source["title"])
        row = {
            "title": source["title"],
            "category": source["category"],
            "doc_type": source["doc_type"],
            "source_org": source["source_org"],
            "source_url": source["url"],
            "file_path": "",
            "tags": source["tags"],
            "downloaded_at": now,
            "sha256": "",
            "status": "",
            "error": "",
        }
        try:
            raw, content_type = read_url(source["url"], source.get("verify_ssl", True))
            is_pdf = "pdf" in content_type.lower() or source["url"].lower().split("?")[0].endswith(".pdf")
            if is_pdf:
                path = category_dir / f"{index:02d}_{slug}.pdf"
                path.write_bytes(raw)
            else:
                path = category_dir / f"{index:02d}_{slug}.md"
                markdown = html_to_markdown(decode_html(raw), source["title"], source["url"], source["source_org"])
                path.write_text(markdown, encoding="utf-8")
            row["file_path"] = str(path.relative_to(ROOT))
            row["sha256"] = sha256_file(path)
            row["status"] = "downloaded"
        except (HTTPError, URLError, TimeoutError, ssl.SSLError, OSError) as exc:
            path = category_dir / f"{index:02d}_{slug}.url.md"
            row["file_path"] = str(path.relative_to(ROOT))
            row["sha256"] = write_url_stub(path, source, f"{type(exc).__name__}: {exc}")
            row["status"] = "failed_url_saved"
            row["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(row)
        time.sleep(0.4)
    return rows


def write_generated_docs(rows: list[dict[str, str]]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    for relative_path, content in GENERATED_DOCS.items():
        path = ROOT / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.strip() + "\n", encoding="utf-8")
        rows.append(
            {
                "title": Path(relative_path).stem,
                "category": Path(relative_path).parts[0],
                "doc_type": "自建话术模板",
                "source_org": "AI标书系统项目自建",
                "source_url": "",
                "file_path": relative_path,
                "tags": "国网投标,电力工程,RAG模板",
                "downloaded_at": now,
                "sha256": sha256_file(path),
                "status": "generated",
                "error": "",
            }
        )


def write_indexes(rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "title",
        "category",
        "doc_type",
        "source_org",
        "source_url",
        "file_path",
        "tags",
        "downloaded_at",
        "sha256",
        "status",
        "error",
    ]
    with (ROOT / "index.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    with (ROOT / "index.jsonl").open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_readme(rows: list[dict[str, str]]) -> None:
    counts = {category: 0 for category in ["01_tender_documents", "02_policy_regulations", "03_standards_specs", "04_standard_phrases"]}
    for row in rows:
        counts[row["category"]] = counts.get(row["category"], 0) + 1
    downloaded = sum(1 for row in rows if row["status"] == "downloaded")
    generated = sum(1 for row in rows if row["status"] == "generated")
    failed = sum(1 for row in rows if row["status"] == "failed_url_saved")
    content = f"""# 国网电力行业 RAG 种子知识库

本目录用于给企业知识库提供第一批国网电力招投标基础资料。资料分为公开来源下载和项目自建模板两类，重点支撑国家电网、输变电工程、配网工程、电力设施安装调试等投标场景。

## 目录

- `01_tender_documents/`：国网公开采购公告、输变电工程公开报告和招投标流程样例。
- `02_policy_regulations/`：招标投标、电力法、能源法、电力建设安全、质量监督和备案等政策法规。
- `03_standards_specs/`：电力建设标准目录、常用标准引用说明和国网企业技术体系引用边界。
- `04_standard_phrases/`：自建国网投标标准话术、章节库、资格/商务/技术/质量安全环保模板、检查清单。
- `index.csv` / `index.jsonl`：RAG 入库元数据索引。

## 本次采集数量

- `01_tender_documents`：{counts.get("01_tender_documents", 0)} 条
- `02_policy_regulations`：{counts.get("02_policy_regulations", 0)} 条
- `03_standards_specs`：{counts.get("03_standards_specs", 0)} 条
- `04_standard_phrases`：{counts.get("04_standard_phrases", 0)} 条
- 下载成功：{downloaded} 条
- 自建生成：{generated} 条
- 下载失败但保留 URL：{failed} 条

## 入库建议

1. 优先导入 `04_standard_phrases`，这些是可直接用于生成投标文件的自有知识。
2. 再导入 `02_policy_regulations`，用于法规依据、资格条件、质量安全、必须招标范围、质量监督和备案要求问答。
3. 最后导入 `01_tender_documents` 和 `03_standards_specs`，用于学习国网采购公告结构、ECP/ETP 平台流程、评标/应答风险、电力工程标准引用和输变电项目场景词汇。
4. PDF 建议先走 MinerU/OCR，保留页码、表格和章节层级；HTML/Markdown 可以直接按标题层级切片。

## 版权和使用边界

本目录优先采集政府网站、国家能源局、国家电网公开页面或公开 PDF。国家标准、行业标准、国网企业标准全文通常存在版权边界，后续不要混入来源不明或付费平台搬运的全文资料；可通过标准名称、标准编号、适用场景、条文引用位置和企业自有理解形成可检索的二级知识。

## 重新下载

```bash
python rag_seed/power_grid_resources/_scripts/download_power_grid_rag_seed.py
```
"""
    (ROOT / "README.md").write_text(content, encoding="utf-8")


def main() -> int:
    ensure_dirs()
    rows = download_sources()
    write_generated_docs(rows)
    write_indexes(rows)
    write_readme(rows)
    print(f"wrote {len(rows)} power-grid seed records under {ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
