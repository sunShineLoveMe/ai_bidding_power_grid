#!/usr/bin/env python3
"""Download and assemble a water-resources bidding RAG seed corpus.

The script intentionally uses public government / public transaction-platform
sources. It stores downloaded HTML as cleaned Markdown where possible, keeps
public PDFs as-is, and writes a metadata index for downstream ingestion.
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
        "title": "中华人民共和国招标投标法实施条例",
        "url": "https://www.gov.cn/gongbao/content/2019/content_5468831.htm",
        "source_org": "中国政府网/国务院公报",
        "doc_type": "法律法规",
        "tags": "招标投标,工程建设,法律法规",
    },
    {
        "category": "02_policy_regulations",
        "title": "水利工程建设项目招标投标管理规定",
        "url": "https://www.gov.cn/gongbao/content/2002/content_61624.htm",
        "source_org": "中国政府网/国务院公报",
        "doc_type": "部门规章",
        "tags": "水利工程,招标投标,施工,监理,材料设备",
    },
    {
        "category": "02_policy_regulations",
        "title": "水利工程建设项目管理规定试行",
        "url": "https://www.gov.cn/zhengce/1995-04/21/content_5712333.htm",
        "source_org": "中国政府网/水利部",
        "doc_type": "部门规章",
        "tags": "水利工程,项目管理,建设程序",
    },
    {
        "category": "02_policy_regulations",
        "title": "水利工程建设项目验收管理规定",
        "url": "https://www.gov.cn/zhengce/2006-12/18/content_5712309.htm",
        "source_org": "中国政府网/水利部",
        "doc_type": "部门规章",
        "tags": "水利工程,验收,法人验收,政府验收",
    },
    {
        "category": "02_policy_regulations",
        "title": "水利工程质量管理规定",
        "url": "https://www.gov.cn/gongbao/content/2023/content_5743637.htm",
        "source_org": "中国政府网/国务院公报",
        "doc_type": "部门规章",
        "tags": "水利工程,质量管理,质量责任",
    },
    {
        "category": "02_policy_regulations",
        "title": "水利工程质量事故处理规定",
        "url": "https://www.gov.cn/zhengce/202412/content_6991025.htm",
        "source_org": "中国政府网/水利部",
        "doc_type": "部门规章",
        "tags": "水利工程,质量事故,事故处理",
    },
    {
        "category": "02_policy_regulations",
        "title": "水利建设市场经营主体信用信息管理办法",
        "url": "https://www.gov.cn/gongbao/2024/issue_11606/202409/content_6976921.html",
        "source_org": "中国政府网/国务院公报",
        "doc_type": "规范性文件",
        "tags": "水利建设市场,信用信息,全国水利监管平台",
    },
    {
        "category": "02_policy_regulations",
        "title": "水利工程建设安全生产管理规定",
        "url": "https://slt.fj.gov.cn/xxgk/fggw/slbyqtbwgz/202103/t20210302_5542929.htm",
        "source_org": "福建省水利厅转载水利部",
        "doc_type": "部门规章",
        "tags": "水利工程,安全生产,施工安全",
    },
    {
        "category": "01_tender_documents",
        "title": "板芙镇蚙蜞塘水库除险加固工程招标文件提前公示",
        "url": "https://www.zsjypt.cn/artical/210/243404",
        "source_org": "中山市公共资源交易平台",
        "doc_type": "招标文件公示页面",
        "tags": "水库除险加固,水利工程,招标文件公示",
    },
    {
        "category": "01_tender_documents",
        "title": "桃江县花果山等19座小型水库除险加固工程项目五六标段",
        "url": "https://jyzx.yiyang.gov.cn/ggzyjy/31065/31081/31110/31117/37918/content_1912637.html",
        "source_org": "益阳市公共资源交易中心",
        "doc_type": "招标公告及附件页面",
        "tags": "水库除险加固,小型水库,招标文件,工程量清单",
        "verify_ssl": False,
    },
    {
        "category": "01_tender_documents",
        "title": "汨罗市黄金水库等16座小型水库除险加固工程总承包EPC",
        "url": "https://www.miluo.gov.cn/25221/25242/25243/content_2228827.html",
        "source_org": "汨罗市人民政府",
        "doc_type": "招标公告",
        "tags": "水库除险加固,EPC,资格后审,综合评估法",
    },
    {
        "category": "01_tender_documents",
        "title": "汨罗市2025年度青坑水库等10座小型水库除险加固工程总承包",
        "url": "https://www.miluo.gov.cn/25308/27701/27714/27937/31074/content_2269303.html",
        "source_org": "汨罗市人民政府",
        "doc_type": "招标公告",
        "tags": "水库除险加固,EPC,水利发展资金",
    },
    {
        "category": "01_tender_documents",
        "title": "彝良县长海子水库除险加固工程招标公告",
        "url": "https://www.ggzy.gov.cn/html/b/530000/0101/202512/19/00530522b7909cf34c8a80d04c0410736d30.shtml",
        "source_org": "全国公共资源交易平台",
        "doc_type": "招标公告",
        "tags": "水库除险加固,施工,公共资源交易",
    },
    {
        "category": "01_tender_documents",
        "title": "东莞市黄牛埔水库除险加固工程招标公告",
        "url": "https://www.dg.gov.cn/hj/ztzl/ggzyjy/ztbxx/zbgg/content/post_4326669.html",
        "source_org": "东莞市人民政府门户网站",
        "doc_type": "招标公告",
        "tags": "水库除险加固,水利工程,招标公告",
    },
    {
        "category": "01_tender_documents",
        "title": "兰溪市双峰岭水库除险加固扩容工程勘察设计项目招标文件",
        "url": "https://zjjcmspublic.oss-cn-hangzhou-zwynet-d01-a.internet.cloud.zj.gov.cn/jcms_files/jcms1/web3614/site/attach/0/1/603/%E5%85%B0%E6%BA%AA%E5%B8%82%E5%8F%8C%E5%B3%B0%E5%B2%AD%E6%B0%B4%E5%BA%93%E9%99%A4%E9%99%A9%E5%8A%A0%E5%9B%BA%EF%BC%88%E6%89%A9%E5%AE%B9%EF%BC%89%E5%B7%A5%E7%A8%8B%E5%8B%98%E5%AF%9F%E8%AE%BE%E8%AE%A1%E9%A1%B9%E7%9B%AE-%E6%8B%9B%E6%A0%87%E6%96%87%E4%BB%B6.pdf",
        "source_org": "浙江政务公开附件",
        "doc_type": "招标文件PDF",
        "tags": "水库除险加固,勘察设计,招标文件",
    },
    {
        "category": "01_tender_documents",
        "title": "郏县老虎洞水库除险加固工程项目第一批监理招标文件",
        "url": "https://zhumadian.zfcg.henan.gov.cn/cmsweb81e27e/nas/webfile2024/pdsjx/rootfiles/2023/10/20/1417391a249a41fa899fcbbb272d7299.pdf",
        "source_org": "河南省政府采购网附件",
        "doc_type": "监理招标文件PDF",
        "tags": "水库除险加固,监理,招标文件",
    },
    {
        "category": "01_tender_documents",
        "title": "喀什噶尔河灌区骨干工程节水改造灌区信息化建设项目I标招标文件",
        "url": "https://slt.xinjiang.gov.cn/slt/uploadfiles/2018/8/13/1534161830624.pdf",
        "source_org": "新疆维吾尔自治区水利厅附件",
        "doc_type": "招标文件PDF",
        "tags": "灌区,节水改造,信息化,招标文件",
    },
    {
        "category": "01_tender_documents",
        "title": "塔里木河流域希尼尔水库除险加固工程施工监理I标二次招标文件",
        "url": "https://slt.xinjiang.gov.cn/slt/uploadfiles/2019/5/21/1558410432736.pdf",
        "source_org": "新疆维吾尔自治区水利厅附件",
        "doc_type": "监理招标文件PDF",
        "tags": "水库除险加固,施工监理,招标文件",
    },
    {
        "category": "01_tender_documents",
        "title": "塔里木河流域希尼尔水库除险加固工程坝基防渗处理施工标招标文件",
        "url": "https://slt.xinjiang.gov.cn/slt/uploadfiles/2019/4/19/1555666040089.pdf",
        "source_org": "新疆维吾尔自治区水利厅附件",
        "doc_type": "施工招标文件PDF",
        "tags": "水库除险加固,坝基防渗,施工,招标文件",
    },
    {
        "category": "01_tender_documents",
        "title": "斋堂水库除险加固工程招标文件",
        "url": "https://ggzyfw.beijing.gov.cn/cmsbj/u/cms/cn.gov.bjggzyfw.www/202312/6060234282617.pdf",
        "source_org": "北京市公共资源交易服务平台附件",
        "doc_type": "招标文件PDF",
        "tags": "水库除险加固,招标文件,公共资源交易",
    },
    {
        "category": "03_standards_specs",
        "title": "贵州省水利工程标准施工招标文件示范文本",
        "url": "https://mwr.guizhou.gov.cn/gzdt/tzgg/tzwj/202407/P020240709338983332101.pdf",
        "source_org": "贵州省水利厅附件",
        "doc_type": "示范文本PDF",
        "tags": "水利工程,标准施工招标文件,示范文本,评标办法",
    },
]


GENERATED_DOCS = {
    "03_standards_specs/water_conservancy_standards_catalog.md": """# 水利投标常用标准规范目录

