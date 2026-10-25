#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""設計審查掃描器：靜態原始碼掃描＋渲染後畫面掃描，產出 scan.json 與截圖。

用法：
  python scan.py --file page.html --out design-review/round-1
  python scan.py --url http://localhost:3000 [--src ./src] --out design-review/round-1
  python scan.py --src ./src --out design-review/round-1        （沒有可開的頁面時，只做靜態掃描）
選項：
  --widths 1440,390   截圖與量測的視窗寬度（小於 600 視為手機）
  --no-dom            不開瀏覽器，只做靜態掃描
  --no-install        缺 playwright 時不自動安裝（公司主機請加）
  --max-per-rule 8    每條規則最多列幾筆，其餘彙整成一筆「另有 N 處」

退出碼：0 沒有命中　1 有命中（交給審查者逐條確認或排除）　2 執行錯誤
掃描結果只是候選，不是判決；最後由審查者確認。
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rules import RULES, RULESET_VERSION, SEVERITIES  # noqa: E402

SCANNER_VERSION = "1.0"

SRC_EXT = {".html", ".htm", ".css", ".scss", ".sass", ".less", ".jsx", ".tsx", ".js", ".ts",
           ".vue", ".svelte", ".astro"}
MARKUP_EXT = {".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte", ".astro", ".js", ".ts"}
SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", ".nuxt", "out", "coverage",
             "design-review", "__pycache__", ".venv", "venv", ".svelte-kit", "vendor"}

# 靜態規則：(規則, 樣式, 證據說明, 畫面掃描能否涵蓋)
# 有畫面掃描時，畫面能涵蓋的規則改由畫面掃描判斷（看的是實際渲染結果，比原始碼準）。
STATIC_RULES = [
    ("C1", r"bg-clip-text|(?:-webkit-)?background-clip\s*:\s*text", "使用漸層文字（background-clip: text）", True),
    ("C2", r"\b(?:from|via|to)-(?:purple|violet|indigo|fuchsia)-\d{2,3}\b", "使用紫藍色階漸層", True),
    ("C3", r"shadow-(?:purple|violet|indigo|fuchsia|blue|cyan|pink)-\d{3}(?:/\d+)?|drop-shadow-\[0_0_", "使用彩色發光陰影", True),
    ("C4", r"\bblur-(?:2xl|3xl)\b|filter\s*:\s*blur\(\s*\d{2,}px", "使用大範圍模糊色塊", True),
    ("C6", r"\bbackdrop-blur(?:-\w+)?\b|backdrop-filter\s*:\s*blur", "使用玻璃擬態", True),
    ("A2", r"\banimate-(?:ping|pulse)\b", "使用呼吸／脈衝動畫，確認背後是否有真實狀態", True),
    ("A3", r"""href\s*=\s*["'](?:#|javascript:void\(0\);?)["']""", "連結指向 # 或 javascript:void(0)，點了不會去任何地方", True),
    ("A3", r"on[Cc]lick\s*=\s*\{\s*\(\s*\)\s*=>\s*\{\s*\}\s*\}", "點擊處理是空函式", False),
    ("C10", r"shadow-\[-?\d+px_-?\d+px_0(?:px)?_|box-shadow\s*:\s*-?\d+px\s+-?\d+px\s+0(?:px)?\s+(?:#000\b|#000000|black|rgb\(0,\s*0,\s*0\))",
     "使用硬邊黑色位移陰影", True),
    ("C8", r"animation\s*:[^;]*\binfinite\b|\banimate-(?:bounce|spin)\b", "使用無限循環動畫", True),
]

# 文字規則：只看使用者讀得到的文字
CLAIM_PATTERNS = [
    r"\d+(?:\.\d+)?\s*%",
    r"\d{1,3}(?:,\d{3})+\s*\+",
    r"\d+(?:\.\d+)?\s*(?:[kKmM]|萬|千|百萬)\s*\+",
    r"\b(?:trusted|loved|used)\s+by\b",
    r"\brated\s+\d",
    r"★{3,}|⭐{3,}",
    r"\d+(?:\.\d+)?\s*(?:x|倍)\s*(?:faster|更快|提升)",
    r"(?:超過|逾|已有|已獲)\s*\d[\d,\.]*\s*(?:萬|千|百)?\s*(?:位|家|名|個)?\s*(?:用戶|使用者|客戶|企業|團隊|開發者|工程師)",
]
CLICHE_WORDS = [
    r"seamless(?:ly)?", r"supercharge", r"unlock\s+(?:the\s+)?(?:power|potential)", r"elevate\s+your",
    r"revolutioni[sz]e", r"next[- ]gen(?:eration)?", r"cutting[- ]edge", r"game[- ]chang\w*",
    r"effortless(?:ly)?", r"empower\w*", r"all[- ]in[- ]one", r"world[- ]class", r"best[- ]in[- ]class",
    r"harness\s+the\s+power", r"to\s+the\s+next\s+level", r"(?:lightning|blazing)[- ]fast", r"streamline\w*",
    r"無縫", r"賦能", r"一站式", r"全方位", r"顛覆", r"革命性", r"極致體驗", r"打造極致", r"輕鬆搞定",
    r"釋放潛能", r"解鎖", r"下一代", r"領先業界", r"全新升級",
]
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF✨⚡⭐✅❌❤]")

