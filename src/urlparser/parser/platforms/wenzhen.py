"""
问真八字 (pcbz.iwzwh.com) 解析器

交互流程 (已探明):
  1. URL 默认打开「基本排盘」(约 996 字, 缺大运 / 流年 / 流月)
  2. 点击侧边栏 ``.sidebar-item`` 中文本为「专业细盘」的元素
     → DOM 从 ~534 节点爆增到 ~1410 节点, 全量数据一次性渲染
  3. 无需滚动, 直接取 ``document.body.innerText`` (~2527 字) 解析

数据块 (12 类, 全部来自专业细盘 innerText):
  四柱 / 十神 / 地支藏干 / 纳音 / 空亡 / 大运 / 流年 / 流月 /
  小运 / 神煞 / 命宫身宫 / 十二长生

innerText 中专业细盘网格 6 列布局 (经数据校验):
  [流年, 大运, 年柱, 月柱, 日柱, 时柱]
  - 流年列 (丙午) 主星=七杀 (丙→庚), 纳音=天河水
  - 大运列 (戊午) 主星=偏印 (戊→庚), 纳音=天上火
  - 后 4 列与基本排盘四柱一致
"""
from __future__ import annotations

import asyncio
import re
from typing import Dict, List, Optional, Tuple

from playwright.async_api import Page

from ..base import ArticleParser
from ..models import ParserConfig


# ── 地支藏干数量 (本/中/余气), 用于把扁平藏干列表按柱分组 ──
_DIZHI_CANGGAN_COUNT: Dict[str, int] = {
    "子": 1, "丑": 3, "寅": 3, "卯": 1, "辰": 3, "巳": 3,
    "午": 2, "未": 3, "申": 3, "酉": 1, "戌": 3, "亥": 2,
}

# ── 六十甲子纳音表 ──
_NAYIN_MAP: Dict[str, str] = {
    "甲子": "海中金", "乙丑": "海中金",
    "丙寅": "炉中火", "丁卯": "炉中火",
    "戊辰": "大林木", "己巳": "大林木",
    "庚午": "路旁土", "辛未": "路旁土",
    "壬申": "剑锋金", "癸酉": "剑锋金",
    "甲戌": "山头火", "乙亥": "山头火",
    "丙子": "涧下水", "丁丑": "涧下水",
    "戊寅": "城头土", "己卯": "城头土",
    "庚辰": "白蜡金", "辛巳": "白蜡金",
    "壬午": "杨柳木", "癸未": "杨柳木",
    "甲申": "泉中水", "乙酉": "泉中水",
    "丙戌": "屋上土", "丁亥": "屋上土",
    "戊子": "霹雳火", "己丑": "霹雳火",
    "庚寅": "松柏木", "辛卯": "松柏木",
    "壬辰": "长流水", "癸巳": "长流水",
    "甲午": "沙中金", "乙未": "沙中金",
    "丙申": "山下火", "丁酉": "山下火",
    "戊戌": "平地木", "己亥": "平地木",
    "庚子": "壁上土", "辛丑": "壁上土",
    "壬寅": "金箔金", "癸卯": "金箔金",
    "甲辰": "覆灯火", "乙巳": "覆灯火",
    "丙午": "天河水", "丁未": "天河水",
    "戊申": "大驿土", "己酉": "大驿土",
    "庚戌": "钗钏金", "辛亥": "钗钏金",
    "壬子": "桑柘木", "癸丑": "桑柘木",
    "甲寅": "大溪水", "乙卯": "大溪水",
    "丙辰": "沙中土", "丁巳": "沙中土",
    "戊午": "天上火", "己未": "天上火",
    "庚申": "石榴木", "辛酉": "石榴木",
    "壬戌": "大海水", "癸亥": "大海水",
}


# ── 专业细盘附加块结构化提取脚本 (五行旺衰 / 调候用神 / 宫位 / 六亲社会 / 干支关系逐对) ──
# 单次 evaluate 采集, 每块独立 try/catch, 选择器缺失静默跳过.
_EXTRA_BLOCKS_JS = r"""() => {
  const out = {};
  const clean = (s) => (s || '').replace(/\s+/g, ' ').trim();

  // 1. 五行旺衰 (.pro-pan-wuxing-item)
  try {
    const w = [...document.querySelectorAll('.pro-pan-wuxing-item')]
      .map((e) => (e.textContent || '').trim()).filter(Boolean);
    if (w.length) out.wuxing = w;
  } catch (e) {}

  // 2. 调候用神 (.thys-block)
  try {
    const b = document.querySelector('.thys-block');
    if (b) {
      const titleEl = b.querySelector('.thys-block-title');
      const title = clean(titleEl ? titleEl.textContent : '');
      const tou = [...b.querySelectorAll('.thys-block-tips-text1')]
        .map((e) => (e.textContent || '').trim())
        .filter((x) => x && x !== '透' && x !== '藏');
      const cang = [...b.querySelectorAll('.thys-block-tips-text2')]
        .map((e) => (e.textContent || '').trim())
        .filter((x) => x && x !== '透' && x !== '藏');
      const full = clean(b.textContent);
      if (title || tou.length || cang.length || full) {
        out.tiaohou = { title, tou, cang, full };
      }
    }
  } catch (e) {}

  const parseRow = (el) => {
    const gong = [...el.querySelectorAll('.ganzhi_row_gong span, .ganzhi_row_gong2 span')]
      .map((e) => (e.textContent || '').trim()).filter(Boolean);
    const ss = [...el.querySelectorAll('.ganzhi_row_ss')]
      .map((e) => (e.textContent || '').trim()).filter(Boolean);
    const gz = [...el.querySelectorAll('.ganzhi_row_gz, .ganzhi_row_gz2')]
      .map((e) => (e.textContent || '').trim()).filter(Boolean);
    const ttl = [...el.querySelectorAll('.ganzhi_row_title')]
      .map((e) => (e.textContent || '').trim()).filter(Boolean);
    if (gong.length || ss.length || gz.length || ttl.length) {
      return { gong, ss, gz, title: ttl };
    }
    return null;
  };
  const parseTab = (wrapper) => {
    if (!wrapper) return [];
    const sections = [];
    let cur = null;
    const els = wrapper.querySelectorAll('.ganzhi_wrapper_table_title, .ganzhi_row');
    els.forEach((el) => {
      if (el.classList.contains('ganzhi_wrapper_table_title')) {
        cur = { title: (el.textContent || '').trim(), rows: [] };
        sections.push(cur);
      } else {
        const row = parseRow(el);
        if (row) {
          if (cur === null) { cur = { title: '', rows: [] }; sections.push(cur); }
          cur.rows.push(row);
        }
      }
    });
    return sections;
  };

  // 3. 宫位映射 (.ganzhi_tab03_wrapper)
  try {
    const c = document.querySelector('.ganzhi_tab03_wrapper');
    if (c) {
      const sections = parseTab(c);
      if (sections.length) out.gongwei = { sections, full: clean(c.textContent) };
    }
  } catch (e) {}

  // 4. 六亲 / 社会关系 (.ganzhi_tab04_wrapper)
  try {
    const c = document.querySelector('.ganzhi_tab04_wrapper');
    if (c) {
      const sections = parseTab(c);
      if (sections.length) out.liuqin = { sections, full: clean(c.textContent) };
    }
  } catch (e) {}

  // 5. 干支关系逐对 (.gzchatitem)
  try {
    const items = [...document.querySelectorAll('.gzchatitem')].map((el) => {
      const relEl = el.querySelector('.gzchatitem_relaction');
      const rel = relEl ? (relEl.textContent || '').trim() : '';
      const gz = [...el.querySelectorAll('.gzchatitem_gz')]
        .map((e) => (e.textContent || '').trim()).filter(Boolean);
      return { rel, gz };
    }).filter((it) => it.rel || it.gz.length);
    if (items.length) out.gz_rel = items;
  } catch (e) {}

  return out;
}"""