> 说明：标准规范全文通常存在版权边界，本文件只整理标准名称、适用场景和 RAG 入库建议，不收录来源不明的标准全文。

## 招标采购与合同

- 《中华人民共和国招标投标法》：招投标基本法律依据，适用于招标范围、招标方式、投标、开评标、中标、法律责任等检索。
- 《中华人民共和国招标投标法实施条例》：细化资格预审、招标文件、投标保证金、评标委员会、否决投标、投诉处理等规则。
- 《水利工程建设项目招标投标管理规定》：水利工程勘察设计、施工、监理、重要设备材料采购招标的行业规则。
- 《标准施工招标文件》及水利工程行业示范文本：用于学习投标人须知、评标办法、合同条款、工程量清单、投标文件格式。

## 水利工程质量与验收

- SL 176《水利水电工程施工质量检验与评定规程》：质量评定、单元工程、分部工程、单位工程验收资料组织。
- SL 223《水利水电建设工程验收规程》：阶段验收、单位工程验收、合同工程完工验收、竣工验收。
- 《水利工程质量管理规定》：项目法人、勘察、设计、施工、监理、检测等主体质量责任。
- 《水利工程建设项目验收管理规定》：法人验收、政府验收、验收监督管理。

## 施工安全与环保水保

- SL 398《水利水电工程施工通用安全技术规程》：施工现场安全、临时用电、机械、起重、临边临水等。
- 《水利工程建设安全生产管理规定》：安全生产责任、专项施工方案、应急管理。
- 《生产安全事故应急条例》：应急预案、演练、事故响应。
- 水土保持方案批复及环保批复：用于施工期水保、弃渣场、临时占地、生态恢复承诺。