SCROLL_JS = """async () => {
  const step = Math.max(200, window.innerHeight * 0.8);
  for (let i = 0, y = 0; i < 40 && y < document.documentElement.scrollHeight; i++, y += step) {
    window.scrollTo(0, y); await new Promise(r => setTimeout(r, 120));
  }
  window.scrollTo(0, 0); await new Promise(r => setTimeout(r, 400));
}"""

DOM_JS = r"""(TARGET_W) => {
  const VW = window.innerWidth, VH = window.innerHeight, MOBILE = TARGET_W < 600;
  const hits = [];
  const add = (rule, where, evidence, severity) => hits.push({ rule, where, evidence, severity: severity || null });

  // ---------- 顏色工具：一律經 canvas 轉成 sRGB，oklch 等新色彩空間也吃得下 ----------
  const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const cx = cv.getContext('2d', { willReadFrequently: true });
  const cc = new Map();
  const rgba = s => {
    if (!s || s === 'transparent' || s === 'none') return { r: 0, g: 0, b: 0, a: 0 };
    if (cc.has(s)) return cc.get(s);
    cx.clearRect(0, 0, 1, 1); cx.fillStyle = 'rgba(0,0,0,0)'; cx.fillStyle = s; cx.fillRect(0, 0, 1, 1);
    const d = cx.getImageData(0, 0, 1, 1).data;
    const v = { r: d[0], g: d[1], b: d[2], a: d[3] / 255 }; cc.set(s, v); return v;
  };
  const hsl = c => {
    const r = c.r / 255, g = c.g / 255, b = c.b / 255, mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2;
    let h = 0, s = 0;
    if (mx !== mn) { const d = mx - mn; s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn);
      h = mx === r ? ((g - b) / d + (g < b ? 6 : 0)) : mx === g ? (b - r) / d + 2 : (r - g) / d + 4; h *= 60; }
    return { h, s, l };
  };
  const hex = c => '#' + [c.r, c.g, c.b].map(v => Math.round(v).toString(16).padStart(2, '0')).join('');
  const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const contrast = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const blend = (fg, bg) => ({ r: fg.r * fg.a + bg.r * (1 - fg.a), g: fg.g * fg.a + bg.g * (1 - fg.a), b: fg.b * fg.a + bg.b * (1 - fg.a), a: 1 });
  const COLOR_RE = /(?:rgba?|hsla?|oklch|oklab|lab|lch|color)\([^()]*\)|#[0-9a-fA-F]{3,8}\b/g;
  const colorsIn = s => (String(s).match(COLOR_RE) || []).map(rgba);
  const WHITE = { r: 255, g: 255, b: 255, a: 1 };

  // ---------- 元素工具 ----------
  const SKIP = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'META', 'LINK', 'BR', 'HEAD', 'TITLE']);
  const all = Array.from(document.body.querySelectorAll('*')).filter(el =>
    !SKIP.has(el.tagName) && (!el.closest('svg') || el.tagName.toLowerCase() === 'svg'));
  const csm = new Map(); const cs = el => { let v = csm.get(el); if (!v) { v = getComputedStyle(el); csm.set(el, v); } return v; };
  const rm = new Map(); const rect = el => { let v = rm.get(el); if (!v) { v = el.getBoundingClientRect(); rm.set(el, v); } return v; };
  const shown = el => { const r = rect(el), s = cs(el); return r.width >= 1 && r.height >= 1 && s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity) > 0.02; };
  const vis = all.filter(shown);
  const where = el => {
    const parts = []; let e = el, d = 0;
    while (e && e.nodeType === 1 && e !== document.body && d < 4) {
      let p = e.tagName.toLowerCase();
      if (e.id) { parts.unshift(p + '#' + e.id); break; }
      const cls = Array.from(e.classList).filter(c => /^[a-zA-Z_-][\w-]*$/.test(c)).slice(0, 2);
      if (cls.length) p += '.' + cls.join('.');
      parts.unshift(p); e = e.parentElement; d++;
    }
    return parts.join(' > ') || el.tagName.toLowerCase();
  };
  const txt = el => (el.innerText || el.textContent || '').trim().replace(/\s+/g, ' ');
  const ownText = el => Array.from(el.childNodes).filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim().replace(/\s+/g, ' ');
  const short = (s, n) => (s.length > n ? s.slice(0, n) + '…' : s);
  const q = s => '「' + short(s, 28) + '」';
  const y = el => 'y≈' + Math.round(rect(el).top + window.scrollY) + 'px';
  const INTERACTIVE = 'a[href], button, input, select, textarea, label, summary, [role=button], [role=link], [role=tab], [role=menuitem], [role=switch], [role=checkbox], [onclick], [tabindex]:not([tabindex="-1"])';
  const interactive = el => !!el.closest(INTERACTIVE);
  const effOp = el => { let o = 1, e = el; while (e && e.nodeType === 1) { o *= parseFloat(cs(e).opacity); e = e.parentElement; } return o; };
  const bgOf = el => {
    let e = el; const layers = [];
    while (e && e.nodeType === 1) {
      const s = cs(e);
      if (s.backgroundImage && s.backgroundImage !== 'none') return { color: null, image: true };
      const c = rgba(s.backgroundColor);
      if (c.a > 0) { layers.push(c); if (c.a >= 0.99) break; }
      e = e.parentElement;
    }
    let base = WHITE;
    for (let i = layers.length - 1; i >= 0; i--) base = blend(layers[i], base);
    return { color: base, image: false };
  };
  const radius = (s, h) => { const v = s.borderTopLeftRadius; return v.endsWith('%') ? (parseFloat(v) >= 30 ? 9999 : 0) : (parseFloat(v) || 0); };
  const h1 = vis.find(e => e.tagName === 'H1');
  const h1Top = h1 ? rect(h1).top : null;

  // ---------- E1／E2／B3／B4：文字可讀性與階層 ----------
  const fsChars = {}; const fsSet = new Set(); let foldChars = 0, foldTiny = 0, maxFoldFs = 0;
  const low = [], tiny = [];
  for (const el of vis) {
    const t = ownText(el); if (t.length < 2) continue;
    const s = cs(el), r = rect(el), fs = parseFloat(s.fontSize), fw = parseInt(s.fontWeight, 10) || 400;
    fsChars[fs] = (fsChars[fs] || 0) + t.length; fsSet.add(Math.round(fs));
    const inFold = r.top < VH && r.bottom > 0;
    if (inFold) { foldChars += t.length; if (fs < 13) foldTiny++; if (fs > maxFoldFs) maxFoldFs = fs; }
    if (fs < 12) tiny.push([el, fs, t]);
    const bg = bgOf(el); if (bg.image) continue;
    const fc = rgba(s.color); fc.a *= effOp(el);
    const ratio = contrast(blend(fc, bg.color), bg.color);
    const large = fs >= 24 || (fs >= 18.66 && fw >= 700);
    if (ratio < (large ? 3 : 4.5)) low.push([el, ratio, fs, t, large, bg.color]);
  }
  low.sort((a, b) => a[1] - b[1]);
  for (const [el, ratio, fs, t, large, bg] of low)
    add('E1', where(el), `對比 ${ratio.toFixed(2)}：1（${large ? '大字需 3：1' : '內文需 4.5：1'}），字級 ${fs}px，底色 ${hex(bg)}，文字${q(t)}，${y(el)}`);
  for (const [el, fs, t] of tiny) add('E2', where(el), `字級 ${fs}px，小於 12px，文字${q(t)}，${y(el)}`);
  const bodyFs = +((Object.entries(fsChars).sort((a, b) => b[1] - a[1])[0] || [16])[0]);
  const ratioH = bodyFs ? maxFoldFs / bodyFs : 0;
  if (ratioH && ratioH < 1.8) add('B3', 'page', `首屏最大字 ${maxFoldFs}px，內文主要字級 ${bodyFs}px，比例 ${ratioH.toFixed(2)}，標題壓不住內文`);
  if (fsSet.size > 9) add('B3', 'page', `全頁用了 ${fsSet.size} 種字級，階層太碎，讀者分不出誰比較重要`);
  if (foldTiny >= 10) add('B4', 'first-viewport', `首屏有 ${foldTiny} 段小於 13px 的文字，資訊塞太滿、讀起來吃力`);
  if (foldChars > (MOBILE ? 500 : 900)) add('B4', 'first-viewport', `首屏約 ${foldChars} 字，第一眼要讀的東西太多`, 'P2');

  // ---------- A1：看起來能點卻不能點（膠囊、帶框小標） ----------
  const pills = [];
  for (const el of vis) {
    if (interactive(el)) continue;
    const r = rect(el), s = cs(el);
    if (r.height < 16 || r.height > 44 || r.width < 24 || r.width > 420 || el.children.length > 4) continue;
    const t = txt(el); if (t.length < 2 || t.length > 48) continue;
    if (radius(s, r.height) < r.height / 2 - 1) continue;
    const bw = parseFloat(s.borderTopWidth) || 0, bc = rgba(s.borderTopColor);
    const border = bw >= 1 && bc.a > 0.15;
    const fill = rgba(s.backgroundColor);
    let filled = false;
    if (fill.a > 0.08 && el.parentElement) { const pb = bgOf(el.parentElement); filled = pb.image ? true : contrast(blend(fill, pb.color), pb.color) > 1.08; }
    if (border || filled) pills.push(el);
  }
  for (const el of pills.filter(p => !pills.some(o => o !== p && o.contains(p)))) {
    const r = rect(el);
    const aboveH1 = h1Top !== null && r.bottom <= h1Top + 2 && h1Top - r.bottom < 220;
    add('A1', where(el), `膠囊外觀（圓角、${border_or_fill(el)}）但不是可互動元素，文字${q(txt(el))}${aboveH1 ? '，位在主標題正上方' : ''}，${y(el)}`);
  }
  function border_or_fill(el) { const s = cs(el); return (parseFloat(s.borderTopWidth) || 0) >= 1 ? '有邊框' : '有底色'; }

  // ---------- A2：假狀態燈號 ----------
  const animOn = e => cs(e).animationName !== 'none' || getComputedStyle(e, '::before').animationName !== 'none' || getComputedStyle(e, '::after').animationName !== 'none';
  for (const el of vis) {
    const r = rect(el); if (r.width < 4 || r.width > 18 || r.height < 4 || r.height > 18 || Math.abs(r.width - r.height) > 3) continue;
    const s = cs(el), bg = rgba(s.backgroundColor);
    if (bg.a < 0.3 || radius(s, r.height) < r.width / 2 - 1) continue;
    const sib = el.parentElement ? Array.from(el.parentElement.children).filter(k => k !== el && rect(k).width <= 24) : [];
    if (!(animOn(el) || Array.from(el.children).some(animOn) || sib.some(animOn))) continue;
    const par = el.parentElement; let ctx = par ? txt(par) : ''; if (ctx.length < 2 && par && par.parentElement) ctx = txt(par.parentElement);
    add('A2', where(el), `會閃爍的 ${hex(bg)} 小圓點，旁邊文字${q(ctx)}；確認它背後有真實狀態，否則是假燈號，${y(el)}`);
  }

  // ---------- A3：死連結 ----------
  for (const a of vis.filter(e => e.tagName === 'A')) {
    const h = a.getAttribute('href');
    if (h === '#' || h === '' || /^javascript:/i.test(h || ''))
      add('A3', where(a), `連結 href 為「${h}」，文字${q(txt(a))}，點了不會去任何地方，${y(a)}`);
  }

  // ---------- A4：能點的看起來不能點 ----------
  for (const a of vis.filter(e => e.tagName === 'A' && e.getAttribute('href') && e.getAttribute('href') !== '#')) {
    const p = a.parentElement; if (!p || !/^(P|LI|SPAN|TD|DD)$/.test(p.tagName) || ownText(p).length < 10) continue;
    const s = cs(a), ps = cs(p);
    const underline = s.textDecorationLine.includes('underline') || (parseFloat(s.borderBottomWidth) || 0) > 0;
    const diff = contrast(rgba(s.color), rgba(ps.color));
    const bolder = (parseInt(s.fontWeight, 10) || 400) - (parseInt(ps.fontWeight, 10) || 400) >= 200;
    if (!underline && diff < 1.25 && !bolder) add('A4', where(a), `段落裡的連結${q(txt(a))}沒有底線、顏色和內文幾乎一樣，看不出能點，${y(a)}`);
  }

  // ---------- A5：游標說謊或用 div 冒充按鈕 ----------
  for (const el of vis) {
    if (cs(el).cursor !== 'pointer' || interactive(el)) continue;
    const p = el.parentElement; if (p && cs(p).cursor === 'pointer') continue;
    add('A5', where(el), `游標變成手指但不是語意上的可互動元素（可能是假互動，或用 div 冒充按鈕，鍵盤無法操作），文字${q(txt(el))}，${y(el)}`);
  }

  // ---------- B1：等大功能卡 ----------
  const groups = [];
  for (const p of vis) {
    const kids = Array.from(p.children).filter(shown);
    if (kids.length < 3 || kids.length > 6) continue;
    const rs = kids.map(rect), w0 = rs[0].width, h0 = rs[0].height;
    if (w0 < 140 || h0 < 100) continue;
    if (!rs.every(r => Math.abs(r.width - w0) <= Math.max(6, w0 * 0.04) && Math.abs(r.height - h0) <= Math.max(10, h0 * 0.08))) continue;
    const sig = k => k.tagName + '|' + k.children.length;
    if (!kids.every(k => sig(k) === sig(kids[0]))) continue;
    if (!kids.every(k => k.querySelector('h2,h3,h4,h5,h6,strong,b,[class*=title]'))) continue;
    const iconish = k => k.querySelector('svg,img,i,[class*=icon]') || /^[\u{1F300}-\u{1FAFF}✨⚡⭐✅]/u.test(txt(k));
    if (!kids.every(iconish)) continue;
    groups.push([p, kids]);
  }
  for (const [p, kids] of groups.filter(g => !groups.some(o => o !== g && o[0].contains(g[0])))) {
    const heads = kids.map(k => txt(k.querySelector('h2,h3,h4,h5,h6,strong,b,[class*=title]') || k)).map(s => short(s, 14));
    add('B1', where(p), `${kids.length} 張一樣大、一樣結構的「圖示＋標題＋說明」卡片（${heads.join('、')}），看不出哪一項最重要，${y(p)}`);
  }

  // ---------- B2：首屏多個同強度主按鈕 ----------
  const ctas = vis.filter(e => e.matches('a[href], button, [role=button]')).filter(e => {
    const r = rect(e); if (r.top >= VH || r.bottom <= 0 || r.width * r.height < 1200) return false;
    if ((cs(e).backgroundImage || '').includes('gradient')) return true;
    const bg = rgba(cs(e).backgroundColor); if (bg.a < 0.6) return false;
    const pb = e.parentElement ? bgOf(e.parentElement) : { color: WHITE, image: false };
    const base = pb.image ? WHITE : pb.color;
    return hsl(bg).s > 0.4 || contrast(blend(bg, base), base) > 3;
  });
  const ctaTop = ctas.filter(e => !ctas.some(o => o !== e && o.contains(e)));
  if (ctaTop.length >= 3) add('B2', 'first-viewport', `首屏有 ${ctaTop.length} 顆實心主按鈕（${ctaTop.map(e => q(txt(e))).join('、')}），讀者不知道該先按哪一顆`);

  // ---------- C1／C2：漸層文字、紫藍霓虹漸層與彩色光暈 ----------
  for (const el of vis) {
    const s = cs(el), bi = s.backgroundImage || ''; if (!bi.includes('gradient')) continue;
    const r = rect(el);
    const clip = (s.backgroundClip === 'text' || s.webkitBackgroundClip === 'text');
    if (clip) { add('C1', where(el), `漸層文字${q(txt(el))}，${y(el)}`); continue; }
    if (r.width * r.height < VW * VH * 0.02) continue;
    const cols = colorsIn(bi).filter(c => c.a > 0.08).map(c => [c, hsl(c)]).filter(([c, x]) => x.s > 0.4 && x.l > 0.15 && x.l < 0.85);
    const purple = cols.some(([c, x]) => x.h >= 250 && x.h <= 320);
    let spread = 0; for (const [, a] of cols) for (const [, b] of cols) { const d = Math.min(Math.abs(a.h - b.h), 360 - Math.abs(a.h - b.h)); if (d > spread) spread = d; }
    if (purple || spread >= 40) add('C2', where(el), `大面積彩色漸層（${cols.slice(0, 4).map(([c]) => hex(c)).join('→')}）${purple ? '，含紫色系' : ''}，${y(el)}`);
  }

  // ---------- C3／C10：陰影 ----------
  const splitTop = s => { const out = []; let d = 0, cur = ''; for (const ch of s) { if (ch === '(') d++; if (ch === ')') d--; if (ch === ',' && d === 0) { out.push(cur); cur = ''; } else cur += ch; } if (cur.trim()) out.push(cur); return out; };
  const parseSh = layer => { const cols = layer.match(COLOR_RE) || []; const rest = layer.replace(COLOR_RE, ' '); const n = (rest.match(/-?\d*\.?\d+px/g) || []).map(parseFloat);
    return { color: cols.length ? rgba(cols[0]) : { r: 0, g: 0, b: 0, a: 1 }, x: n[0] || 0, y: n[1] || 0, blur: n[2] || 0, inset: /inset/.test(layer) }; };
  let hard = [], rotated = 0, thick = 0;
  for (const el of vis) {
    const s = cs(el);
    if (s.boxShadow && s.boxShadow !== 'none') {
      for (const L of splitTop(s.boxShadow).map(parseSh)) {
        if (L.inset) continue;
        const x = hsl(L.color);
        if (L.blur >= 16 && x.s > 0.45 && L.color.a >= 0.2) { add('C3', where(el), `彩色發光陰影 ${hex(L.color)}，模糊 ${L.blur}px，${y(el)}`); break; }
        if (L.blur === 0 && Math.abs(L.x) + Math.abs(L.y) >= 3 && lum(L.color) < 0.05 && L.color.a >= 0.7) { hard.push(el); break; }
      }
    }
    if (s.textShadow && s.textShadow !== 'none') {
      for (const L of splitTop(s.textShadow).map(parseSh)) { if (L.blur >= 6 && hsl(L.color).s > 0.45 && L.color.a >= 0.3) { add('C3', where(el), `發光文字 ${hex(L.color)}，模糊 ${L.blur}px，${y(el)}`); break; } }
    }
    if ((s.filter || '').includes('drop-shadow')) { const c = colorsIn(s.filter)[0]; if (c && hsl(c).s > 0.45 && c.a >= 0.3) add('C3', where(el), `彩色 drop-shadow ${hex(c)}，${y(el)}`); }
    const tf = s.transform; if (tf && tf.startsWith('matrix(') && ownText(el).length + txt(el).length > 0) { const m = tf.slice(7, -1).split(',').map(parseFloat); const deg = Math.abs(Math.atan2(m[1], m[0]) * 180 / Math.PI); if (deg >= 1 && deg <= 20) rotated++; }
    if ((parseFloat(s.borderTopWidth) || 0) >= 2 && lum(rgba(s.borderTopColor)) < 0.05 && rect(el).height >= 40) thick++;
  }
  if (hard.length >= 3 || (rotated >= 2 && thick >= 3))
    add('C10', 'page', `硬邊黑色位移陰影 ${hard.length} 處、歪斜貼紙 ${rotated} 處、粗黑框 ${thick} 處（例：${hard.slice(0, 2).map(where).join('；')}）`);

  // ---------- C4：模糊光斑 ----------
  for (const el of vis) {
    const s = cs(el); if (!['absolute', 'fixed'].includes(s.position)) continue;
    const m = (s.filter || '').match(/blur\(([\d.]+)px\)/); if (!m || parseFloat(m[1]) < 20) continue;
    const r = rect(el); if (r.width * r.height < VW * VH * 0.03) continue;
    add('C4', where(el), `絕對定位的模糊色塊（blur ${m[1]}px，約 ${Math.round(r.width)}×${Math.round(r.height)}px），純裝飾，${y(el)}`);
  }

  // ---------- C5：卡片 ----------
  const isCard = el => {
    if (el.matches(INTERACTIVE)) return false;
    const r = rect(el); if (r.height < 60 || r.width < 120 || el.children.length < 1) return false;
    if (r.width >= VW * 0.9 && r.height >= VH) return false;
    const s = cs(el); if (radius(s, r.height) < 6) return false;
    const border = (parseFloat(s.borderTopWidth) || 0) >= 1 && rgba(s.borderTopColor).a > 0.1;
    const shadow = s.boxShadow && s.boxShadow !== 'none';
    let fill = false; const bgc = rgba(s.backgroundColor);
    if (bgc.a > 0.05 && el.parentElement) { const pb = bgOf(el.parentElement); fill = pb.image ? true : contrast(blend(bgc, pb.color), pb.color) > 1.06; }
    return border || shadow || fill;
  };
  const cards = vis.filter(isCard); const cardSet = new Set(cards);
  const outerCard = c => { let p = c.parentElement; while (p) { if (cardSet.has(p)) return p; p = p.parentElement; } return null; };
  const nested = cards.map(c => [c, outerCard(c)]).filter(([, o]) => o);
  const reported = new Set();
  for (const [c, o] of nested) { if (reported.has(o)) continue; reported.add(o); add('C5', where(o), `卡片裡又套卡片（內層：${where(c)}），${y(o)}`); }
  if (cards.length > 15) add('C5', 'page', `全頁共有 ${cards.length} 個卡片框，用框代替了留白與對齊`, 'P2');

  // ---------- C6／C7／C8 ----------
  const glass = vis.filter(e => { const b = cs(e).backdropFilter; return b && b !== 'none'; });
  if (glass.length >= 2) add('C6', 'page', `${glass.length} 個元素使用背景模糊（玻璃擬態）`);
  const eyebrows = vis.filter(e => { const s = cs(e), fs = parseFloat(s.fontSize); return ownText(e).length >= 2 && s.textTransform === 'uppercase' && fs <= 14 && (parseFloat(s.letterSpacing) || 0) / fs >= 0.05; });
  if (eyebrows.length >= 3) add('C7', 'page', `${eyebrows.length} 處全大寫加寬字距的小標（例：${eyebrows.slice(0, 3).map(e => q(ownText(e))).join('、')}）`);
  const loops = vis.filter(e => { const s = cs(e); return s.animationName !== 'none' && s.animationIterationCount.includes('infinite'); });
  if (loops.length >= 2) add('C8', 'page', `${loops.length} 個元素在無限循環播放動畫（例：${loops.slice(0, 3).map(where).join('；')}）`);

  // ---------- C11：米白底斜體襯線雜誌風 ----------
  const pbg = bgOf(document.body).color;
  if (pbg) { const x = hsl(pbg); const cream = x.h >= 25 && x.h <= 60 && x.s >= 0.15 && x.l >= 0.88 && x.l < 0.985;
    const italicSerif = vis.filter(e => /^H[1-3]$/.test(e.tagName) || (e.tagName === 'EM' && e.closest('h1,h2,h3'))).some(e => { const s = cs(e); return s.fontStyle === 'italic' && /serif/i.test(s.fontFamily) && !/sans-serif/i.test(s.fontFamily); });
    if (cream && italicSerif) add('C11', 'page', `米白底（${hex(pbg)}）配斜體襯線標題，是 2025 年常見的 AI 雜誌風套路`); }

  // ---------- C12：強調色過多 ----------
  const hue = new Map();
  const addHue = c => { if (c.a < 0.3) return; const x = hsl(c); if (x.s < 0.45 || x.l < 0.2 || x.l > 0.85) return; const b = Math.round(x.h / 30) % 12; hue.set(b, (hue.get(b) || 0) + 1); };
  for (const el of vis) { const s = cs(el), r = rect(el);
    if (ownText(el).length >= 2) addHue(rgba(s.color));
    if (r.width * r.height >= 400) addHue(rgba(s.backgroundColor));
    if ((parseFloat(s.borderTopWidth) || 0) >= 1) addHue(rgba(s.borderTopColor));
    if ((s.backgroundImage || '').includes('gradient')) colorsIn(s.backgroundImage).forEach(addHue); }
  const buckets = Array.from(hue.values()).filter(n => n >= 2).length;
  if (buckets >= 5) add('C12', 'page', `畫面上有 ${buckets} 組不同色相的鮮豔色（各出現兩次以上），強調色太多等於沒有強調`);

  // ---------- E3：水平溢出 ----------
  // 手機模擬時內容太寬，瀏覽器會整頁縮小，innerWidth 跟著變大；所以要跟設定的寬度比
  const sw = Math.max(document.documentElement.scrollWidth, VW);
  if (sw > TARGET_W + 2) {
    const culprits = vis.filter(e => rect(e).right > TARGET_W + 2 && rect(e).left < TARGET_W);
    const top = culprits.filter(e => !culprits.some(o => o !== e && o.contains(e) && o !== document.documentElement)).slice(0, 3);
    add('E3', top.map(where).join('；') || 'page', `內容寬 ${sw}px 超出視窗 ${TARGET_W}px，畫面會被縮小或出現左右捲動`, MOBILE ? 'P0' : 'P1');
  }

  // ---------- E4：觸控目標太小（只看手機寬度） ----------
  if (MOBILE) for (const el of vis.filter(e => e.matches('button, input, select, [role=button], a[href]'))) {
    const s = cs(el); if (el.tagName === 'A' && s.display === 'inline') continue;
    const r = rect(el); if (r.width < 24 || r.height < 24) add('E4', where(el), `觸控目標 ${Math.round(r.width)}×${Math.round(r.height)}px，小於 24×24px，文字${q(txt(el))}，${y(el)}`);
  }

  // ---------- E5：缺少可讀名稱 ----------
  for (const img of vis.filter(e => e.tagName === 'IMG')) if (!img.hasAttribute('alt')) add('E5', where(img), `圖片缺少 alt，src=${short(img.getAttribute('src') || '', 40)}`);
  for (const b of vis.filter(e => e.matches('button, a[href], [role=button]'))) {
    const name = (b.getAttribute('aria-label') || b.getAttribute('title') || txt(b) || Array.from(b.querySelectorAll('img[alt]')).map(i => i.alt).join('')).trim();
    if (!name && !b.querySelector('svg title') && !b.getAttribute('aria-labelledby')) add('E5', where(b), `互動元素沒有可讀名稱，螢幕閱讀器念不出它是什麼，${y(b)}`);
  }

  return {
    hits,
    metrics: { viewport: TARGET_W, layout_width: VW, body_font_px: bodyFs, max_fold_font_px: maxFoldFs, heading_ratio: +ratioH.toFixed(2),
      font_sizes: fsSet.size, fold_chars: foldChars, fold_tiny_texts: foldTiny, cards: cards.length,
      nested_cards: nested.length, vivid_hue_groups: buckets, low_contrast_texts: low.length, scroll_width: sw },
  };
}"""


