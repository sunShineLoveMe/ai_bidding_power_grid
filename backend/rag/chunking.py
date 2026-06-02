"""父子双层分块器（按 doc_role 路由）。

设计依据：`feishu/docs/国家电网物资协议库存标书RAG技术路线评审稿.md` §6。

核心思想（Small-to-Big）：
- 一份文本资料切一次，产出两层 chunk：
    * parent（章/节级）：完整上下文，服务标书正文写作。
    * child（条/款/段级）：小而自洽，服务向量召回、问答、合规判定。
- child 通过 metadata.parent_index 指向同文档内的 parent。
- 召回时“用 child 命中，按场景返回 child 或回溯 parent”。

切分策略按 doc_role 分化（不使用统一固定长度作为主策略）：
- policy_regulation / sgcc_rule / contract_*  -> 章(parent) + 条(child)
- standard_spec                               -> 章节(parent) + 条文(child)
- tender_notice / main_tender_file           -> 段标题(parent) + 编号业务段(child)
- bid_instructions                            -> 全文(parent) + 每条风险(child)
- self_phrase / 其它                          -> 标题段(parent) + 段落(child)

所有策略都先做清洗（去网页导航噪声、采集头、空行折叠），再切分；
兜底（无结构可识别时）按句子边界的定长切分，绝不从字中间截断。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# ---- 清洗 -------------------------------------------------------------------

# 采集脚本写入的元信息头（- 来源 / - 原始链接 / - 采集时间）—— 整行删除
_META_LINE = re.compile(r"^\s*-\s*(来源|原始链接|采集时间)\s*[:：].*$", re.MULTILINE)

# 常见网页导航 / 站点噪声片段（出现在正文开头，需剔除）
_NAV_NOISE_PATTERNS = [
    r"您当前位置[:：].*?正文",
    r"首页\s*\|.*?(登录|注册)",
    r"登录\s+Languages.*?搜索",
    r"Languages\s+English.*?(搜索|无障碍)",
    r"简\s*\|\s*繁\s*\|\s*EN.*?(登录|无障碍)",
    r"大\s+中\s+小",
    r"发布时间[:：]\s*\d{4}-\d{1,2}-\d{1,2}",
    r"更多\s*>>",
]
_NAV_NOISE = re.compile("|".join(f"(?:{p})" for p in _NAV_NOISE_PATTERNS))

# 章 / 条
_CHAPTER = re.compile(r"第[一二三四五六七八九十百零〇\d]+[章编]\s*[^\n　]{0,40}")
_ARTICLE = re.compile(r"第[一二三四五六七八九十百千零〇\d]+条")
# 编号业务段：1. / 1、/ （一） / 一、
_NUM_SECTION = re.compile(r"(?:^|\n)\s*(?:\d{1,2}\s*[.、]|（[一二三四五六七八九十]+）|[一二三四五六七八九十]+、)")


def clean_text(raw: str) -> str:
    """去除采集元信息头、网页导航噪声，折叠多余空行。"""
    text = raw or ""
    # 去掉首个 markdown 标题行后的采集元信息行
    text = _META_LINE.sub("", text)
    text = _NAV_NOISE.sub(" ", text)
    # 折叠空白
    text = re.sub(r"[ \t\u3000]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _strip_title(text: str) -> tuple[str, str]:
    """分离首行 markdown 标题（# xxx），返回 (标题, 余下正文)。"""
    m = re.match(r"#\s*(.+?)\n", text)
    if m:
        return m.group(1).strip(), text[m.end():]
    return "", text


# ---- 数据结构 ----------------------------------------------------------------


@dataclass
class Chunk:
    layer: str                 # "parent" | "child"
    content: str
    index: int
    parent_index: int | None = None
    section: str | None = None
    block_type: str = "paragraph"   # clause | rule | section | paragraph | table | toc
    extra: dict[str, Any] = field(default_factory=dict)


# ---- 兜底定长切分（句子边界回退） -------------------------------------------

_SENT_END = re.compile(r"(?<=[。；！？\n])")


def _length_split(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text] if text.strip() else []
    pieces: list[str] = []
    buf = ""
    for sent in _SENT_END.split(text):
        if not sent:
            continue
        if len(buf) + len(sent) > max_chars and buf:
            pieces.append(buf.strip())
            buf = ""
        buf += sent
    if buf.strip():
        pieces.append(buf.strip())
    return [p for p in pieces if p]


# ---- 按结构切“条” -----------------------------------------------------------


def _split_by_article(chapter_body: str, child_max: int) -> list[str]:
    """把一章正文按“第X条”切成多个 child。"""
    matches = list(_ARTICLE.finditer(chapter_body))
    if not matches:
        return _length_split(chapter_body, child_max)
    children: list[str] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(chapter_body)
        article = chapter_body[start:end].strip()
        if not article:
            continue
        # 单条过长再按句子兜底切，但保留条号在首块
        if len(article) > child_max:
            head = article[: m.end() - m.start()]  # 条号
            for j, piece in enumerate(_length_split(article, child_max)):
                children.append(piece if j == 0 else f"{head} {piece}")
        else:
            children.append(article)
    return children


