#!/usr/bin/env python3
"""
零依赖语义搜索索引

目标：让"帮我写测试用例"这类自然语言查询能命中 test-driven-development，
而不是像 SQL LIKE 那样只能靠字面包含。

实现：TF-IDF + 余弦相似度，纯标准库，无 numpy / torch / 模型下载依赖。
当前 235 个技能的规模下，暴力余弦计算在毫秒级完成。

中文处理：中文没有空格，采用「单字 + 字符 bigram」切分，
"测试" -> ["测", "试", "测试"]，兼顾召回与精度。

若后续安装 sentence-transformers 或配置了 embedding API，
可在 db.search 中把 backend 替换为真向量，本模块接口保持不变。
"""

import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).parent.parent
INDEX_PATH = PROJECT_ROOT / "data" / "search-index.json"
INDEX_VERSION = 1

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_+\-#\.]*")
CJK_RE = re.compile(r"[\u4e00-\u9fff]+")

# 英文高频虚词，对语义区分无贡献
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "of", "to", "in", "on",
    "for", "with", "from", "by", "at", "as", "is", "are", "be", "this", "that",
    "it", "use", "used", "using", "when", "you", "your", "how", "what", "can",
    "will", "should", "do", "does", "skill", "skills", "please", "help", "me",
    "i", "my", "we", "our",
}

# 名称权重：技能名比正文更能代表语义
NAME_REPEAT = 3

# description 末尾的触发模板句（建索引时剥离，见 strip_trigger_tail）
TRIGGER_TAIL_RE = re.compile(
    r"[\u3002\s]*当用户[^。]*时触发本技能[\u3002\s]*$"
    r"|\s*Use this skill when [^.]*\.\s*$",
    re.S,
)


def tokenize(text: str) -> List[str]:
    """中英文混合分词：英文按词，中文按单字 + bigram"""
    if not text:
        return []
    text = text.lower()
    tokens: List[str] = []

    for w in TOKEN_RE.findall(text):
        if len(w) > 1 and w not in STOPWORDS:
            tokens.append(w)

    for seg in CJK_RE.findall(text):
        if len(seg) == 1:
            tokens.append(seg)
            continue
        # 单字保证召回，bigram 保证精度
        for ch in seg:
            tokens.append(ch)
        for i in range(len(seg) - 1):
            tokens.append(seg[i:i + 2])

    return tokens