## 水库除险加固常见专业

- 水库大坝安全评价相关规范：用于病险水库问题识别、除险加固依据。
- 坝体/坝基防渗处理规范：适用于帷幕灌浆、防渗墙、土工膜、黏土心墙等章节。
- 混凝土工程施工规范：适用于溢洪道、放水设施、护坡、消力池、闸室等混凝土结构。
- 土石方填筑与碾压试验规范：适用于坝体加高培厚、坝坡整治、堤防填筑。
- 金属结构及启闭机安装规范：适用于闸门、启闭机、压力钢管、防腐、调试。

## 灌区与泵站常见专业

- GB 50288《灌溉与排水工程设计标准》：灌区工程设计和技术响应。
- 泵站设计与施工验收相关规范：泵站土建、机电设备安装、试运行。
- 自动化监测/信息化建设标准：闸门自动控制、雨水情监测、视频监控、调度平台、网络安全。

## RAG 入库建议

标准类资料建议采用“标准名称 + 适用章节 + 常见响应点 + 禁止编造条文”的方式入库。生成投标文件时，模型可以引用标准名称和适用场景，但不能伪造条文编号和原文。
""",
    "04_standard_phrases/water_conservancy_section_library.md": """# 水利投标章节库

## 水库除险加固施工常见章节