# ---- 主入口 ------------------------------------------------------------------


def build_parent_child_chunks(
    raw_text: str,
    *,
    doc_role: str,
    parent_max: int = 4000,
    child_max: int = 600,
) -> list[Chunk]:
    """按 doc_role 生成父子分块。返回扁平列表（parent 在前，其 child 紧随）。

    child.parent_index 指向同列表中 parent 的 index。
    """
    text = clean_text(raw_text)
    title, body = _strip_title(text)
    if not body.strip():
        return []

    role = (doc_role or "").lower()
    if role in {"policy_regulation", "sgcc_rule", "contract_general_terms",
                "contract_special_terms", "standard_spec"}:
        return _chunk_clause_doc(title, body, parent_max, child_max)
    if role in {"tender_notice", "bid_notice_prequalification",
                "bid_notice_postqualification", "main_tender_file", "bid_instructions"}:
        return _chunk_section_doc(title, body, parent_max, child_max, role)
    return _chunk_generic(title, body, parent_max, child_max)


def _chunk_clause_doc(title: str, body: str, parent_max: int, child_max: int) -> list[Chunk]:
    """法规/规章/合同/标准：章(parent) + 条(child)。"""
    chunks: list[Chunk] = []
    chapters = list(_CHAPTER.finditer(body))
    idx = 0

    def add_parent(section: str, content: str) -> int:
        nonlocal idx
        p_index = idx
        chunks.append(Chunk(layer="parent", content=content.strip(), index=idx,
                            section=section or title, block_type="section"))
        idx += 1
        return p_index

    if not chapters:
        # 没有“章”，直接按“条”切，全文做一个 parent
        p_index = add_parent(title, body)
        for child in _split_by_article(body, child_max):
            chunks.append(Chunk(layer="child", content=child, index=idx, parent_index=p_index,
                                section=title, block_type="clause"))
            idx += 1
        return chunks

    for i, m in enumerate(chapters):
        start = m.start()
        end = chapters[i + 1].start() if i + 1 < len(chapters) else len(body)
        chapter_title = m.group(0).strip()
        chapter_body = body[start:end].strip()
        p_index = add_parent(chapter_title, chapter_body[:parent_max])
        for child in _split_by_article(chapter_body, child_max):
            chunks.append(Chunk(layer="child", content=child, index=idx, parent_index=p_index,
                                section=chapter_title, block_type="clause"))
            idx += 1
    return chunks


def _chunk_section_doc(title: str, body: str, parent_max: int, child_max: int, role: str) -> list[Chunk]:
    """招标公告/招标文件/投标注意事项：编号业务段。"""
    chunks: list[Chunk] = []
    idx = 0
    # 全文作为一个 parent（公告通常不长）
    chunks.append(Chunk(layer="parent", content=body[:parent_max].strip(), index=idx,
                        section=title, block_type="section"))
    p_index = idx
    idx += 1

    # 按编号业务段切 child
    cuts = [m.start() for m in _NUM_SECTION.finditer(body)]
    block_type = "rule" if role == "bid_instructions" else "clause"
    if not cuts:
        for child in _length_split(body, child_max):
            chunks.append(Chunk(layer="child", content=child, index=idx, parent_index=p_index,
                                section=title, block_type=block_type))
            idx += 1
        return chunks
    cuts = [0] + cuts + [len(body)]
    for i in range(len(cuts) - 1):
        seg = body[cuts[i]:cuts[i + 1]].strip()
        if not seg:
            continue
        if len(seg) > child_max:
            for piece in _length_split(seg, child_max):
                chunks.append(Chunk(layer="child", content=piece, index=idx, parent_index=p_index,
                                    section=title, block_type=block_type))
                idx += 1
        else:
            chunks.append(Chunk(layer="child", content=seg, index=idx, parent_index=p_index,
                                section=title, block_type=block_type))
            idx += 1
    return chunks


def _chunk_generic(title: str, body: str, parent_max: int, child_max: int) -> list[Chunk]:
    """自建话术/未知类型：标题段(parent) + 段落(child)。"""
    chunks: list[Chunk] = []
    idx = 0
    # 按 markdown 二级标题分段；没有则全文一个 parent
    sections = re.split(r"\n(?=#{1,3}\s)", body)
    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        m = re.match(r"#{1,3}\s*(.+)", sec)
        sec_title = m.group(1).strip() if m else (title or "正文")
        chunks.append(Chunk(layer="parent", content=sec[:parent_max], index=idx,
                            section=sec_title, block_type="section"))
        p_index = idx
        idx += 1
        for para in re.split(r"\n\s*\n", sec):
            para = para.strip()
            if not para or para.startswith("#"):
                continue
            for piece in _length_split(para, child_max):
                chunks.append(Chunk(layer="child", content=piece, index=idx, parent_index=p_index,
                                    section=sec_title, block_type="paragraph"))
                idx += 1
    return chunks
