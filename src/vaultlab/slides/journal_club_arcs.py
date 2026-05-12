"""Journal-club narrative arcs by paper type.

Absorbed from the nature-paper2ppt skill (Yuan Yizhe, SJTU) at
nature-skills/skills/nature-paper2ppt/. Each arc maps a paper type to the
ordered slide structure that best supports the paper's actual scientific
argument — not the manuscript section order.

Pattern source: nature-paper2ppt's seven paper-type arcs.

Public API
----------

- :data:`JOURNAL_CLUB_ARCS` — registry of arc dicts keyed by paper-type
  slug (e.g. ``"discovery"``, ``"methods"``, ``"dataset"``)
- :func:`get_arc` — fetch an arc by slug
- :func:`arc_to_slide_plan` — convert an arc into a list of slide-plan
  dicts ready for ``vaultlab.slides.build_from_plan``
- :func:`classify_paper_type` — heuristic paper-type classifier from
  a frontmatter dict / abstract / title

Each arc is structured as ::

    {
      "slug": "discovery",
      "name": "Discovery / mechanism paper",
      "default_logic": "question-to-evidence",
      "slides": [
        {"title": "Why this matters", "purpose": "...", "type": "bullets"},
        ...
      ],
      "language": "en",  # or "zh-CN" for Chinese variant
    }

Slide entries are skeletons — the actual content is filled in by the deck
plan generator, but the *order* and *role* of each slide is fixed by the
arc.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

ArcLanguage = Literal["en", "zh-CN"]


# ---------------------------------------------------------------------------
# English arc definitions


_DISCOVERY_ARC: dict[str, Any] = {
    "slug": "discovery",
    "name": "Discovery / mechanism paper",
    "default_logic": "question-to-evidence",
    "slides": [
        {"title": "Why this phenomenon matters", "purpose": "context", "type": "bullets"},
        {"title": "What's unknown about the mechanism", "purpose": "gap", "type": "bullets"},
        {"title": "The hypothesis the authors test", "purpose": "claim", "type": "bullets"},
        {"title": "Experimental design", "purpose": "method", "type": "figure"},
        {"title": "Key evidence #1", "purpose": "evidence", "type": "figure"},
        {"title": "Key evidence #2", "purpose": "evidence", "type": "figure"},
        {"title": "Key evidence #3 (or robustness)", "purpose": "evidence", "type": "figure"},
        {"title": "Proposed mechanism / model", "purpose": "model", "type": "figure"},
        {"title": "Limitations and next experiments", "purpose": "limitations", "type": "bullets"},
    ],
    "language": "en",
}


_METHODS_ARC: dict[str, Any] = {
    "slug": "methods",
    "name": "Methods / algorithm / tool paper",
    "default_logic": "problem-to-solution",
    "slides": [
        {"title": "The current bottleneck", "purpose": "context", "type": "bullets"},
        {
            "title": "What the proposed method does differently",
            "purpose": "claim",
            "type": "bullets",
        },
        {"title": "Workflow / architecture", "purpose": "method", "type": "figure"},
        {"title": "Evaluation design", "purpose": "method", "type": "bullets"},
        {"title": "Performance vs baselines", "purpose": "evidence", "type": "figure"},
        {"title": "Ablation / robustness", "purpose": "evidence", "type": "figure"},
        {"title": "Failure modes (where it breaks)", "purpose": "evidence", "type": "figure"},
        {"title": "Reuse scenarios + limitations", "purpose": "limitations", "type": "bullets"},
    ],
    "language": "en",
}


_DATASET_ARC: dict[str, Any] = {
    "slug": "dataset",
    "name": "Resource / dataset / atlas / benchmark paper",
    "default_logic": "workflow-to-validation",
    "slides": [
        {"title": "Why this resource was needed", "purpose": "context", "type": "bullets"},
        {"title": "Cohort / sample design", "purpose": "method", "type": "bullets"},
        {"title": "Generation + QC workflow", "purpose": "method", "type": "figure"},
        {"title": "Headline landscape / map", "purpose": "evidence", "type": "figure"},
        {"title": "Validation + reproducibility", "purpose": "evidence", "type": "figure"},
        {
            "title": "Example biological / technical insight",
            "purpose": "evidence",
            "type": "figure",
        },
        {"title": "Access, reuse, boundaries", "purpose": "limitations", "type": "bullets"},
    ],
    "language": "en",
}


_CLINICAL_ARC: dict[str, Any] = {
    "slug": "clinical",
    "name": "Clinical / population / intervention study",
    "default_logic": "design-to-inference",
    "slides": [
        {"title": "Clinical / public-health problem", "purpose": "context", "type": "bullets"},
        {"title": "The study question", "purpose": "claim", "type": "bullets"},
        {"title": "Cohort / trial design", "purpose": "method", "type": "figure"},
        {"title": "Endpoints + variables", "purpose": "method", "type": "bullets"},
        {"title": "Primary result", "purpose": "evidence", "type": "figure"},
        {"title": "Subgroup + sensitivity analyses", "purpose": "evidence", "type": "figure"},
        {
            "title": "Bias, limitations, practical implication",
            "purpose": "limitations",
            "type": "bullets",
        },
    ],
    "language": "en",
}


_MATERIALS_ARC: dict[str, Any] = {
    "slug": "materials",
    "name": "Materials / chemistry / physics / engineering paper",
    "default_logic": "property-to-mechanism",
    "slides": [
        {"title": "Target property / technical challenge", "purpose": "context", "type": "bullets"},
        {"title": "Design principle", "purpose": "claim", "type": "figure"},
        {"title": "Synthesis / fabrication / setup", "purpose": "method", "type": "figure"},
        {"title": "Characterization", "purpose": "evidence", "type": "figure"},
        {"title": "Performance evidence", "purpose": "evidence", "type": "figure"},
        {
            "title": "Mechanism / structure–property relationship",
            "purpose": "model",
            "type": "figure",
        },
        {
            "title": "Scalability, stability, application boundary",
            "purpose": "limitations",
            "type": "bullets",
        },
    ],
    "language": "en",
}


_REVIEW_ARC: dict[str, Any] = {
    "slug": "review",
    "name": "Review / perspective / commentary",
    "default_logic": "evidence-map",
    "slides": [
        {"title": "Why this topic matters now", "purpose": "context", "type": "bullets"},
        {"title": "Conceptual framework", "purpose": "claim", "type": "figure"},
        {"title": "Theme 1", "purpose": "evidence", "type": "figure"},
        {"title": "Theme 2", "purpose": "evidence", "type": "figure"},
        {"title": "Theme 3", "purpose": "evidence", "type": "figure"},
        {
            "title": "Open controversy / unresolved problem",
            "purpose": "limitations",
            "type": "bullets",
        },
        {"title": "Author's synthesis + future directions", "purpose": "model", "type": "bullets"},
    ],
    "language": "en",
}


_JOURNAL_CLUB_DEFAULT_ARC: dict[str, Any] = {
    "slug": "journal_club_default",
    "name": "Journal-club default (generic)",
    "default_logic": "claim-first",
    "slides": [
        {"title": "Paper context + significance", "purpose": "context", "type": "bullets"},
        {"title": "What the paper claims", "purpose": "claim", "type": "bullets"},
        {"title": "How they tested it", "purpose": "method", "type": "figure"},
        {"title": "Headline evidence", "purpose": "evidence", "type": "figure"},
        {"title": "Supporting evidence + controls", "purpose": "evidence", "type": "figure"},
        {"title": "What's new / reusable", "purpose": "model", "type": "bullets"},
        {"title": "Limitations + discussion points", "purpose": "limitations", "type": "bullets"},
    ],
    "language": "en",
}


# Registry — paper-type slug → arc dict.
JOURNAL_CLUB_ARCS: dict[str, dict[str, Any]] = {
    "discovery": _DISCOVERY_ARC,
    "methods": _METHODS_ARC,
    "dataset": _DATASET_ARC,
    "clinical": _CLINICAL_ARC,
    "materials": _MATERIALS_ARC,
    "review": _REVIEW_ARC,
    "journal_club_default": _JOURNAL_CLUB_DEFAULT_ARC,
}


# ---------------------------------------------------------------------------
# Chinese title translations (nature-paper2ppt is Chinese-first; we mirror)


_TITLE_TRANSLATIONS: dict[str, str] = {
    # Generic
    "Paper context + significance": "论文背景与意义",
    "What the paper claims": "论文核心主张",
    "How they tested it": "实验设计 / 研究方法",
    "Headline evidence": "关键证据",
    "Supporting evidence + controls": "支持证据与对照",
    "What's new / reusable": "创新点与可复用价值",
    "Limitations + discussion points": "局限性与讨论",
    # Discovery
    "Why this phenomenon matters": "为什么这个现象重要",
    "What's unknown about the mechanism": "机制层面的未知",
    "The hypothesis the authors test": "作者提出的假设",
    "Experimental design": "实验设计",
    "Key evidence #1": "关键证据 #1",
    "Key evidence #2": "关键证据 #2",
    "Key evidence #3 (or robustness)": "关键证据 #3 / 稳健性",
    "Proposed mechanism / model": "提出的机制 / 模型",
    "Limitations and next experiments": "局限性与下一步实验",
    # Methods
    "The current bottleneck": "当前技术瓶颈",
    "What the proposed method does differently": "新方法的核心差异",
    "Workflow / architecture": "工作流 / 架构",
    "Evaluation design": "评测设计",
    "Performance vs baselines": "对比基线的性能",
    "Ablation / robustness": "消融实验 / 稳健性",
    "Failure modes (where it breaks)": "失败模式",
    "Reuse scenarios + limitations": "可复用场景与局限",
    # Dataset
    "Why this resource was needed": "为什么需要这个资源",
    "Cohort / sample design": "样本队列设计",
    "Generation + QC workflow": "生成与质控流程",
    "Headline landscape / map": "整体图谱",
    "Validation + reproducibility": "验证与可重复性",
    "Example biological / technical insight": "示例生物学 / 技术发现",
    "Access, reuse, boundaries": "获取、复用与边界",
    # Clinical
    "Clinical / public-health problem": "临床 / 公卫问题",
    "The study question": "研究问题",
    "Cohort / trial design": "队列 / 试验设计",
    "Endpoints + variables": "终点与变量",
    "Primary result": "主要结果",
    "Subgroup + sensitivity analyses": "亚组与敏感性分析",
    "Bias, limitations, practical implication": "偏倚、局限与实际意义",
    # Materials
    "Target property / technical challenge": "目标性质 / 技术挑战",
    "Design principle": "设计原则",
    "Synthesis / fabrication / setup": "合成 / 制备 / 装置",
    "Characterization": "表征",
    "Performance evidence": "性能证据",
    "Mechanism / structure–property relationship": "机制 / 结构–性能关系",
    "Scalability, stability, application boundary": "可扩展性、稳定性与应用边界",
    # Review
    "Why this topic matters now": "为什么这个话题现在重要",
    "Conceptual framework": "概念框架",
    "Theme 1": "主题 1",
    "Theme 2": "主题 2",
    "Theme 3": "主题 3",
    "Open controversy / unresolved problem": "未解争议 / 开放问题",
    "Author's synthesis + future directions": "作者综合视角与未来方向",
}


def get_arc(slug: str, *, language: ArcLanguage = "en") -> dict[str, Any]:
    """Fetch an arc by slug. Raises KeyError for unknown slug.

    If ``language="zh-CN"``, returns the arc with Chinese slide titles
    (English titles fall through unchanged).
    """
    if slug not in JOURNAL_CLUB_ARCS:
        raise KeyError(f"Unknown paper-type slug: {slug!r}. Available: {sorted(JOURNAL_CLUB_ARCS)}")
    arc = deepcopy(JOURNAL_CLUB_ARCS[slug])
    if language == "zh-CN":
        arc["language"] = "zh-CN"
        for slide in arc["slides"]:
            slide["title"] = _TITLE_TRANSLATIONS.get(slide["title"], slide["title"])
    return arc


def arc_to_slide_plan(
    arc: dict[str, Any],
    *,
    deck_title: str = "",
    deck_subtitle: str = "",
) -> dict[str, Any]:
    """Convert an arc into a slide-plan dict ready for build_from_plan.

    Returns a dict with ``title``, ``subtitle``, and ``slides`` (each slide
    has ``type``, ``title``, ``bullets=[]``, plus the arc's ``purpose``
    field preserved as metadata).
    """
    slides_out: list[dict[str, Any]] = []
    # Title slide always first
    slides_out.append(
        {
            "type": "title",
            "title": deck_title or arc["name"],
            "subtitle": deck_subtitle,
            "bullets": [],
        }
    )
    for slide in arc["slides"]:
        slides_out.append(
            {
                "type": slide.get("type", "bullets"),
                "title": slide["title"],
                "bullets": [],
                "_purpose": slide.get("purpose", ""),
            }
        )
    return {
        "title": deck_title or arc["name"],
        "subtitle": deck_subtitle,
        "language": arc.get("language", "en"),
        "arc_slug": arc["slug"],
        "arc_logic": arc.get("default_logic", ""),
        "slides": slides_out,
    }


def classify_paper_type(metadata: dict[str, Any]) -> str:
    """Heuristic paper-type classifier.

    Inspects (in order): an explicit ``paper_type`` field, the title +
    abstract for keyword hits, and the journal name. Returns one of the
    arc slugs in :data:`JOURNAL_CLUB_ARCS`.

    Defaults to ``"journal_club_default"`` when nothing matches.
    """
    explicit = (metadata.get("paper_type") or "").lower()
    if explicit in JOURNAL_CLUB_ARCS:
        return explicit

    text = " ".join(
        str(metadata.get(k, "")) for k in ("title", "abstract", "tldr", "journal")
    ).lower()

    rules: list[tuple[tuple[str, ...], str]] = [
        # Strong indicators
        (("dataset", "atlas", "benchmark", "resource"), "dataset"),
        (("randomized", "clinical trial", "cohort", "phase ii", "phase iii", "rct"), "clinical"),
        (("algorithm", "neural network", "deep learning", "framework", "tool"), "methods"),
        (("synthesis", "fabrication", "characterization", "materials", "alloy"), "materials"),
        (("review", "perspective", "commentary", "outlook"), "review"),
        # Discovery (default-ish — last)
        (("mechanism", "discover", "uncover", "reveal"), "discovery"),
    ]
    for keywords, slug in rules:
        if any(k in text for k in keywords):
            return slug

    return "journal_club_default"


__all__ = [
    "JOURNAL_CLUB_ARCS",
    "ArcLanguage",
    "arc_to_slide_plan",
    "classify_paper_type",
    "get_arc",
]