1. 工程概况与编制依据
2. 施工总体部署与项目组织机构
3. 施工总平面布置
4. 施工导流与安全度汛
5. 施工测量与试验检测
6. 土石方开挖与填筑施工方案
7. 坝体防渗及坝基处理施工方案
8. 混凝土工程施工方案
9. 砌石、护坡及排水工程施工方案
10. 金属结构及机电设备安装方案
11. 自动化监测与信息化系统施工方案
12. 施工进度计划及保证措施
13. 资源配置计划
14. 质量管理体系与保证措施
15. 安全生产管理体系与保证措施
16. 环境保护、水土保持与文明施工
17. 汛期、雨季、冬季及高温施工措施
18. 成品保护、资料管理与竣工验收
19. 应急预案与风险控制
20. 对本项目重点难点的认识及应对措施

## 勘察设计类常见章节

1. 项目理解与设计目标
2. 现状调查、资料收集与现场踏勘
3. 勘察设计工作大纲
4. 病险问题复核与除险加固思路
5. 水文、水工、地质、结构、金属结构、机电专业设计方案
6. 投资控制与限额设计措施
7. 设计进度计划与成果交付安排
8. 质量保证体系和设计校审制度
9. 施工期设计服务与后续服务承诺

## 监理类常见章节

1. 监理范围、目标和依据
2. 项目监理机构及人员配置
3. 质量控制措施
4. 进度控制措施
5. 投资控制措施
6. 安全生产监理措施
7. 合同、信息和资料管理
8. 旁站、巡视和平行检测计划
9. 验收与缺陷责任期监理服务
""",
    "04_standard_phrases/water_conservancy_rag_ingestion_notes.md": """# 水利行业 RAG 入库建议

## 推荐分层

1. 法规政策层：招投标法、实施条例、水利工程招标投标管理规定、质量/安全/验收/信用管理规定。
2. 招标文件层：水库除险加固、灌区节水改造、施工监理、勘察设计、EPC 总承包等公开招标文件和公告。
3. 投标写作层：资格响应、商务响应、技术方案、质量安全环保、水土保持、进度计划、资料清单等自有话术模板。
4. 项目事实层：企业资质、人员、业绩、设备、财务、信用、获奖、专利、工法、类似工程案例。

## 切片建议

- 法规政策：按章/条切片，chunk 约 600-1000 中文字，保留条号和来源 URL。
- 招标文件：按“投标人须知前附表、资格条件、评标办法、合同条款、技术标准、投标文件格式”切片。
- PDF：先用 MinerU/OCR 保留标题层级、表格和页码，再入库；表格类内容优先用 Markdown 表格或 JSON 结构保存。
- 话术模板：按业务场景切片，给每个切片加 `scenario`、`适用章节`、`风险提示` 元数据。

## 元数据字段

`title`、`category`、`doc_type`、`source_org`、`source_url`、`file_path`、`tags`、`downloaded_at`、`sha256`。
""",
    "04_standard_phrases/qualification_response_phrases.md": """# 水利投标资格响应标准话术

## 企业资质响应

我单位具备独立法人资格，持有有效的营业执照，并具备招标文件要求的水利水电工程施工总承包资质/工程设计资质/工程勘察资质/监理资质。相关证书均处于有效期内，资质类别、等级和业务范围能够覆盖本项目招标范围。

## 安全生产许可证响应

我单位持有建设行政主管部门核发的安全生产许可证，证书处于有效期内。项目实施期间，我单位将严格落实安全生产责任制，按招标文件、合同文件及水利工程建设安全生产管理要求组织施工。

## 信用档案响应

我单位已按水利建设市场监管要求建立信用档案，并承诺投标文件中填报的企业基本信息、人员信息、业绩信息、奖惩信息真实、准确、完整。如招标文件要求在全国水利建设市场监管平台或地方水利建设市场监管系统备案，我单位将按规定提供查询路径、截图或证明材料。