# ---------------------------------------------------------------- 靜態掃描

def collect_sources(file=None, src=None):
    paths = []
    if file:
        paths.append(Path(file))
    if src:
        root = Path(src)
        if root.is_file():
            paths.append(root)
        else:
            for p in sorted(root.rglob("*")):
                if p.is_file() and p.suffix.lower() in SRC_EXT and not (set(p.parts) & SKIP_DIRS):
                    paths.append(p)
    seen, out = set(), []
    for p in paths:
        k = str(p.resolve())
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out


def _lineno(text, idx):
    return text.count("\n", 0, idx) + 1


def visible_text(path, raw):
    """抽出使用者讀得到的文字（近似）。CSS 檔沒有可見文字。"""
    ext = path.suffix.lower()
    if ext not in MARKUP_EXT:
        return ""
    t = re.sub(r"<style[^>]*>.*?</style>", " ", raw, flags=re.S | re.I)
    t = re.sub(r"<script[^>]*>.*?</script>", " ", t, flags=re.S | re.I) if ext in (".html", ".htm") else t
    chunks = re.findall(r">([^<>{}]+)<", t)
    if ext not in (".html", ".htm"):
        # JSX／Vue 等：再收字串常值裡像句子的內容（含空白或中文）
        for m in re.findall(r"""["'`]([^"'`\n]{4,200})["'`]""", t):
            if (" " in m or re.search(r"[一-鿿]", m)) and not re.search(r"[\[\]{}/=]|^\s*[\w-]+(?:\s+[\w:-]+)+\s*$", m):
                chunks.append(m)
    return "\n".join(c.strip() for c in chunks if c.strip())


