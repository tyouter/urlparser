"""
Harness Gate: evaluate urlparser generic-webpage extraction quality.

Compares current urlparser output against trafilatura ceiling and baseline .md files.
Outputs a scored table + gate verdict, exits 0 if all gates pass, 1 otherwise.

Usage:
    python iteration/harness/evaluate.py
"""
import asyncio
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import trafilatura
from urlparser import parse, ParseConfig

TESTCASE_DIR = REPO_ROOT / "output" / "urlparser testcases"

# ============================================================
# Test URL Configuration (from README.md 2026-05-09)
# ============================================================
@dataclass
class TestCase:
    id: str
    url: str
    tier: str          # "good_case" | "general" | "bad_case"
    baseline_md: str   # relative to TESTCASE_DIR/tier/

TEST_URLS = [
    # ---- good_case: 国内可访问, 必须零回归 ----
    TestCase("csdn",              "https://blog.csdn.net/HeFlyYoung/article/details/124149314",           "good_case", "CSDN技术博客.md"),
    TestCase("sspai",             "https://sspai.com/post/97131",                                         "good_case", "少数派Markdown方案对比.md"),
    TestCase("cubox_jobs",        "https://cubox.pro/doc/jobs.html",                                      "good_case", "Cubox招聘页面.md"),
    TestCase("wiz",               "https://www.wiz.cn/xapp",                                               "good_case", "为知笔记首页.md"),
    TestCase("cubox_help",        "https://help.cubox.pro/hi/8218",                                        "good_case", "Cubox功能导游帮助.md"),
    TestCase("feishu",            "https://lcnziv86vkx6.feishu.cn/wiki/BOWXwqEL2iZKnFkbRBWcSq93nng",       "good_case", "一人公司9款APP飞书文档.md"),
    # ---- general: 大文档, 内容量必须提升 ----
    TestCase("weixin_harness",    "https://mp.weixin.qq.com/s/sVGeofV9uTgvhgR44q8pNA",                    "general",   "微信文章_Harness才是关键.md"),
    TestCase("zhihu_claude",      "https://www.zhihu.com/answer/1995525473137099738",                      "general",   "知乎_Claude代码能力.md"),
    # ---- bad_case: Dribbble, 必须突破空壳 ----
    TestCase("dribbble_cred",     "https://dribbble.com/shots/25795063",                                   "bad_case",  "Credivance_Dribbble融资deck.md"),
    TestCase("dribbble_lumore",   "https://dribbble.com/shots/26148325",                                   "bad_case",  "LUMORE_Dribbble护肤deck.md"),
]

# ============================================================
# Scoring engine
# ============================================================
NAV_KEYWORDS = [
    "搜索", "登录", "注册", "菜单", "广告",
    "footer", "license", "copyright", "skip to main content",
    "sign in", "sign up", "menu", "search", "subscribe",
    "share", "related", "recommended", "sponsored",
    "cookie", "privacy policy", "terms of service",
]

TRUNCATION_END = re.compile(
    r'[。！？.!?…"""\'\)\}\]>]$|```\s*$|</\w+>\s*$', re.MULTILINE
)

@dataclass
class DimScore:
    name: str
    score: int
    max_score: int = 3
    detail: str = ""

@dataclass
class CaseResult:
    tc: TestCase
    success: bool
    error: str = ""
    parse_time: float = 0.0
    content: str = ""
    baseline: str = ""
    ceiling: str = ""
    dims: list = field(default_factory=list)
    total: int = 0
    max_total: int = 18


def count_headings(text: str) -> int:
    return len(re.findall(r'^#{1,3}\s', text or '', re.MULTILINE))

def count_links(text: str) -> int:
    return len(re.findall(r'\]\(https?://', text or ''))

def count_code_blocks(text: str) -> int:
    return len(re.findall(r'```', text or '')) // 2

def count_list_items(text: str) -> int:
    return len(re.findall(r'^[\-\*]\s', text or '', re.MULTILINE))


def dim_content_volume(improved: str, ceiling: str) -> DimScore:
    imp = len(improved.strip()) if improved else 0
    ceil = len(ceiling.strip()) if ceiling else 1
    if ceil < 200:
        return DimScore("内容量", 3, detail=f"tiny page (ceiling={ceil} chars)")
    r = imp / ceil
    if r >= 0.80: s = 3
    elif r >= 0.50: s = 2
    elif r >= 0.20: s = 1
    else: s = 0
    return DimScore("内容量", s, detail=f"improved={imp} / ceiling={ceil} = {r:.1%}")

def dim_structure(improved: str, baseline: str) -> DimScore:
    ih = count_headings(improved); bh = count_headings(baseline)
    ic = count_code_blocks(improved); bc = count_code_blocks(baseline)
    il = count_list_items(improved); bl = count_list_items(baseline)
    if bh == 0 and bc == 0 and bl == 0:
        return DimScore("结构保留", 3, detail="baseline has no structure")
    lost = max(0, bh - ih) + max(0, bc - ic) + max(0, bl - il)
    if lost == 0: s = 3
    elif lost <= 2: s = 2
    elif lost <= 5: s = 1
    else: s = 0
    return DimScore("结构保留", s, detail=f"headings({ih}/{bh}) code({ic}/{bc}) lists({il}/{bl})")