## 类似业绩响应

我单位近年承担过与本项目工程性质、规模、施工内容相近的水利工程项目，具备水库除险加固、堤防治理、灌区节水改造、泵站/闸站施工、混凝土工程、土石方工程、金属结构安装、机电设备安装等相关经验。所附合同、中标通知书、完工/竣工验收资料能够证明业绩真实性。

## 项目经理响应

拟派项目经理具备招标文件要求的注册建造师资格和安全生产考核合格证书，具有类似水利工程项目管理经验，未担任其他在建工程项目经理或符合招标文件关于在建项目的规定。项目实施期间，项目经理将常驻现场，全面负责进度、质量、安全、合同和协调管理。

## 技术负责人响应

拟派技术负责人具备水利水电工程相关专业技术职称或招标文件要求的执业资格，熟悉水利工程施工技术标准、质量验收程序和安全生产要求，能够承担施工方案审核、技术交底、质量控制和技术变更管理工作。
""",
    "04_standard_phrases/business_response_phrases.md": """# 水利投标商务响应标准话术

## 投标函基础承诺

我单位已全面阅读并理解招标文件、图纸、工程量清单、合同条款、技术标准和补遗澄清文件，愿按招标文件规定的范围、质量标准、计划工期和合同条件完成本项目全部工作内容。

## 工期承诺

我单位承诺按招标文件规定的计划工期完成施工任务。中标后将结合现场条件、汛期影响、材料供应、交通组织和关键工序搭接关系，编制可执行的施工总进度计划、月度计划和周计划，并通过资源投入和过程纠偏确保节点目标实现。

## 质量承诺

我单位承诺工程质量达到国家、水利行业及招标文件规定的验收标准。施工过程中将建立项目质量管理体系，严格执行原材料进场验收、试验检测、工序自检、隐蔽工程验收、分部工程验收和质量资料归档制度。

## 安全承诺

我单位承诺严格遵守安全生产法律法规和水利工程建设安全生产管理要求，落实项目法人、监理单位和主管部门的安全管理要求，建立安全风险分级管控和隐患排查治理机制，确保施工安全。

## 环保和水保承诺

我单位承诺严格执行环境保护和水土保持要求，对施工扬尘、噪声、废水、弃渣、临时占地、植被保护、河道水体保护等采取有效控制措施，工程完工后及时完成场地清理和生态恢复。

## 投标有效期承诺

我单位承诺投标文件在招标文件规定的投标有效期内保持有效。在有效期内，我单位不撤销、不修改实质性投标内容，并按招标文件要求接受评标、澄清、定标和合同签订程序。

## 履约担保承诺

如我单位中标，将按招标文件和合同约定及时提交履约担保，签订合同并组织进场，确保项目按期开工、规范实施、顺利验收。
""",
    "04_standard_phrases/technical_construction_organization_phrases.md": """# 水利施工组织设计常用章节与写法

## 施工总体部署

本项目按照“先准备、后主体；先重点、后一般；先控制性工程、后配套工程；施工与安全度汛同步考虑”的原则组织实施。项目部将结合施工现场地形、水文、交通、供电、材料供应和汛期约束，合理划分施工区段，优化施工顺序，确保关键线路受控。

## 施工测量

进场后对设计控制点进行复核，建立施工测量控制网。施工测量成果经复核无误并报监理确认后使用。开挖、填筑、混凝土结构、金属结构安装等关键工序均实施测量放样和复测制度，确保轴线、标高、断面尺寸满足设计要求。

## 土石方开挖

土石方开挖前完成清表、临时排水和边坡防护准备。开挖过程中按设计边线、坡比和高程分层分段施工，严禁超挖扰动基底。对软弱、渗水、破碎部位及时采取排水、支护、换填或加固措施。

## 土方填筑

填筑料源经试验检测合格后使用，填筑前进行碾压试验，确定铺土厚度、含水率控制范围、碾压遍数和压实机械组合。填筑施工按分层摊铺、分层碾压、分层检测执行，压实度或相对密度满足设计和规范要求后方可进入下一层施工。

## 混凝土工程