def run_static(paths, dom_ran):
    hits, texts = [], []
    for p in paths:
        try:
            raw = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for rule, pat, evidence, dom_covers in STATIC_RULES:
            if dom_ran and dom_covers:
                continue
            for m in re.finditer(pat, raw, flags=re.I):
                hits.append({"rule": rule, "where": "%s:%d" % (p, _lineno(raw, m.start())),
                             "evidence": evidence + "：`" + m.group(0)[:60] + "`", "layer": "static"})
        texts.append(visible_text(p, raw))
    return hits, "\n".join(t for t in texts if t)


def run_text_rules(text, where_label):
    hits, spans = [], []
    for pat in CLAIM_PATTERNS:
        for m in re.finditer(pat, text, flags=re.I):
            spans.append((max(0, m.start() - 16), min(len(text), m.end() + 16)))
    spans.sort()
    merged = []
    for a, b in spans:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    for a, b in merged:
        snippet = re.sub(r"\s+", " ", text[a:b]).strip()
        hits.append({"rule": "D1", "where": where_label,
                     "evidence": "宣稱「…" + snippet + "…」：PRODUCT.md 的可證實數據裡有出處嗎？沒有就是編造"})
    words = []
    for pat in CLICHE_WORDS:
        for m in re.finditer(pat, text, flags=re.I):
            words.append(m.group(0))
    if words:
        uniq = list(dict.fromkeys(words))
        hits.append({"rule": "D2", "where": where_label,
                     "evidence": "通用行銷詞 %d 處：%s" % (len(words), "、".join("「%s」" % w for w in uniq[:12]))})
    emojis = EMOJI_RE.findall(text)
    if emojis:
        uniq = "".join(dict.fromkeys(emojis))[:12]
        hits.append({"rule": "C9", "where": where_label,
                     "evidence": "文字裡有 %d 個 emoji（%s），常被當成功能圖示" % (len(emojis), uniq)})
    for h in hits:
        h["layer"] = "text"
    return hits