def _tf_counts(tokens: List[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1
    return counts


class SemanticIndex:
    """稀疏 TF-IDF 向量索引"""

    def __init__(self) -> None:
        self.version = INDEX_VERSION
        self.keys: List[Tuple[str, str, str]] = []   # (namespace, name, owner)
        self.df: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.vectors: List[Dict[str, float]] = []
        self.n = 0

    # ---------- 构建 ----------
    def build(self, docs: List[Tuple[Tuple[str, str, str], str]]) -> None:
        """docs: [((namespace, name, owner), text), ...]"""
        self.keys = [k for k, _ in docs]
        self.n = len(docs)
        self.df = {}
        token_lists: List[Dict[str, int]] = []

        for _, text in docs:
            tf = _tf_counts(tokenize(text))
            token_lists.append(tf)
            for term in tf:
                self.df[term] = self.df.get(term, 0) + 1

        self.idf = {
            t: math.log((self.n + 1) / (df + 1)) + 1.0
            for t, df in self.df.items()
        }

        self.vectors = []
        for tf in token_lists:
            vec: Dict[str, float] = {}
            for term, cnt in tf.items():
                # 次线性 tf，避免长文档靠堆词取胜
                vec[term] = (1.0 + math.log(cnt)) * self.idf.get(term, 1.0)
            self.vectors.append(_l2_normalize(vec))

    # ---------- 查询 ----------
    def search(self, query: str, top_k: int = 20) -> List[Tuple[Tuple[str, str, str], float]]:
        if not self.vectors or not query:
            return []
        q_vec = _l2_normalize(self._vectorize(expand_query(query)))
        if not q_vec:
            return []
        scored = []
        for key, vec in zip(self.keys, self.vectors):
            score = _sparse_dot(q_vec, vec)
            if score > 0:
                scored.append((key, score))
        scored.sort(key=lambda x: -x[1])
        return scored[:top_k]

    def _vectorize(self, text: str) -> Dict[str, float]:
        tf = _tf_counts(tokenize(text))
        vec = {}
        for term, cnt in tf.items():
            if term in self.idf:
                vec[term] = (1.0 + math.log(cnt)) * self.idf[term]
        return vec

    # ---------- 持久化 ----------
    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "n": self.n,
            "keys": [list(k) for k in self.keys],
            "idf": self.idf,
            "vectors": self.vectors,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Optional["SemanticIndex"]:
        if data.get("version") != INDEX_VERSION:
            return None
        idx = cls()
        idx.n = data.get("n", 0)
        idx.keys = [tuple(k) for k in data.get("keys", [])]
        idx.idf = data.get("idf", {})
        idx.vectors = data.get("vectors", [])
        if not idx.keys or len(idx.keys) != len(idx.vectors):
            return None
        return idx

    def save(self, path: Path = INDEX_PATH) -> None:
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path = INDEX_PATH) -> Optional["SemanticIndex"]:
        if not path.exists():
            return None
        try:
            return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            return None


def _l2_normalize(vec: Dict[str, float]) -> Dict[str, float]:
    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm == 0:
        return {}
    return {k: v / norm for k, v in vec.items()}


def _sparse_dot(a: Dict[str, float], b: Dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(w * b[k] for k, w in a.items() if k in b)


# 中文查询 → 英文术语扩展：库内大量技能描述为英文，
# 纯中文查询与其词元零重叠，靠此表打通跨语言召回。
QUERY_SYNONYMS = {
    "测试": ["test", "testing", "qa"], "用例": ["test", "case"],
    "单元": ["unit"], "集成": ["integration"], "回归": ["regression"],
    "代码": ["code"], "编程": ["coding", "programming"], "开发": ["development"],
    "审查": ["review", "audit"], "评审": ["review"], "重构": ["refactor"],
    "设计": ["design"], "设计稿": ["figma", "design"], "原型": ["prototype"],
    "前端": ["frontend", "ui"], "后端": ["backend", "server"],
    "页面": ["page", "ui"], "组件": ["component"], "样式": ["css", "style"],
    "浏览器": ["browser"], "自动化": ["automation", "automate"],
    "部署": ["deploy", "deployment"], "发布": ["release", "publish"],
    "文档": ["docs", "documentation"], "注释": ["comment"],
    "安全": ["security"], "漏洞": ["vulnerability", "security"],
    "性能": ["performance"], "优化": ["optimize", "performance"],
    "数据库": ["database", "sql"], "查询": ["query"], "缓存": ["cache"],
    "接口": ["api"], "请求": ["request"], "服务": ["service"],
    "图片": ["image", "picture"], "视频": ["video"], "音频": ["audio"],
    "文件": ["file"], "目录": ["directory", "folder"],
    "数据": ["data"], "分析": ["analysis", "analyze"], "报表": ["report"],
    "生成": ["generate", "generator"], "创建": ["create"], "写": ["write", "create"],
    "转换": ["convert", "transform"], "迁移": ["migrate", "migration"],
    "监控": ["monitor", "observability"], "日志": ["log", "logging"],
    "团队": ["team"], "协作": ["collaboration"], "项目": ["project"],
    "流程": ["workflow", "process"], "任务": ["task"], "计划": ["plan", "planning"],
    "安装": ["install", "setup"], "配置": ["config", "configuration"],
    "模型": ["model", "llm"], "提示": ["prompt"], "智能体": ["agent"],
    "搜索": ["search"], "排序": ["sort"], "校验": ["validate", "validation"],
    "支付": ["payment"], "登录": ["login", "auth"], "用户": ["user"],
    "小程序": ["miniprogram", "wechat"], "微信": ["wechat"],
    "爬": ["crawl", "scrape"], "抓取": ["crawl", "scrape"],
    "图表": ["chart", "diagram"], "可视化": ["visualization", "chart"],
}


def expand_query(query: str) -> str:
    """中文查询补充英文术语，打通中英跨语言召回"""
    if not query or not re.search(r"[\u4e00-\u9fff]", query):
        return query
    extra: List[str] = []
    for zh, ens in QUERY_SYNONYMS.items():
        if zh in query:
            extra.extend(ens)
    if not extra:
        return query
    # 重复一次以加权，避免被原查询的长尾词稀释
    return query + " " + " ".join(extra) + " " + " ".join(extra)


def strip_trigger_tail(text: str) -> str:
    """剥离 description 末尾的“何时使用”模板句

    该句由 fix-skill-metadata.py --add-triggers 批量追加，是给 Agent 判断激活用的；
    建索引时必须去掉，否则上百条描述共享同一模板会稀释 TF-IDF 区分度。
    """
    return TRIGGER_TAIL_RE.sub("", text or "")


def build_index_text(skill: Dict[str, Any]) -> str:
    """拼装用于建索引的文本：名称加权，描述与分类补充"""
    name = skill.get("name", "")
    parts = [f"{name} "] * NAME_REPEAT
    for field in ("name_zh", "name_en", "description", "description_zh",
                  "description_en", "category_name"):
        v = skill.get(field)
        if v:
            parts.append(strip_trigger_tail(str(v)))
    tags = skill.get("tags", "")
    if tags:
        parts.append(str(tags).replace(",", " "))
    return " ".join(parts)