混凝土施工严格控制原材料、配合比、拌合、运输、浇筑、振捣、养护和温控。模板、钢筋、预埋件经检查验收合格后浇筑混凝土。浇筑过程连续进行，重点控制施工缝处理、振捣密实、表面收光和早期养护。

## 防渗处理

帷幕灌浆、防渗墙、土工膜、黏土心墙等防渗工程施工前应完成专项方案、试验段或工艺试验。施工过程中重点控制孔位、孔深、浆液配比、灌浆压力、搭接宽度、焊缝检测和隐蔽验收。

## 金属结构与机电设备安装

闸门、启闭机、压力钢管、泵站设备、自动化监测设备等安装前核查设备合格证、出厂资料和基础尺寸。安装过程控制中心线、标高、垂直度、间隙、焊接质量、防腐质量和试运行参数。

## 安全度汛

项目处于汛期或跨汛期施工时，将编制安全度汛方案和应急预案，明确防汛组织、预警响应、抢险物资、临时导排水措施、撤离路线和应急值守制度。遇强降雨、洪水或上游来水变化时，及时启动响应并服从防汛调度。
""",
    "04_standard_phrases/quality_safety_environment_phrases.md": """# 水利工程质量安全环保响应模板

## 质量管理体系

项目部建立以项目经理为第一责任人、技术负责人具体负责、质量员全过程控制的质量管理体系。严格执行设计文件、合同文件、施工规范和验收规程，形成“材料验收、过程控制、检测复核、资料同步、验收闭合”的质量控制链条。

## 原材料质量控制

水泥、钢筋、砂石料、外加剂、止水材料、土工合成材料、金属结构及机电设备等进场材料均按规定进行外观检查、质量证明文件核验和见证取样复验。未经检验或检验不合格的材料不得用于工程实体。

## 工序质量控制

关键工序实行技术交底、样板引路、旁站检查和验收签认制度。隐蔽工程在覆盖前完成自检、互检、专检和监理验收，形成完整影像和书面资料。

## 安全风险控制

针对深基坑、高边坡、临水临边、起重吊装、临时用电、有限空间、爆破作业、汛期施工等危险源，实施专项方案审批和安全技术交底，配置必要的防护设施、警示标识和应急物资。

## 环境保护措施

施工道路定期洒水降尘，易扬尘材料覆盖堆放；施工废水经沉淀处理后回用或达标排放；机械设备定期维护减少跑冒滴漏；弃渣按指定地点堆放并采取拦挡、排水和覆盖措施。

## 水土保持措施

临时占地按照“少占、快用、及时恢复”的原则管理。对裸露边坡、弃渣场、临时道路和施工营地采取截排水、拦挡、覆盖、绿化恢复等措施，减少水土流失。

## 资料归档

质量、安全、环保、水保、试验检测、测量复核、隐蔽验收、会议纪要、变更签证等资料与工程进度同步形成、同步审核、同步归档，确保资料完整、真实、可追溯。
""",
    "04_standard_phrases/bid_document_checklist.md": """# 水利投标文件合规检查清单

## 一、资格文件

- 营业执照是否有效，名称是否与投标人名称一致。
- 资质证书类别、等级、业务范围是否满足招标文件。
- 安全生产许可证是否在有效期内。
- 项目经理、技术负责人、专职安全员、质量员等人员证书是否匹配。
- 类似业绩证明材料是否包含中标通知书、合同、验收或完工证明。
- 水利建设市场监管平台/地方监管系统信用档案是否满足要求。

## 二、商务文件

- 投标函金额、清单报价、报价汇总表是否一致。
- 投标有效期、工期、质量、安全、缺陷责任期是否响应招标文件。
- 投标保证金或电子保函是否满足金额、形式、有效期要求。
- 联合体协议是否明确牵头人、分工、责任承担。
- 法定代表人身份证明、授权委托书、签字盖章是否齐全。

## 三、技术文件