class WenzhenParser(ArticleParser):
    """问真八字专业细盘解析器。

    策略: 点击「专业细盘」一次 → 全量数据进入 innerText → Python 文本解析。
    """

    platform = "wenzhen"
    platform_domains = ["pcbz.iwzwh.com", "iwzwh.com"]

    # ── 字符集 (用于识别干支 / 十神缩写) ──
    _TIAN_GAN = "甲乙丙丁戊己庚辛壬癸"
    _DI_ZHI = "子丑寅卯辰巳午未申酉戌亥"
    _SHI_SHEN = "财官印比劫食杀伤枭才"  # 十神单字缩写: 财/官/印/比/劫/食/伤/杀/枭/才

    # ── 大运/流年行 CSS 选择器 (级联点击) ──
    _YUN_ITEM = "span.pro-pan-yun-item-small"

    # ── 24 节气 (流月行锚点) ──
    _SOLAR_TERMS = {
        "立春", "雨水", "惊蛰", "春分", "清明", "谷雨",
        "立夏", "小满", "芒种", "夏至", "小暑", "大暑",
        "立秋", "处暑", "白露", "秋分", "寒露", "霜降",
        "立冬", "小雪", "大雪", "冬至", "小寒", "大寒",
    }

    # 专业网格维度标签 (innerText 中按顺序出现)
    _DIM_LABELS = frozenset({
        "主星", "天干", "地支", "藏干", "副星",
        "星运", "自坐", "空亡", "纳音", "神煞",
    })
    # 列标题候选
    _PILLAR_NAMES = frozenset({
        "年柱", "月柱", "日柱", "时柱", "胎元", "命宫", "身宫",
        "流年", "大运", "流月",
    })

    def __init__(self, config: Optional[ParserConfig] = None):
        super().__init__(config)

    # ================================================================
    #  fetch lifecycle
    # ================================================================

    async def _fetch_with_page(self, page: Page, url: str):  # type: ignore[override]
        """goto → 点专业细盘 → 等 DOM 稳定 → extract_content."""
        await page.goto(url, timeout=60000, wait_until="domcontentloaded")
        await asyncio.sleep(2.5)

        await self._switch_to_professional(page)

        content = await self.extract_content(page)
        content["url"] = url
        content["platform"] = self.platform
        content["fetch_success"] = True
        return self.post_process(content)

    async def _switch_to_professional(self, page: Page) -> None:
        """点击「专业细盘」直到大运/流年/流月内容出现 (最多重试 3 次)."""
        for _ in range(3):
            already = await page.evaluate(
                "() => { const t = document.body.innerText || '';"
                "  return t.indexOf('大运') >= 0 && t.indexOf('流年') >= 0"
                "      && t.indexOf('流月') >= 0; }"
            )
            if already:
                return
            # 点击 .sidebar-item 中文本为「专业细盘」的元素
            await page.evaluate("""() => {
                const items = document.querySelectorAll('.sidebar-item');
                for (const el of items) {
                    if (el.textContent.trim() === '专业细盘') { el.click(); return true; }
                }
                for (const el of document.querySelectorAll('*')) {
                    if (el.textContent.trim() === '专业细盘' && el.children.length === 0) {
                        el.click(); return true;
                    }
                }
                return false;
            }""")
            # 等待内容锚点出现
            try:
                await page.wait_for_function(
                    "() => { const t = document.body.innerText || '';"
                    "  return t.indexOf('大运') >= 0 && t.indexOf('流年') >= 0; }",
                    timeout=8000,
                )
            except Exception:
                pass
            await self._wait_dom_stable(page, timeout_ms=5000)
            await asyncio.sleep(0.8)

    async def _wait_dom_stable(self, page: Page, timeout_ms: int = 5000) -> None:
        """等待 DOM 节点数连续 3 次不变."""
        try:
            await page.wait_for_function("""() => new Promise((resolve) => {
                let last = -1, stable = 0;
                const check = () => {
                    const n = document.querySelectorAll('*').length;
                    if (n === last) { stable++; } else { stable = 0; last = n; }
                    if (stable >= 3) { resolve(true); } else { setTimeout(check, 300); }
                };
                check();
            })""", timeout=timeout_ms)
        except Exception:
            await asyncio.sleep(1.0)

    # ================================================================
    #  content extraction
    # ================================================================

    async def extract_content(self, page: Page) -> Dict:
        """默认视图提取 + 大运级联点击提取完整流年/流月.

        流程:
          1. 取专业细盘默认 innerText → 解析四柱/神煞/大运/默认流年流月 (保底)
          2. 遍历大运表逐行点击 → 提取每段流年 → 汇总成完整流年表
          3. 每段流年内逐个点击流年行 → 提取该年12个月流月 → 全量流月表
          4. 点击失败不中断: 无级联数据时回退默认视图流年/流月
        """
        text = await page.evaluate("() => document.body.innerText")
        text = text or ""

        # 解析大运表 (级联点击的依据)
        _lines = [ln.strip() for ln in text.split("\n")]
        _nz = [ln for ln in _lines if ln]
        dayun_rows = self._parse_dayun(_nz)

        # 级联点击: 遍历大运表提取完整流年
        segments: List[Tuple[str, List[List[str]]]] = []
        if dayun_rows:
            try:
                segments = await self._cascade_liunian(page, dayun_rows)
            except Exception:
                segments = []

        # 专业细盘结构化 DOM 块 (五行/调候/宫位/六亲/干支关系逐对, 静态不随大运变化)
        extra = await self._extract_extra_blocks(page)

        # 渲染: 有级联数据则按大运分段, 否则保底默认视图
        return self._parse(text, liunian_segments=segments or None, extra=extra)

    async def _extract_extra_blocks(self, page: Page) -> Dict:
        """提取专业细盘 5 个结构化 DOM 块 (单次 evaluate, 选择器缺失静默跳过).

        块: 五行旺衰 / 调候用神 / 宫位映射 / 六亲社会关系 / 干支关系逐对.
        均为静态 DOM, 不随大运级联变化, 故在默认视图一次性采集.
        """
        try:
            data = await page.evaluate(_EXTRA_BLOCKS_JS)
        except Exception:
            return {}
        return data or {}

    # ================================================================
    #  大运级联点击 (流年全量提取)
    # ================================================================

    async def _cascade_liunian(
        self, page: Page, dayun_rows: List[List[str]]
    ) -> List[Tuple[str, List[List[str]], List[Tuple[str, List[List[str]]]]]]:
        """遍历大运表, 逐行点击提取该段流年, 并对流年逐行点击提取流月.

        Returns: [(大运标签, 流年行列表, [(流年标签, 流月行列表), ...]), ...]
                  大运标签 e.g. "大运 辛酉（5岁 · 1987年起）" / "1~4岁（1983年起）"
                  流年标签 e.g. "流年 2017 丁酉"
                  流月行 = [节气, 日期, 流月干支, 十神, 纳音]
        """
        segments: List[Tuple[str, List[List[str]], List[Tuple[str, List[List[str]]]]]] = []
        for dy_row in dayun_rows:
            # dy_row = [起运年, 年龄, 大运干支, 十神, 纳音]
            if len(dy_row) < 2:
                continue
            start_year = dy_row[0]
            age_text = dy_row[1]
            if not age_text or "岁" not in age_text:
                continue

            # 点击该大运行; 失败则跳过 (保留默认视图保底, 不中断整体流程)
            try:
                clicked = await self._click_dayun_row(page, age_text)
            except Exception:
                clicked = False
            if not clicked:
                continue

            # 等 DOM 稳定 + 流年表刷新
            await self._wait_dom_stable(page, timeout_ms=5000)
            await asyncio.sleep(0.5)

            try:
                seg_text = await page.evaluate("() => document.body.innerText")
            except Exception:
                continue
            seg_nz = [ln for ln in (s.strip() for s in (seg_text or "").split("\n")) if ln]

            # 沿用现有流年解析逻辑
            liunian_rows = self._parse_liunian(seg_nz)
            if not liunian_rows:
                continue

            # 流月级联: 在当前大运段内, 逐个点击流年行提取该年12个月流月
            try:
                liuyue_segments = await self._cascade_liuyue(page, liunian_rows)
            except Exception:
                liuyue_segments = []

            ganzhi = dy_row[2] if len(dy_row) > 2 else "—"
            if ganzhi and ganzhi != "—":
                label = f"大运 {ganzhi}（{age_text} · {start_year}年起）"
            else:
                label = f"{age_text}（{start_year}年起）"
            segments.append((label, liunian_rows, liuyue_segments))
        return segments

    async def _cascade_liuyue(
        self, page: Page, liunian_rows: List[List[str]]
    ) -> List[Tuple[str, List[List[str]]]]:
        """在当前大运段内, 遍历流年行逐个点击提取该年12个月流月.

        Returns: [(流年标签, 流月行列表), ...]
                  流月行 = [节气, 日期, 流月干支, 十神, 纳音]
                  流年标签 e.g. "流年 2017 丁酉"

        约束:
          - 点击失败不中断 (跳过该流年, 保底由默认视图流月兜底)
          - 流年行可能被滚动遮挡, 点击前先 scrollIntoView (见 _click_liunian_row)
        """
        out: List[Tuple[str, List[List[str]]]] = []
        for ln_row in liunian_rows:
            # ln_row = [年份, 流年干支, 十神, 纳音, 小运干支]
            if not ln_row:
                continue
            year = ln_row[0]
            if not re.match(r"^\d{4}$", year or ""):
                continue
            ganzhi = ln_row[1] if len(ln_row) > 1 else "—"

            # 点击该流年行; 失败则跳过 (不中断)
            try:
                clicked = await self._click_liunian_row(page, year)
            except Exception:
                clicked = False
            if not clicked:
                continue

            # 等 DOM 稳定 + 流月表刷新
            await self._wait_dom_stable(page, timeout_ms=5000)
            await asyncio.sleep(0.35)

            try:
                ym_text = await page.evaluate("() => document.body.innerText")
            except Exception:
                continue
            ym_nz = [ln for ln in (s.strip() for s in (ym_text or "").split("\n")) if ln]

            liuyue_rows = self._parse_liuyue(ym_nz)
            if not liuyue_rows:
                continue

            label = (f"流年 {year} {ganzhi}"
                     if ganzhi and ganzhi != "—" else f"流年 {year}")
            out.append((label, liuyue_rows))
        return out

    async def _click_dayun_row(self, page: Page, age_text: str) -> bool:
        """点击指定年龄文本的大运行 (基于 span.pro-pan-yun-item-small)."""
        return await self._click_yun_item(page, age_text, scroll=False)

    async def _click_liunian_row(self, page: Page, year_text: str) -> bool:
        """点击指定年份文本的流年行 (基于 span.pro-pan-yun-item-small).

        流年行可能被滚动遮挡, 点击前先 scrollIntoView 再 click.
        """
        return await self._click_yun_item(page, year_text, scroll=True)

    async def _click_yun_item(
        self, page: Page, target: str, scroll: bool = False
    ) -> bool:
        """点击 .pro-pan-yun-item-small 中文本 === target 的元素 (大运/流年通用).

        scroll=True 时先 scrollIntoView (流年行可能被滚动遮挡).
        失败返回 False, 由调用方保底 (不中断整体流程).
        """
        try:
            return await page.evaluate("""([sel, target, scroll]) => {
                const rows = document.querySelectorAll(sel);
                const match = (el) => el.textContent.trim() === target;
                const doScroll = (el) => {
                    if (scroll) {
                        try { el.scrollIntoView({block: 'center', inline: 'center'}); }
                        catch (e) {}
                    }
                };
                // 优先: 可见 + 精确匹配
                for (const el of rows) {
                    if (match(el) && el.offsetParent !== null) {
                        doScroll(el); el.click(); return true;
                    }
                }
                // 兜底: 即使隐藏也派发 click 事件 (含 scrollIntoView)
                for (const el of rows) {
                    if (match(el)) {
                        doScroll(el);
                        el.dispatchEvent(new Event('click', { bubbles: true }));
                        return true;
                    }
                }
                return false;
            }""", [self._YUN_ITEM, target, scroll])
        except Exception:
            return False

    # ================================================================
    #  text parser (pure python)
    # ================================================================

    def _parse(
        self,
        text: str,
        liunian_segments: Optional[List[Tuple[str, List[List[str]], List[Tuple[str, List[List[str]]]]]]] = None,
        extra: Optional[Dict] = None,
    ) -> Dict:
        # 非空行视图 (保留顺序用于索引)
        lines = [ln.strip() for ln in text.split("\n")]
        nz = [ln for ln in lines if ln]

        parts: List[str] = []

        # ── 标题 + 基本信息 ──
        title = self._parse_title(nz)
        basic_md, basic_meta = self._parse_basic_info(nz)
        parts.append(f"# {title}\n")
        if basic_md:
            parts.append(basic_md + "\n")

        # ── 四柱主网格 (专业细盘, 含 主星/天干/地支/藏干/副星/星运/自坐/空亡/纳音) ──
        dims, col_headers = self._parse_main_grid(nz)
        fuxing_flat: List[str] = []
        if dims:
            parts.append("## 四柱（专业细盘 · 胎命身）\n")
            table_md, fuxing_flat = self._render_main_table(dims, col_headers)
            parts.append(table_md)
            parts.append("")
            # 副星若无法按柱对齐则单独列出 (不丢数据)
            if fuxing_flat:
                parts.append("**副星（藏干十神）**：" + "、".join(fuxing_flat) + "\n")

        # ── 神煞 ──
        shensha = dims.get("神煞", []) if dims else []
        if shensha:
            parts.append("## 神煞\n")
            parts.append("- " + "、".join(shensha) + "\n")
            parts.append("")

        # ── 专业细盘附加块 (五行旺衰 / 调候用神 / 宫位映射 / 六亲社会 / 干支关系逐对) ──
        extra = extra or {}
        for _blk_md in (
            self._fmt_wuxing(extra.get("wuxing")),
            self._fmt_tiaohou(extra.get("tiaohou")),
            self._fmt_gongwei(extra.get("gongwei")),
            self._fmt_liuqin(extra.get("liuqin")),
        ):
            if _blk_md:
                parts.append(_blk_md)
                parts.append("")
        # 干支关系: 天干留意/地支留意 (汇总) + 逐对
        rel_md = self._parse_relations(nz)
        _gz_rel_body = self._fmt_gz_rel_body(extra.get("gz_rel"))
        if rel_md or _gz_rel_body:
            parts.append("## 干支关系\n")
            if rel_md:
                parts.append(rel_md + "\n")
            if _gz_rel_body:
                parts.append(_gz_rel_body + "\n")
            parts.append("")

        # ── 大运 (含首个起始小运) ──
        dayun_rows = self._parse_dayun(nz)
        if dayun_rows:
            parts.append("## 大运\n")
            parts.append(self._fmt_table(
                ["起运年", "年龄", "大运干支", "十神", "纳音"],
                dayun_rows,
            ))
            parts.append("")

        # ── 流年 (默认视图或大运级联全量) ──
        liunian_rows: List[List[str]] = []
        # 流月级联: [(大运标签, 流年标签, 流月行列表), ...] (仅大运级联模式下填充)
        liuyue_cascade: List[Tuple[str, str, List[List[str]]]] = []
        if liunian_segments:
            parts.append(
                f"## 流年（大运级联 · 全量 {len(liunian_segments)} 段）\n"
            )
            for label, seg_rows, ly_segs in liunian_segments:
                parts.append(f"### {label}\n")
                parts.append(self._fmt_table(
                    ["年份", "流年干支", "十神", "纳音", "小运干支"],
                    seg_rows,
                ))
                parts.append("")
                liunian_rows.extend(seg_rows)
                for ly_label, ly_rows in (ly_segs or []):
                    liuyue_cascade.append((label, ly_label, ly_rows))
        else:
            liunian_rows = self._parse_liunian(nz)
            if liunian_rows:
                parts.append("## 流年\n")
                parts.append(self._fmt_table(
                    ["年份", "流年干支", "十神", "纳音", "小运干支"],
                    liunian_rows,
                ))
                parts.append("")

        # ── 流月 (大运·流年级联全量, 或默认视图保底) ──
        if liuyue_cascade:
            total_ly = sum(len(r) for _, _, r in liuyue_cascade)
            parts.append(
                f"## 流月（大运·流年级联 · 全量 {len(liuyue_cascade)} 流年 / "
                f"{total_ly} 节气）\n"
            )
            last_dy: Optional[str] = None
            for dy_label, ly_label, ly_rows in liuyue_cascade:
                if dy_label != last_dy:
                    parts.append(f"### {dy_label}\n")
                    last_dy = dy_label
                parts.append(f"#### {ly_label}\n")
                parts.append(self._fmt_table(
                    ["节气", "日期", "流月干支", "十神", "纳音"],
                    ly_rows,
                ))
                parts.append("")
            liuyue_rows = [r for _, _, rs in liuyue_cascade for r in rs]
        else:
            liuyue_rows = self._parse_liuyue(nz)
            if liuyue_rows:
                parts.append("## 流月\n")
                parts.append(self._fmt_table(
                    ["节气", "日期", "流月干支", "十神", "纳音"],
                    liuyue_rows,
                ))
                parts.append("")

        raw_text = "\n".join(parts)

        metadata: Dict = {"platform": self.platform}
        metadata.update(basic_meta)
        metadata["dayun_count"] = len(dayun_rows)
        metadata["liunian_count"] = len(liunian_rows)
        metadata["liunian_segments"] = len(liunian_segments) if liunian_segments else 0
        metadata["liuyue_count"] = len(liuyue_rows)
        metadata["liuyue_segments"] = len(liuyue_cascade)
        metadata["shensha_count"] = len(shensha)
        metadata["wuxing_count"] = len(extra.get("wuxing") or [])
        metadata["tiaohou"] = 1 if extra.get("tiaohou") else 0
        _gw = extra.get("gongwei") or {}
        metadata["gongwei_palaces"] = sum(
            len(_r.get("gong", []))
            for _s in (_gw.get("sections") or [])
            for _r in _s.get("rows", [])
        )
        _lq = extra.get("liuqin") or {}
        metadata["liuqin_sections"] = len(_lq.get("sections") or [])
        metadata["gz_rel_count"] = len(extra.get("gz_rel") or [])

        return {
            "title": title,
            "content": raw_text,
            "raw_text": raw_text,
            "metadata": metadata,
        }

    # ----------------------------------------------------------------
    #  标题 & 基本信息
    # ----------------------------------------------------------------

    def _parse_title(self, lines: List[str]) -> str:
        """姓名 = 第一条「阴历」行之前最近的非装饰行."""
        for i, ln in enumerate(lines):
            if "阴历" in ln:
                for j in range(i - 1, max(-1, i - 5), -1):
                    cand = lines[j]
                    if (1 <= len(cand) <= 8
                            and re.search(r"[\u4e00-\u9fffA-Za-z0-9]", cand)
                            and cand != "."
                            and "切换" not in cand
                            and "手机版" not in cand):
                        return cand
                break
        return "问真八字"

    def _parse_basic_info(self, lines: List[str]) -> Tuple[str, Dict[str, str]]:
        out: List[str] = []
        meta: Dict[str, str] = {}

        # 性别 + 阴历 (第一条「阴历」行)
        for ln in lines:
            if "阴历" in ln:
                m = re.search(r"(乾造|坤造)", ln)
                if m:
                    meta["gender"] = m.group(1)
                    out.append(f"- **性别**：{m.group(1)}")
                mm = re.search(r"阴历[:：]\s*(.+?)(?:\s*[（(]|$)", ln)
                if mm:
                    lunar = mm.group(1).strip()
                    meta["lunar"] = lunar
                    out.append(f"- **阴历**：{lunar}")
                break

        # 阳历
        for ln in lines:
            if ln.startswith("阳历"):
                mm = re.search(r"阳历[:：]\s*(.+)", ln)
                if mm:
                    solar = mm.group(1).strip()
                    meta["solar_date"] = solar
                    out.append(f"- **阳历**：{solar}")
                break

        # 起运 / 交运 / 空亡 / 司令 (专业细盘区, 从「胎命身」起搜)
        tai_idx = self._find(lines, "胎命身")
        search_from = tai_idx if tai_idx >= 0 else 0
        for ln in lines[search_from:]:
            if ln.startswith("起运"):
                out.append(f"- {ln.strip()}")
                meta["qiyun"] = ln.strip()
            elif ln.startswith("交运"):
                out.append(f"- {ln.strip()}")
                meta["jiaoyun"] = ln.strip()
            elif "空亡" in ln and ("（" in ln or "(" in ln):
                val = ln.strip()
                out.append(f"- **空亡**：{val}")
                meta["kongwang"] = val
            elif ln.startswith("司令"):
                val = re.split(r"[:：]", ln, 1)[-1].strip()
                out.append(f"- **司令**：{val}")
                meta["siling"] = val

        return ("\n".join(out) if out else ""), meta

    # ----------------------------------------------------------------
    #  四柱主网格
    # ----------------------------------------------------------------

    def _parse_main_grid(self, lines: List[str]) -> Tuple[Dict[str, List[str]], List[str]]:
        """解析专业细盘主网格. 返回 (维度字典, 列标题)."""
        tai = self._find(lines, "胎命身")
        if tai < 0:
            return {}, []
        zx = self._find(lines, "主星", tai + 1)
        if zx < 0:
            return {}, []

        header_lines = lines[tai + 1: zx]

        # 维度解析: 从「主星」读到「起运」等边界
        stop_prefixes = ("起运", "交运", "智能古籍", "智能四柱", "干支设置", "开通")
        dims: Dict[str, List[str]] = {}
        current: Optional[str] = None
        i = zx
        while i < len(lines):
            ln = lines[i]
            if any(ln.startswith(p) for p in stop_prefixes):
                break
            if ln in self._DIM_LABELS:
                current = ln
                dims[current] = []
            elif current is not None:
                dims[current].append(ln)
            i += 1

        # 列标题: 取 header 中柱名, 去掉「日期」(合并单元格), 对齐主星列数
        col_headers = [h for h in header_lines
                       if h in self._PILLAR_NAMES and h != "日期"]
        num_cols = len(dims.get("主星", []))
        if num_cols:
            if len(col_headers) > num_cols:
                col_headers = col_headers[:num_cols]
            elif len(col_headers) < num_cols:
                col_headers = col_headers + [
                    f"柱{k + 1}" for k in range(len(col_headers), num_cols)
                ]
        return dims, col_headers

    def _render_main_table(
        self, dims: Dict[str, List[str]], col_headers: List[str]
    ) -> Tuple[str, List[str]]:
        """渲染四柱主表. 返回 (表格 markdown, 无法对齐的副星扁平列表)."""
        num_cols = len(col_headers) or len(dims.get("主星", [])) or 4
        if not col_headers:
            col_headers = [f"柱{i + 1}" for i in range(num_cols)]
        headers = ["项目"] + list(col_headers)

        dz_vals = dims.get("地支", [])
        cg_vals = dims.get("藏干", [])
        fx_vals = dims.get("副星", [])

        # 藏干按柱分组 (依地支藏干数量)
        cg_grouped = self._group_by_pillar(cg_vals, dz_vals, num_cols)
        # 副星: 若总数与藏干一致则按同样方式分组, 否则稍后扁平输出
        fx_grouped = None
        fx_flat: List[str] = []
        if fx_vals and cg_grouped and len(fx_vals) == len(cg_vals):
            fx_grouped = self._group_by_pillar(fx_vals, dz_vals, num_cols)
        elif fx_vals:
            fx_flat = list(fx_vals)

        rows: List[List[str]] = []

        def add(label: str, vals: List[str], join_groups: bool = False,
                groups: Optional[List[List[str]]] = None) -> None:
            if groups is not None:
                cells = [" ".join(g) for g in groups]
            elif join_groups:
                cells = vals
            else:
                cells = vals
            if not cells:
                return
            padded = list(cells[:num_cols]) + [""] * (num_cols - len(cells))
            rows.append([label] + padded[:num_cols])

        add("主星", dims.get("主星", []))
        add("天干", dims.get("天干", []))
        add("地支", dims.get("地支", []))
        if cg_grouped:
            add("藏干", [], groups=cg_grouped)
        else:
            add("藏干", cg_vals[:num_cols])
        if fx_grouped:
            add("副星", [], groups=fx_grouped)
        add("星运(十二长生)", dims.get("星运", []))
        add("自坐", dims.get("自坐", []))
        add("空亡", dims.get("空亡", []))
        add("纳音", dims.get("纳音", []))

        if not rows:
            return "_（无四柱数据）_\n", fx_flat
        return self._fmt_table(headers, rows), fx_flat

    @staticmethod
    def _group_by_pillar(
        vals: List[str], dz_vals: List[str], num_cols: int
    ) -> Optional[List[List[str]]]:
        """按地支藏干数量把扁平 vals 切分到各柱. 总数不匹配返回 None."""
        if not vals or not dz_vals:
            return None
        counts = [_DIZHI_CANGGAN_COUNT.get(dz, 1) for dz in dz_vals[:num_cols]]
        if sum(counts) != len(vals):
            return None
        groups: List[List[str]] = []
        idx = 0
        for c in counts:
            groups.append(vals[idx: idx + c])
            idx += c
        return groups

    # ----------------------------------------------------------------
    #  大运
    # ----------------------------------------------------------------

    def _parse_dayun(self, lines: List[str]) -> List[List[str]]:
        """解析大运. 每行 = [起运年, 年龄, 大运干支, 十神, 纳音].

        innerText 结构 (每格独立一行):
            大
            运
            1983          ← 起始 (1~4岁, 无干支)
            1~4岁
            小            ← 小运子标题 (跳过)
            运
            1987          ← 大运1
            5岁
            辛劫          ← 天干+十神
            酉劫          ← 地支+十神
            1997 ...
        """
        start = self._find_marker(lines, "大", "运")
        if start < 0:
            return []
        end = self._find_marker(lines, "流", "年", start)  # 大运终于流年
        if end < 0:
            end = len(lines)

        rows: List[List[str]] = []
        i = start
        while i < end:
            ln = lines[i]
            if ln in ("小", "运", "大"):
                i += 1
                continue
            if re.match(r"^\d{4}$", ln):
                year = ln
                age = lines[i + 1] if i + 1 < end and "岁" in lines[i + 1] else ""
                stem_ss, branch_ss, j = "", "", i + 2
                if j < end and self._is_stem_ss(lines[j]):
                    stem_ss = lines[j]
                    j += 1
                    if j < end and self._is_branch_ss(lines[j]):
                        branch_ss = lines[j]
                        j += 1
                ganzhi, shishen = self._combine_ss(stem_ss, branch_ss)
                nayin = _NAYIN_MAP.get(ganzhi, "") if ganzhi else ""
                rows.append([
                    year, age,
                    ganzhi or "—", shishen or "—", nayin or "—",
                ])
                i = j
                continue
            i += 1
        return rows

    # ----------------------------------------------------------------
    #  流年
    # ----------------------------------------------------------------

    def _parse_liunian(self, lines: List[str]) -> List[List[str]]:
        """解析流年. 每行 = [年份, 流年干支, 十神, 纳音, 小运干支].

        innerText 结构:
            流
            年
            小运          ← 子标题 (跳过)
            2017          ← 年份
            丁官          ← 天干+十神
            酉劫          ← 地支+十神
            丙午          ← 小运干支
            2018 ...
        """
        start = self._find_marker(lines, "流", "年")
        if start < 0:
            return []
        # 跳过紧跟的「小运」子标题
        if start < len(lines) and lines[start] == "小运":
            start += 1
        end = self._find_marker(lines, "流", "月", start)  # 流年终于流月
        if end < 0:
            end = len(lines)

        rows: List[List[str]] = []
        i = start
        while i < end:
            if re.match(r"^\d{4}$", lines[i]):
                year = lines[i]
                stem_ss = lines[i + 1] if i + 1 < end and self._is_stem_ss(lines[i + 1]) else ""
                branch_ss = lines[i + 2] if i + 2 < end and self._is_branch_ss(lines[i + 2]) else ""
                xiaoyun = lines[i + 3] if i + 3 < end and self._is_ganzhi(lines[i + 3]) else ""
                ganzhi, shishen = self._combine_ss(stem_ss, branch_ss)
                nayin = _NAYIN_MAP.get(ganzhi, "") if ganzhi else ""
                rows.append([
                    year,
                    ganzhi or "—", shishen or "—", nayin or "—",
                    xiaoyun or "—",
                ])
                i += 4
                continue
            i += 1
        return rows

    # ----------------------------------------------------------------
    #  流月
    # ----------------------------------------------------------------

    def _parse_liuyue(self, lines: List[str]) -> List[List[str]]:
        """解析流月. 每行 = [节气, 日期, 流月干支, 十神, 纳音].

        innerText 结构:
            流
            月
            立春          ← 节气
            2/4           ← 日期
            庚比          ← 天干+十神
            寅才          ← 地支+十神
            惊蛰 ...
        """
        start = self._find_marker(lines, "流", "月")
        if start < 0:
            return []

        boundaries = (
            "天干留意", "地支留意", "智能", "干支设置", "干支关系",
            "土旺", "金相", "火休", "木囚", "水死", "五行",
        )

        rows: List[List[str]] = []
        i = start
        while i < len(lines):
            ln = lines[i]
            if any(ln == b or ln.startswith(b) for b in boundaries):
                break
            if ln in self._SOLAR_TERMS:
                jieqi = ln
                date = (lines[i + 1]
                        if i + 1 < len(lines) and re.match(r"^\d{1,2}/\d{1,2}$", lines[i + 1])
                        else "")
                stem_ss = (lines[i + 2]
                           if i + 2 < len(lines) and self._is_stem_ss(lines[i + 2]) else "")
                branch_ss = (lines[i + 3]
                             if i + 3 < len(lines) and self._is_branch_ss(lines[i + 3]) else "")
                ganzhi, shishen = self._combine_ss(stem_ss, branch_ss)
                nayin = _NAYIN_MAP.get(ganzhi, "") if ganzhi else ""
                rows.append([
                    jieqi, date,
                    ganzhi or "—", shishen or "—", nayin or "—",
                ])
                i += 4
                continue
            i += 1
        return rows

    # ----------------------------------------------------------------
    #  干支关系
    # ----------------------------------------------------------------

    def _parse_relations(self, lines: List[str]) -> str:
        """取最后一次「天干留意 / 地支留意」(专业细盘区)."""
        tg = dz = None
        for ln in lines:
            if ln.startswith("天干留意"):
                tg = ln
            elif ln.startswith("地支留意"):
                dz = ln
        out: List[str] = []
        if tg:
            content = re.split(r"[:：]", tg, 1)[-1].strip() if re.search(r"[:：]", tg) else tg
            out.append(f"**天干留意**：{content}")
        if dz:
            content = re.split(r"[:：]", dz, 1)[-1].strip() if re.search(r"[:：]", dz) else dz
            out.append(f"**地支留意**：{content}")
        return "  \n".join(out)

    # ----------------------------------------------------------------
    #  专业细盘附加块渲染 (五行 / 调候 / 宫位 / 六亲 / 干支关系逐对)
    # ----------------------------------------------------------------

    def _fmt_wuxing(self, items: Optional[List[str]]) -> str:
        """五行旺衰: 月令对应的 旺/相/休/囚/死."""
        if not items:
            return ""
        return "## 五行旺衰\n- " + "、".join(items) + "\n"

    def _fmt_tiaohou(self, th: Optional[Dict]) -> str:
        """调候用神: 用神提示 + 本八字透出/暗藏."""
        if not th:
            return ""
        lines: List[str] = []
        title = (th.get("title") or "").strip()
        tou = th.get("tou") or []
        cang = th.get("cang") or []
        full = (th.get("full") or "").strip()
        if title:
            lines.append(f"- **{title}**")
        if tou:
            lines.append(f"- 本八字透出：{'、'.join(tou)}")
        if cang:
            lines.append(f"- 本八字暗藏：{'、'.join(cang)}")
        if not lines and full:
            lines.append(f"- {full}")
        if not lines:
            return ""
        return "## 调候用神\n" + "\n".join(lines) + "\n"

    def _fmt_gongwei(self, gw: Optional[Dict]) -> str:
        """宫位映射: 六宫 + 四柱干支对照."""
        if not gw:
            return ""
        palaces: List[str] = []
        pillar_titles: List[str] = []
        gz_rows: List[List[str]] = []
        for sec in (gw.get("sections") or []):
            for row in sec.get("rows", []):
                if row.get("gong"):
                    palaces.extend(row["gong"])
                if row.get("title"):
                    pillar_titles = row["title"]
                if row.get("gz"):
                    gz_rows.append(row["gz"])
        if not palaces and not pillar_titles:
            full = (gw.get("full") or "").strip()
            return f"## 宫位映射\n{full}\n" if full else ""
        lines = ["## 宫位映射"]
        if palaces:
            lines.append("- **六宫**：" + "、".join(self._dedupe(palaces)))
        if pillar_titles and gz_rows:
            rows: List[List[str]] = []
            for gzr in gz_rows:
                if len(gzr) != len(pillar_titles):
                    continue
                if all(c in self._TIAN_GAN for c in gzr):
                    label = "天干"
                elif all(c in self._DI_ZHI for c in gzr):
                    label = "地支"
                else:
                    label = "干支"
                rows.append([label] + list(gzr))
            if rows:
                lines.append("")
                lines.append(
                    self._fmt_table(["四柱"] + list(pillar_titles), rows).rstrip("\n")
                )
        return "\n".join(lines) + "\n"

    def _fmt_liuqin(self, lq: Optional[Dict]) -> str:
        """六亲 / 社会关系: 按亲属关系/社会关系分段, 列关系词 + 十神."""
        if not lq:
            return ""
        secs = lq.get("sections") or []
        if not secs:
            full = (lq.get("full") or "").strip()
            return f"## 六亲 / 社会关系\n{full}\n" if full else ""
        ss_labels = ["天干十神", "藏干十神"]
        lines = ["## 六亲 / 社会关系"]
        has_content = False
        for sec in secs:
            title = (sec.get("title") or "").strip()
            gong_rows: List[List[str]] = []
            ss_rows: List[List[str]] = []
            for row in sec.get("rows", []):
                if row.get("gong"):
                    gong_rows.append(row["gong"])
                if row.get("ss"):
                    ss_rows.append(row["ss"])
            if not gong_rows and not ss_rows:
                continue
            has_content = True
            if title:
                lines.append("")
                lines.append(f"**{title}**")
            for i, gr in enumerate(gong_rows):
                lines.append(
                    f"- {'详细' if i > 0 else '概括'}：{'、'.join(self._dedupe(gr))}"
                )
            for i, ssr in enumerate(ss_rows):
                lbl = ss_labels[i] if i < len(ss_labels) else "十神"
                lines.append(f"- {lbl}：{' '.join(ssr)}")
        if not has_content:
            full = (lq.get("full") or "").strip()
            return f"## 六亲 / 社会关系\n{full}\n" if full else ""
        return "\n".join(lines) + "\n"

    def _fmt_gz_rel_body(self, items: Optional[List[Dict]]) -> str:
        """干支关系逐对 (仅正文, 合并进「干支关系」节). 去重后按天干/地支分组."""
        if not items:
            return ""
        seen = set()
        tg_lines: List[str] = []
        dz_lines: List[str] = []
        for it in items:
            rel = (it.get("rel") or "").strip()
            gz = it.get("gz") or []
            key = (rel, tuple(gz))
            if key in seen:
                continue
            seen.add(key)
            line = f"{rel} {'-'.join(gz)}".strip()
            if not line:
                continue
            if gz and all(c in self._TIAN_GAN for c in gz):
                tg_lines.append(line)
            elif gz and all(c in self._DI_ZHI for c in gz):
                dz_lines.append(line)
            else:
                tg_lines.append(line)
        out: List[str] = []
        if tg_lines:
            out.append(f"- **天干（逐对）**：{'、'.join(tg_lines)}")
        if dz_lines:
            out.append(f"- **地支（逐对）**：{'、'.join(dz_lines)}")
        return "\n".join(out)

    @staticmethod
    def _dedupe(items: List[str]) -> List[str]:
        seen = set()
        out = []
        for x in items:
            if x and x not in seen:
                seen.add(x)
                out.append(x)
        return out

    # ================================================================
    #  helpers
    # ================================================================

    @staticmethod
    def _find(lines: List[str], needle: str, start: int = 0) -> int:
        for i in range(start, len(lines)):
            if lines[i] == needle:
                return i
        return -1

    @staticmethod
    def _find_marker(lines: List[str], a: str, b: str, start: int = 0) -> int:
        """找到连续两行 a, b 的位置, 返回 b 之后的索引; 找不到返回 -1."""
        for i in range(start, len(lines) - 1):
            if lines[i] == a and lines[i + 1] == b:
                return i + 2
        return -1

    def _is_stem_ss(self, s: str) -> bool:
        return len(s) == 2 and s[0] in self._TIAN_GAN and s[1] in self._SHI_SHEN

    def _is_branch_ss(self, s: str) -> bool:
        return len(s) == 2 and s[0] in self._DI_ZHI and s[1] in self._SHI_SHEN

    def _is_ganzhi(self, s: str) -> bool:
        return len(s) == 2 and s[0] in self._TIAN_GAN and s[1] in self._DI_ZHI

    @staticmethod
    def _combine_ss(stem_ss: str, branch_ss: str) -> Tuple[str, str]:
        """把 '辛劫'+'酉劫' 合并为 (干支 '辛酉', 十神 '劫')."""
        if not stem_ss or not branch_ss:
            return "", ""
        ganzhi = stem_ss[0] + branch_ss[0]
        tg_ss = stem_ss[1:] if len(stem_ss) > 1 else ""
        dz_ss = branch_ss[1:] if len(branch_ss) > 1 else ""
        if tg_ss and dz_ss and tg_ss != dz_ss:
            shishen = f"{tg_ss}/{dz_ss}"
        else:
            shishen = tg_ss or dz_ss
        return ganzhi, shishen

    @staticmethod
    def _fmt_table(headers: List[str], rows: List[List[str]]) -> str:
        if not rows:
            return "_（无数据）_\n"
        n = len(headers)
        out = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(["---"] * n) + " |",
        ]
        for r in rows:
            padded = list(r) + [""] * (n - len(r))
            esc = [str(c).replace("|", "\\|").replace("\n", " ")
                   for c in padded[:n]]
            out.append("| " + " | ".join(esc) + " |")
        return "\n".join(out) + "\n"