def dim_nav_pollution(improved: str) -> DimScore:
    first50 = " ".join((improved or "").split("\n")[:50]).lower()
    found = [kw for kw in NAV_KEYWORDS if kw.lower() in first50]
    c = len(found)
    if c == 0: s = 3
    elif c <= 2: s = 2
    elif c <= 5: s = 1
    else: s = 0
    return DimScore("导航污染", s, detail=f"{c} keywords in first 50 lines: {found[:4]}")

def dim_truncation(improved: str) -> DimScore:
    if not improved or len(improved.strip()) < 100:
        return DimScore("截断检测", 3, detail="too short to judge")
    tail = improved.strip()[-200:]
    if TRUNCATION_END.search(tail):
        return DimScore("截断检测", 3, detail=f"ends: ...{tail[-60:].replace(chr(10),' ')}")
    return DimScore("截断检测", 0, detail=f"TRUNCATED: ...{tail[-80:].replace(chr(10),' ')}")

def dim_link_retention(improved: str, baseline: str) -> DimScore:
    il = count_links(improved); bl = count_links(baseline)
    if bl == 0: return DimScore("链接保留", 3, detail="baseline has no links")
    r = il / bl
    if r >= 0.80: s = 3
    elif r >= 0.50: s = 2
    elif r >= 0.30: s = 1
    else: s = 0
    return DimScore("链接保留", s, detail=f"improved={il} / baseline={bl} = {r:.1%}")

def dim_quality(improved: str, _ceiling: str) -> DimScore:
    if not improved or len(improved.strip()) < 100:
        return DimScore("质量分", 0, detail="too short, needs review")
    words = re.findall(r'\w+', improved.lower())
    if not words: return DimScore("质量分", 0, detail="no words")
    unique_ratio = len(set(words)) / len(words)
    paragraphs = len([p for p in improved.split("\n\n") if len(p.strip()) > 20])
    if unique_ratio > 0.5 and paragraphs >= 3: s = 3
    elif unique_ratio > 0.4 and paragraphs >= 2: s = 2
    elif unique_ratio > 0.3: s = 1
    else: s = 0
    return DimScore("质量分", s, detail=f"unique_ratio={unique_ratio:.2f} paragraphs={paragraphs}")


def evaluate_one(tc: TestCase, improved: str, raw_html: str, baseline: str) -> CaseResult:
    ceiling = ""
    if raw_html:
        try:
            ceiling = trafilatura.extract(raw_html, output_format='markdown', favor_precision=True) or ""
        except Exception:
            pass
    dims = [
        dim_content_volume(improved, ceiling),
        dim_structure(improved, baseline),
        dim_nav_pollution(improved),
        dim_truncation(improved),
        dim_link_retention(improved, baseline),
        dim_quality(improved, ceiling),
    ]
    return CaseResult(tc=tc, success=True, content=improved, baseline=baseline,
                      ceiling=ceiling, dims=dims, total=sum(d.score for d in dims))


async def fetch_one(tc: TestCase) -> tuple:
    start = time.time()
    try:
        result = await parse(tc.url, config=ParseConfig.simple())
        elapsed = round(time.time() - start, 2)
        raw = result.raw_html or ""
        content = result.content or result.raw_text or ""
        return content, raw, result.error, elapsed
    except Exception as e:
        return "", "", str(e), round(time.time() - start, 2)


def load_baseline(tc: TestCase) -> str:
    path = TESTCASE_DIR / tc.tier / tc.baseline_md
    if not path.exists(): return ""
    text = path.read_text(encoding="utf-8")
    m = re.search(r'## 内容摘要\s*\n(.*?)(?=\n## |\n---|\Z)', text, re.DOTALL)
    return m.group(1).strip() if m else text


# ============================================================
# Gate logic (updated per README 2026-05-09)
# ============================================================
def gate_good_case_zero_regression(results: list[CaseResult]) -> tuple[bool, str]:
    """Hard gate 1: good_case content >= baseline, structure not degraded."""
    issues = []
    for r in results:
        if r.tc.tier != "good_case" or not r.success: continue
        imp_len = len(r.content.strip())
        base_len = len(r.baseline.strip())
        if base_len > 100 and imp_len < base_len * 0.90:
            issues.append(f"  {r.tc.id}: content shrunk ({imp_len} < {int(base_len*0.90)} threshold, baseline={base_len})")
        vol = next((d for d in r.dims if d.name == "内容量"), None)
        if vol and vol.score < 2:
            issues.append(f"  {r.tc.id}: content volume regression ({vol.detail})")
    ok = len(issues) == 0
    return ok, "\n".join(issues) if issues else "all good_case pass"