- 施工组织设计是否覆盖招标范围和主要工程内容。
- 进度计划是否与计划工期、关键节点、汛期约束一致。
- 质量、安全、环保、水保、文明施工措施是否具体可执行。
- 关键专项方案是否覆盖深基坑、高边坡、导流排水、混凝土、防渗、金属结构安装等内容。
- 资源配置是否与工程规模匹配，包括人员、机械、材料、试验检测设备。

## 四、否决投标风险

- 投标文件逾期递交、未解密或未按系统要求上传。
- 投标人名称、资质、人员、业绩与证明材料不一致。
- 报价超过最高投标限价或存在多个报价。
- 未按要求签字盖章、格式缺项、关键承诺缺失。
- 技术暗标出现可识别投标人身份的信息。
- 投标保证金不符合招标文件要求。
""",
}


def slugify(text: str, max_len: int = 72) -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "_", text, flags=re.UNICODE).strip("_")
    return slug[:max_len] or "document"


def ext_from_response(url: str, content_type: str | None) -> str:
    lower_url = url.lower().split("?")[0]
    if lower_url.endswith(".pdf"):
        return ".pdf"
    if lower_url.endswith(".docx"):
        return ".docx"
    if lower_url.endswith(".xls") or lower_url.endswith(".xlsx"):
        return ".xlsx"
    if content_type and "pdf" in content_type.lower():
        return ".pdf"
    return ".md"


def clean_html_to_markdown(html: bytes, title: str, url: str, source_org: str) -> str:
    text = html.decode("utf-8", errors="ignore")
    if BeautifulSoup is None:
        body = re.sub(r"<script[\s\S]*?</script>", "", text, flags=re.I)
        body = re.sub(r"<style[\s\S]*?</style>", "", body, flags=re.I)
        body = re.sub(r"<[^>]+>", "\n", body)
        lines = [line.strip() for line in body.splitlines() if line.strip()]
    else:
        soup = BeautifulSoup(text, "html.parser")
        for node in soup(["script", "style", "noscript", "svg"]):
            node.decompose()
        main = soup.find("article") or soup.find("main") or soup.find(class_=re.compile("content|article|detail|正文")) or soup.body or soup
        lines = [line.strip() for line in main.get_text("\n").splitlines() if line.strip()]
    compact_lines = []
    previous = None
    for line in lines:
        if line == previous:
            continue
        previous = line
        compact_lines.append(line)
    return "\n".join(
        [
            f"# {title}",
            "",
            f"- 来源：{source_org}",
            f"- 原始链接：{url}",
            "",
            *compact_lines,
            "",
        ]
    )


def fetch(source: dict) -> tuple[bytes, str | None]:
    context = None
    if source.get("verify_ssl") is False:
        context = ssl._create_unverified_context()
    req = Request(source["url"], headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=45, context=context) as resp:
        return resp.read(), resp.headers.get("content-type")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_generated_docs() -> list[dict]:
    rows = []
    now = datetime.now(timezone.utc).isoformat()
    for rel_path, content in GENERATED_DOCS.items():
        path = ROOT / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        data = content.encode("utf-8")
        rows.append(
            {
                "title": path.stem,
                "category": path.parent.name,
                "doc_type": "自建话术模板",
                "source_org": "AI标书系统项目自建",
                "source_url": "",
                "file_path": str(path.relative_to(ROOT)),
                "tags": "水利投标,标准话术,RAG模板",
                "downloaded_at": now,
                "sha256": sha256(data),
                "status": "generated",
                "error": "",
            }
        )
    return rows


def download_sources() -> list[dict]:
    rows = []
    now = datetime.now(timezone.utc).isoformat()
    for idx, source in enumerate(SOURCES, 1):
        category_dir = ROOT / source["category"]
        category_dir.mkdir(parents=True, exist_ok=True)
        url_hash = hashlib.sha1(source["url"].encode("utf-8")).hexdigest()[:8]
        try:
            data, content_type = fetch(source)
            ext = ext_from_response(source["url"], content_type)
            filename = f"{idx:02d}_{slugify(source['title'])}_{url_hash}{ext}"
            path = category_dir / filename
            if ext == ".md":
                markdown = clean_html_to_markdown(data, source["title"], source["url"], source["source_org"])
                path.write_text(markdown, encoding="utf-8")
                stored_bytes = markdown.encode("utf-8")
            else:
                path.write_bytes(data)
                stored_bytes = data
            status = "downloaded"
            error = ""
            digest = sha256(stored_bytes)
            print(f"[OK] {source['title']} -> {path.relative_to(ROOT)}")
        except (HTTPError, URLError, TimeoutError, ssl.SSLError, Exception) as exc:
            filename = f"{idx:02d}_{slugify(source['title'])}_{url_hash}.url.md"
            path = category_dir / filename
            fallback = (
                f"# {source['title']}\n\n"
                f"- 来源：{source['source_org']}\n"
                f"- 原始链接：{source['url']}\n"
                f"- 下载状态：失败，保留链接待重试\n"
                f"- 错误：{type(exc).__name__}: {exc}\n"
            )
            path.write_text(fallback, encoding="utf-8")
            digest = sha256(fallback.encode("utf-8"))
            status = "failed_url_saved"
            error = f"{type(exc).__name__}: {exc}"
            print(f"[FAIL] {source['title']} -> {error}", file=sys.stderr)
        rows.append(
            {
                "title": source["title"],
                "category": source["category"],
                "doc_type": source["doc_type"],
                "source_org": source["source_org"],
                "source_url": source["url"],
                "file_path": str(path.relative_to(ROOT)),
                "tags": source["tags"],
                "downloaded_at": now,
                "sha256": digest,
                "status": status,
                "error": error,
            }
        )
        time.sleep(0.3)
    return rows


def write_indexes(rows: list[dict]) -> None:
    csv_path = ROOT / "index.csv"
    jsonl_path = ROOT / "index.jsonl"
    fields = [
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
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    with jsonl_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_readme(rows: list[dict]) -> None:
    counts = {}
    for row in rows:
        counts[row["category"]] = counts.get(row["category"], 0) + 1
    readme = ROOT / "README.md"
    lines = [
        "# 水利行业 RAG 种子知识库",
        "",
        "本目录用于给企业知识库提供第一批水利招投标基础资料。资料分为公开来源下载和项目自建模板两类。",
        "",
        "## 目录",
        "",
        "- `01_tender_documents/`：公开招标公告、招标文件 PDF、招标文件公示页面。",
        "- `02_policy_regulations/`：招投标、水利建设、质量、安全、验收、信用等政策法规。",
        "- `03_standards_specs/`：公开示范文本、标准目录和规范引用资料。",
        "- `04_standard_phrases/`：自建水利投标标准话术、检查清单、施工组织设计模板。",
        "- `index.csv` / `index.jsonl`：RAG 入库元数据索引。",
        "",
        "## 本次采集数量",
        "",
    ]
    for category, count in sorted(counts.items()):
        lines.append(f"- `{category}`：{count} 条")
    lines.extend(
        [
            "",
            "## 入库建议",
            "",
            "1. 优先导入 `04_standard_phrases`，这些是可直接用于生成投标文件的自有知识。",
            "2. 再导入 `02_policy_regulations`，用于法规依据、资格条件、质量安全、验收和信用合规问答。",
            "3. 最后导入 `01_tender_documents` 和 `03_standards_specs`，用于学习招标文件结构、评标办法、投标文件格式和技术条款表达。",
            "4. PDF 建议先走 MinerU/OCR，保留页码、表格、章节层级；HTML/Markdown 可以直接按标题层级切片。",
            "",
            "## 版权和使用边界",
            "",
            "本目录优先采集政府网站、公共资源交易平台或政府附件公开资料。标准规范全文通常存在版权边界，后续不要混入来源不明或付费平台搬运的全文资料；可通过标准名称、适用场景、条文引用位置和企业自有理解形成可检索的二级知识。",
            "",
            "## 重新下载",
            "",
            "```bash",
            "python rag_seed/water_resources/_scripts/download_water_rag_seed.py",
            "```",
            "",
        ]
    )
    readme.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    rows = []
    rows.extend(download_sources())
    rows.extend(write_generated_docs())
    write_indexes(rows)
    write_readme(rows)
    print(f"Done. {len(rows)} corpus items written under {ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