# ---------------------------------------------------------------- 畫面掃描

def run_dom(url, widths, out, no_install, log):
    import bootstrap
    from playwright.sync_api import sync_playwright
    hits, shots, metrics, page_text = [], [], {}, ""
    with sync_playwright() as p:
        browser = bootstrap.launch_chromium(p, no_install=no_install, log=log)
        try:
            for w in widths:
                mobile = w < 600
                ctx = browser.new_context(viewport={"width": w, "height": 844 if mobile else 900},
                                          is_mobile=mobile, has_touch=mobile)
                page = ctx.new_page()
                page.goto(url, wait_until="load", timeout=45000)
                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:  # noqa: BLE001  開發伺服器常有長連線，等不到就算了
                    pass
                page.evaluate(SCROLL_JS)
                tag = ("mobile-%d" if mobile else "desktop-%d") % w
                for kind, full in (("fold", False), ("full", True)):
                    name = "%s-%s.png" % (tag, kind)
                    page.screenshot(path=os.path.join(out, name), full_page=full)
                    shots.append(name)
                res = page.evaluate(DOM_JS, w)
                for h in res["hits"]:
                    h["layer"] = "dom"
                    h["viewport"] = str(w)
                    hits.append(h)
                metrics[str(w)] = res["metrics"]
                if not page_text:
                    page_text = page.evaluate("() => document.body.innerText")
                ctx.close()
        finally:
            browser.close()
    return hits, shots, metrics, page_text