def gate_general_improvement(results: list[CaseResult]) -> tuple[bool, str]:
    """Hard gate 2: general content not lost, structure preserved."""
    issues = []
    for r in results:
        if r.tc.tier != "general" or not r.success: continue
        imp_len = len(r.content.strip())
        base_len = len(r.baseline.strip())
        # Large baseline docs (30KB+) should not lose content
        if base_len > 10000 and imp_len < base_len * 0.50:
            issues.append(f"  {r.tc.id}: significant content loss ({imp_len} vs baseline {base_len})")
        if r.total < 9:
            issues.append(f"  {r.tc.id}: overall score low ({r.total}/18)")
    ok = len(issues) == 0
    return ok, "\n".join(issues) if issues else "all general pass"

def gate_bad_case_breakthrough(results: list[CaseResult]) -> tuple[bool, str]:
    """Hard gate 3: bad_case > 1000 chars and >= 80% of trafilatura ceiling."""
    issues = []
    for r in results:
        if r.tc.tier != "bad_case" or not r.success: continue
        imp_len = len(r.content.strip())
        if imp_len < 1000:
            issues.append(f"  {r.tc.id}: still too short ({imp_len} chars, need >1000)")
        vol = next((d for d in r.dims if d.name == "内容量"), None)
        if vol and vol.score < 2:
            issues.append(f"  {r.tc.id}: volume below threshold ({vol.detail})")
    ok = len(issues) == 0
    return ok, "\n".join(issues) if issues else "all bad_case improved"

def gate_overall_score(results: list[CaseResult]) -> tuple[bool, str]:
    """Total score >= 80%."""
    total = sum(r.total for r in results)
    max_total = sum(r.max_total for r in results)
    pct = total / max_total * 100 if max_total > 0 else 0
    ok = pct >= 80
    return ok, f"total={total}/{max_total} = {pct:.0f}% (threshold: 80%)"


# ============================================================
# Main
# ============================================================
async def main():
    print("=" * 70)
    print("urlparser Generic Extraction Harness — 10 URL Evaluation")
    print("=" * 70)
    print()

    results: list[CaseResult] = []
    fetch_errors = 0
    total_start = time.time()

    for i, tc in enumerate(TEST_URLS, 1):
        print(f"[{i:2d}/{len(TEST_URLS)}] [{tc.tier}] {tc.id}: {tc.url[:70]}...", end=" ", flush=True)
        try:
            improved, raw_html, error, pt = await asyncio.wait_for(fetch_one(tc), timeout=60)
        except asyncio.TimeoutError:
            improved, raw_html, error, pt = "", "", "timeout (60s)", 60

        if error:
            fetch_errors += 1
            print(f"FETCH FAIL: {error[:60]}")
            results.append(CaseResult(tc=tc, success=False, error=error, parse_time=pt))
            continue

        baseline = load_baseline(tc)
        cr = evaluate_one(tc, improved, raw_html, baseline)
        cr.parse_time = pt
        results.append(cr)
        print(f"{'OK' if cr.total >= 9 else 'WEAK'} | score={cr.total}/18 | {pt:.1f}s")

    elapsed_total = round(time.time() - total_start, 1)

    # ---- Table ----
    DIMS = ["内容量", "结构保留", "导航污染", "截断检测", "链接保留", "质量分"]
    print()
    print("=" * 95)
    print(f"{'ID':<18} {'Tier':<10} {'内容量':>4} {'结构':>4} {'导航':>4} {'截断':>4} {'链接':>4} {'质量':>4} {'总分':>6}")
    print("-" * 95)
    for r in results:
        if not r.success:
            print(f"{r.tc.id:<18} {r.tc.tier:<10} {'— FETCH FAILED —':>30} {r.error[:28]}")
            continue
        scores = ["  —"] * 6
        for d in r.dims:
            idx = DIMS.index(d.name)
            scores[idx] = f"{d.score:>4}"
        print(f"{r.tc.id:<18} {r.tc.tier:<10} {scores[0]} {scores[1]} {scores[2]} {scores[3]} {scores[4]} {scores[5]} {r.total:>4}/{r.max_total}")
    print("-" * 95)

    # ---- Detail ----
    print("\n--- Dimension Details ---")
    for r in results:
        if not r.success: continue
        print(f"\n{r.tc.id} [{r.tc.tier}]:")
        for d in r.dims:
            flag = "PASS" if d.score >= 2 else "FAIL"
            print(f"  {flag} {d.name}: {d.score}/{d.max_score} -- {d.detail}")

    # ---- Gates ----
    print("\n" + "=" * 70)
    print("GATE VERDICT")
    print("=" * 70)
    all_pass = True

    for name, fn in [("Gate 1: good_case zero regression", gate_good_case_zero_regression),
                      ("Gate 2: general content improvement", gate_general_improvement),
                      ("Gate 3: bad_case breakthrough", gate_bad_case_breakthrough),
                      ("Gate 4: overall score >= 80%", gate_overall_score)]:
        ok, msg = fn(results)
        print(f"\n{name}: {'PASS' if ok else 'FAIL'}")
        if msg: print(msg)
        all_pass = all_pass and ok

    print(f"\nFetch errors: {fetch_errors}/{len(TEST_URLS)}")
    print(f"Total time: {elapsed_total:.1f}s")
    print(f"\nFinal verdict: {'ALL GATES PASS' if all_pass else 'SOME GATES FAILED'}")
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
    asyncio.run(main())