# ---------------------------------------------------------------- 彙整

# 同一條規則、同一種改法的命中合成一筆，審查者只需處理一次
AGGREGATE_RULES = {"A3", "E4", "E5"}


def _group_key(h):
    r = h["rule"]
    if r in AGGREGATE_RULES:
        return (r,)
    if h.get("layer") == "dom":
        return (r, h["where"]) if r not in ("B3", "B4") else (r, h["where"], h["evidence"])
    return (r, h["where"], h["evidence"])


def finalize(raw, max_per_rule):
    merged, order = {}, []
    for h in raw:
        key = _group_key(h)
        inst = (h["where"], h["evidence"].split("，y≈")[0])
        if key in merged:
            m = merged[key]
            vp = h.get("viewport")
            if vp and vp not in m["viewports"]:
                m["viewports"].append(vp)
            if inst not in m["_inst"]:
                m["_inst"].append(inst)
            continue
        item = dict(h)
        item["viewports"] = [h["viewport"]] if h.get("viewport") else []
        item.pop("viewport", None)
        if not item.get("severity"):
            item["severity"] = RULES[item["rule"]]["severity"]
        item["_inst"] = [inst]
        merged[key] = item
        order.append(key)
    for m in merged.values():
        inst = m.pop("_inst")
        if len(inst) > 1:
            wheres = list(dict.fromkeys(w for w, _ in inst))
            m["where"] = "；".join(wheres[:4]) + ("；…" if len(wheres) > 4 else "")
            m["count"] = len(inst)
            m["evidence"] = "%s（同類共 %d 處，一併處理）" % (m["evidence"], len(inst))
    by_rule, out = {}, []
    for k in order:
        by_rule.setdefault(merged[k]["rule"], []).append(merged[k])
    rule_order = sorted(by_rule, key=lambda r: (r[0], int(r[1:])))
    for r in rule_order:
        items = sorted(by_rule[r], key=lambda x: SEVERITIES.index(x["severity"]))
        out.extend(items[:max_per_rule])
        if len(items) > max_per_rule:
            rest = items[max_per_rule:]
            out.append({"rule": r, "where": "（彙整）", "layer": rest[0].get("layer", ""),
                        "severity": rest[0]["severity"], "viewports": [],
                        "evidence": "同類命中另有 %d 處，修正時請一併處理（例：%s）" % (
                            len(rest), "；".join(x["where"] for x in rest[:3]))})
    for i, h in enumerate(out, 1):
        h["id"] = "S%02d" % i
        h["name"] = RULES[h["rule"]]["name"]
    return out


def main():
    ap = argparse.ArgumentParser(description="設計審查掃描器")
    ap.add_argument("--url")
    ap.add_argument("--file")
    ap.add_argument("--src")
    ap.add_argument("--out", required=True)
    ap.add_argument("--widths", default="1440,390")
    ap.add_argument("--no-dom", action="store_true")
    ap.add_argument("--no-install", action="store_true")
    ap.add_argument("--max-per-rule", type=int, default=8)
    a = ap.parse_args()
    if not (a.url or a.file or a.src):
        print("錯誤：至少要給 --url、--file 或 --src 其中一個。")
        return 2
    if a.file and not os.path.isfile(a.file):
        print("錯誤：找不到檔案 " + a.file)
        return 2
    os.makedirs(a.out, exist_ok=True)
    log = lambda m: print(m, file=sys.stderr)  # noqa: E731
    widths = [int(w) for w in a.widths.split(",") if w.strip()]
    notes, raw, shots, metrics, page_text = [], [], [], {}, ""
    dom_ok = False
    page_url = a.url or (Path(a.file).resolve().as_uri() if a.file else None)
    if page_url and not a.no_dom:
        try:
            import bootstrap
            if bootstrap.ensure_dom(no_install=a.no_install, log=log):
                dom_hits, shots, metrics, page_text = run_dom(page_url, widths, a.out, a.no_install, log)
                raw.extend(dom_hits)
                dom_ok = True
            else:
                notes.append("畫面掃描未執行：缺少 playwright，且指定不安裝。請改用截圖工具取得畫面，或請使用者提供截圖。")
        except Exception as e:  # noqa: BLE001
            notes.append("畫面掃描失敗：%s。已降級為靜態掃描。" % str(e).splitlines()[0][:200])
    elif not page_url:
        notes.append("沒有可開啟的頁面（未給 --url 或 --file），只做靜態掃描；截圖需另外取得。")
    sources = collect_sources(a.file, a.src)
    static_text = ""
    if sources:
        s_hits, static_text = run_static(sources, dom_ok)
        raw.extend(s_hits)
    raw.extend(run_text_rules(page_text if dom_ok else static_text, "頁面文字" if dom_ok else "原始碼文字"))
    hits = finalize(raw, a.max_per_rule)
    result = {
        "scanner_version": SCANNER_VERSION, "ruleset_version": RULESET_VERSION,
        "target": a.url or a.file or a.src, "src": a.src,
        "layers": {"static": bool(sources), "dom": dom_ok, "text": True},
        "notes": notes, "screenshots": shots, "metrics": metrics, "hits": hits,
    }
    with open(os.path.join(a.out, "scan.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    counts = {s: sum(1 for h in hits if h["severity"] == s) for s in SEVERITIES}
    print("掃描完成：%s" % os.path.join(a.out, "scan.json"))
    print("檢查層：靜態 %s　畫面 %s　文字 是" % ("是" if sources else "否", "是" if dom_ok else "否"))
    print("命中 %d 筆（P0 %d、P1 %d、P2 %d）" % (len(hits), counts["P0"], counts["P1"], counts["P2"]))
    for h in hits:
        print("  %s %s %s｜%s｜%s" % (h["id"], h["severity"], h["rule"], h["name"], h["where"]))
    for n in notes:
        print("注意：" + n)
    if shots:
        print("截圖：" + "、".join(shots))
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
