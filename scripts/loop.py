#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""設計審查迴圈：回合管理、閘門判定、報告產出。

  python loop.py init <dir> [--mode review|full|lite] [--max-rounds 3] [--target 說明]
  python loop.py next <dir>              建立下一回合資料夾並印出路徑
  python loop.py brief <dir>             產生本回合審查子代理的提示詞（路徑全部填好），也存成 brief.md
  python loop.py gate <dir> [--round N]  判定閘門、產出 report.md、更新 state.json（可重跑，會覆蓋同回合紀錄）
  python loop.py status <dir>
  python loop.py extend <dir> [--by 2]   使用者要求再修時，延長回合上限

gate 退出碼：
  0 通過
  1 未通過：依報告修正，修完 next 開下一回合，整套重審
  2 審查檔不完整或格式錯：先補好 review.json 再重跑 gate（不算一回合）
  3 停下交給使用者：達回合上限，或同一問題反覆回歸
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rules import PRINCIPLES, PRINCIPLE_RULE, RULES, SEVERITIES, SEVERITY_NAMES, rule_name  # noqa: E402

# 凍結契約 FROZEN：閘門門檻。要調整請另開 GATE_V2，並更新 FROZEN.md，不得就地修改。
GATE_V1 = {
    "min_score": 2,                     # 四原則每項至少 2 分（滿分 3）
    "tests": ("three_second", "name_swap", "core_task"),
    "blocking": ("P0", "P1"),           # 這兩級只要有一項未修就不通過
    "max_rounds": 3,                    # 自動修正回合上限，到了就停下交給使用者
    "regress_limit": 2,                 # 同一問題修好又回來達兩次，視為打轉
}
FROZEN = {"GATE_V1"}
GATE = GATE_V1

TEST_NAMES = {"three_second": "三秒測試", "name_swap": "換名測試", "core_task": "核心任務測試"}
EXIT = {"PASS": 0, "FAIL": 1, "INVALID": 2, "ESCALATE": 3}
RESULT_NAMES = {"PASS": "通過", "FAIL": "未通過", "INVALID": "審查檔不完整", "ESCALATE": "停下交給使用者"}
FINDING_ID = re.compile(r"^F\d{2,}$")


# ---------------------------------------------------------------- 狀態

def state_path(d):
    return os.path.join(d, "state.json")


def load_state(d):
    p = state_path(d)
    if not os.path.exists(p):
        return {"version": 1, "mode": "review", "max_rounds": GATE["max_rounds"], "target": "", "rounds": []}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_state(d, st):
    os.makedirs(d, exist_ok=True)
    with open(state_path(d), "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)


def round_dirs(d):
    out = []
    if os.path.isdir(d):
        for name in os.listdir(d):
            m = re.match(r"^round-(\d+)$", name)
            if m and os.path.isdir(os.path.join(d, name)):
                out.append(int(m.group(1)))
    return sorted(out)


def read_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- 驗證與判定（純函式，測試直接呼叫）

def _score(v):
    if isinstance(v, dict):
        v = v.get("score")
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _note(v):
    return v.get("note", "") if isinstance(v, dict) else ""


def validate_review(review, scan=None):
    """回傳 (errors, warnings)。errors 非空代表審查不完整，閘門不能判定。"""
    errors, warnings = [], []
    if not isinstance(review, dict):
        return ["review.json 不是物件"], warnings
    scores = review.get("scores")
    if not isinstance(scores, dict):
        errors.append("缺少 scores（四原則分數）")
    else:
        for p in PRINCIPLES:
            s = _score(scores.get(p))
            if s is None or not 0 <= s <= 3:
                errors.append("scores「%s」要是 0 到 3 的整數" % p)
            elif s < 3 and not _note(scores.get(p)).strip():
                warnings.append("scores「%s」沒寫理由（note）" % p)
    tests = review.get("tests")
    if not isinstance(tests, dict):
        errors.append("缺少 tests（三項測試）")
    else:
        for t in GATE["tests"]:
            v = tests.get(t)
            if not isinstance(v, dict) or not isinstance(v.get("pass"), bool):
                errors.append("tests「%s」要有 pass（true／false）" % t)
            elif not str(v.get("note", "")).strip():
                errors.append("tests「%s」要寫 note（看到了什麼）" % t)
    findings = review.get("findings")
    if not isinstance(findings, list):
        errors.append("缺少 findings 陣列（沒有問題也要給空陣列）")
        findings = []
    seen = set()
    for i, f in enumerate(findings):
        tag = "findings[%d]" % i
        if not isinstance(f, dict):
            errors.append(tag + " 不是物件")
            continue
        fid = f.get("id", "")
        if not FINDING_ID.match(str(fid)):
            errors.append(tag + " 的 id 要是 F01 這種格式")
        elif fid in seen:
            errors.append("finding 編號重複：" + fid)
        seen.add(fid)
        if f.get("severity") not in SEVERITIES:
            errors.append("%s（%s）的 severity 要是 P0、P1 或 P2" % (tag, fid))
        if f.get("principle") not in PRINCIPLES:
            errors.append("%s（%s）的 principle 要是四原則之一" % (tag, fid))
        rule = f.get("rule")
        if rule not in RULES and rule != PRINCIPLE_RULE:
            warnings.append("%s 的 rule「%s」不在規則表，若是清單外的問題請填「%s」" % (fid, rule, PRINCIPLE_RULE))
        for k in ("location", "problem", "fix"):
            if not str(f.get(k, "")).strip():
                errors.append("%s（%s）缺少 %s" % (tag, fid, k))
        if f.get("severity") in GATE["blocking"] and len(str(f.get("fix", "")).strip()) < 8:
            errors.append("%s 是 %s，fix 要寫成能直接動手的具體改法" % (fid, f.get("severity")))
        w = f.get("waiver")
        if w:
            if not isinstance(w, dict) or w.get("by") != "user" or not str(w.get("reason", "")).strip():
                errors.append("%s 的豁免無效：只有使用者能豁免，要寫 by=user 與理由" % fid)
    dismissed = review.get("dismissed", [])
    if not isinstance(dismissed, list):
        errors.append("dismissed 要是陣列")
        dismissed = []
    for d in dismissed:
        if not isinstance(d, dict) or not d.get("scan_id") or len(str(d.get("reason", "")).strip()) < 4:
            errors.append("dismissed 每一筆都要有 scan_id 與排除理由：%s" % json.dumps(d, ensure_ascii=False))
    if scan is not None:
        scan_ids = {h["id"] for h in scan.get("hits", [])}
        covered = {s for f in findings if isinstance(f, dict) for s in (f.get("scan_ids") or [])}
        covered |= {d.get("scan_id") for d in dismissed if isinstance(d, dict)}
        missing = sorted(scan_ids - covered)
        if missing:
            errors.append("掃描命中沒有逐條處理（確認就放進 findings 的 scan_ids，排除就寫進 dismissed）：" + "、".join(missing))
        unknown = sorted(c for c in covered - scan_ids if c)
        if unknown:
            warnings.append("引用了不存在的掃描編號：" + "、".join(unknown))
    return errors, warnings


def evaluate(review, scan=None):
    errors, warnings = validate_review(review, scan)
    if errors:
        return {"result": "INVALID", "errors": errors, "warnings": warnings,
                "blocking": [], "low_scores": [], "failed_tests": []}
    findings = review.get("findings", [])
    blocking = [f for f in findings if f["severity"] in GATE["blocking"] and not f.get("waiver")]
    low = [p for p in PRINCIPLES if _score(review["scores"][p]) < GATE["min_score"]]
    failed = [t for t in GATE["tests"] if not review["tests"][t]["pass"]]
    result = "PASS" if not (blocking or low or failed) else "FAIL"
    return {"result": result, "errors": [], "warnings": warnings,
            "blocking": blocking, "low_scores": low, "failed_tests": failed}


def presence_regressions(history, current):
    """history：前面各回合的 finding 編號集合（依序）；current：本回合。
    回傳 {編號: 回歸次數}，回歸＝曾出現、後來消失、又再出現。"""
    seq = list(history) + [set(current)]
    counts = {}
    for fid in set(current):
        seen_before, gone, n = False, False, 0
        for s in seq:
            if fid in s:
                if seen_before and gone:
                    n += 1
                    gone = False
                seen_before = True
            elif seen_before:
                gone = True
        if n:
            counts[fid] = n
    return counts


def decide(eval_result, round_no, max_rounds, regressions, blocking_ids=None):
    r = eval_result["result"]
    if r in ("PASS", "INVALID"):
        return r
    watched = {k: v for k, v in regressions.items() if blocking_ids is None or k in blocking_ids}
    if any(n >= GATE["regress_limit"] for n in watched.values()):
        return "ESCALATE"
    if round_no >= max_rounds:
        return "ESCALATE"
    return "FAIL"


# ---------------------------------------------------------------- 報告

def render_report(round_no, target, scan, review, ev, final, diff, regressions, max_rounds, prev_fixes=None):
    L = []
    f_all = review.get("findings", []) if isinstance(review, dict) else []
    cnt = {s: sum(1 for f in f_all if f.get("severity") == s and not f.get("waiver")) for s in SEVERITIES}
    L.append("# 設計審查報告：第 %d 回合" % round_no)
    L.append("")
    L.append("- 目標：`%s`" % target if target else "- 目標：（未記錄）")
    L.append("- 閘門結果：**%s**（P0 %d 項、P1 %d 項、P2 %d 項）" % (RESULT_NAMES[final], cnt["P0"], cnt["P1"], cnt["P2"]))
    layers = (scan or {}).get("layers", {})
    L.append("- 機器掃描：靜態 %s、畫面 %s；審查者：%s" % (
        "有" if layers.get("static") else "無", "有" if layers.get("dom") else "無",
        {"subagent": "獨立子代理", "self": "設計者本人（非獨立）"}.get(review.get("reviewer"), review.get("reviewer", "未註明"))))
    for n in (scan or {}).get("notes", []):
        L.append("- 注意：" + n)
    if scan is None:
        L.append("- 注意：本回合沒有 scan.json，只有人工審查。")
    L.append("")
    if final == "INVALID":
        L.append("## 審查檔需要補齊")
        L += ["- " + e for e in ev["errors"]]
        return "\n".join(L) + "\n"

    L.append("## 第一層：做對了嗎")
    L.append("")
    L.append("| 原則 | 分數 | 理由 |")
    L.append("|---|---|---|")
    for p in PRINCIPLES:
        v = review["scores"][p]
        mark = "" if _score(v) >= GATE["min_score"] else "（未達 %d）" % GATE["min_score"]
        L.append("| %s | %d／3%s | %s |" % (p, _score(v), mark, _note(v).replace("|", "／") or "（無）"))
    L.append("")
    L.append("| 測試 | 結果 | 看到了什麼 |")
    L.append("|---|---|---|")
    for t in GATE["tests"]:
        v = review["tests"][t]
        L.append("| %s | %s | %s |" % (TEST_NAMES[t], "通過" if v["pass"] else "不通過", str(v.get("note", "")).replace("|", "／")))
    L.append("")

    hits = {h["id"]: h for h in (scan or {}).get("hits", [])}
    for sev in SEVERITIES:
        items = [f for f in f_all if f.get("severity") == sev]
        if not items:
            continue
        L.append("## %s：%s" % (sev, SEVERITY_NAMES[sev]))
        L.append("")
        for f in items:
            title = f.get("title") or rule_name(f.get("rule"))
            L.append("### %s｜%s" % (f["id"], title))
            L.append("")
            L.append("- 位置：" + str(f.get("location", "")))
            L.append("- 違反：%s（%s）" % (f.get("principle", ""), f.get("rule", "")))
            L.append("- 問題：" + str(f.get("problem", "")))
            if f.get("why"):
                L.append("- 為什麼：" + str(f["why"]))
            L.append("- 怎麼改：" + str(f.get("fix", "")))
            if f.get("scan_ids"):
                L.append("- 對應掃描：" + "、".join(f["scan_ids"]))
            if f.get("waiver"):
                L.append("- 已豁免（使用者同意）：" + str(f["waiver"].get("reason", "")))
            if f["id"] in regressions:
                L.append("- **回歸**：這個問題之前修好過，又出現了（第 %d 次）" % regressions[f["id"]])
            L.append("")
    dismissed = review.get("dismissed", [])
    if dismissed:
        L.append("## 排除的掃描命中")
        L.append("")
        L.append("| 掃描 | 規則 | 排除理由 |")
        L.append("|---|---|---|")
        for d in dismissed:
            h = hits.get(d["scan_id"], {})
            L.append("| %s | %s %s | %s |" % (d["scan_id"], h.get("rule", ""), rule_name(h.get("rule", "")), str(d["reason"]).replace("|", "／")))
        L.append("")
    if review.get("positives"):
        L.append("## 保留清單（做對的地方，修正時不要動到）")
        L.append("")
        L += ["- " + str(p) for p in review["positives"]]
        L.append("")
    if diff:
        L.append("## 與上一回合比較")
        L.append("")
        for k, name in (("resolved", "已解決"), ("persisting", "仍存在"), ("new", "新出現")):
            L.append("- %s：%s" % (name, "、".join(diff[k]) if diff[k] else "無"))
        L.append("")
    if prev_fixes:
        L.append("## 上一回合做了哪些修正")
        L.append("")
        L.append(prev_fixes.strip())
        L.append("")
    L.append("## 下一步")
    L.append("")
    if final == "PASS":
        L.append("閘門通過。交付前用 validate_punct.py 檢查本報告，再把成品、前後截圖與本報告交給使用者，並詢問是否滿意。")
        L.append("通過之後不要再改成品；任何修改（包括 P2）都要開新回合重審，報告才會跟成品對得上。")
        if cnt["P2"]:
            L.append("仍有 %d 項 P2 建議，列給使用者決定；使用者同意修，就修完開新回合。" % cnt["P2"])
    elif final == "FAIL":
        parts = []
        if ev["blocking"]:
            parts.append("修正 " + "、".join(f["id"] for f in ev["blocking"]))
        if ev["low_scores"]:
            parts.append("把「" + "、".join(ev["low_scores"]) + "」拉到 %d 分以上" % GATE["min_score"])
        if ev["failed_tests"]:
            parts.append("讓 " + "、".join(TEST_NAMES[t] for t in ev["failed_tests"]) + " 通過")
        L.append("依序處理：" + "；".join(parts) + "。先修 P0 再修 P1，每項修正對應一個 F 編號，不要順手重做沒被點名的地方。")
        L.append("修完把每個 F 編號改了什麼寫進本回合的 `fixes.md`，再執行 `loop.py next` 開第 %d 回合，重新掃描並重新審查整頁（剩餘回合：%d）。" % (round_no + 1, max_rounds - round_no))
    else:
        reason = "同一問題反覆回歸（%s）" % "、".join(k for k, v in regressions.items() if v >= GATE["regress_limit"]) \
            if any(v >= GATE["regress_limit"] for v in regressions.values()) else "已達回合上限 %d" % max_rounds
        L.append("停止自動修正：%s。請把剩下的問題交給使用者決定：" % reason)
        L.append("1. 接受某些項目（使用者豁免，寫明理由）；")
        L.append("2. 方向本身有問題，回到步驟 2 重新定方向；")
        L.append("3. 再給幾回合（`loop.py extend`）。")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- 指令

def cmd_init(a):
    st = load_state(a.dir)
    if st["rounds"] and not a.force:
        print("已有 %d 回合紀錄；要重新開始請加 --force。" % len(st["rounds"]))
        return 2
    st = {"version": 1, "mode": a.mode, "max_rounds": a.max_rounds, "target": a.target or "", "rounds": [],
          "created": time.strftime("%Y-%m-%dT%H:%M:%S")}
    save_state(a.dir, st)
    print("已建立 %s（模式 %s，回合上限 %d）" % (state_path(a.dir), a.mode, a.max_rounds))
    return 0


def cmd_next(a):
    existing = round_dirs(a.dir)
    n = (existing[-1] + 1) if existing else 1
    p = os.path.join(a.dir, "round-%d" % n)
    os.makedirs(p, exist_ok=True)
    print(p)
    return 0


def cmd_gate(a):
    st = load_state(a.dir)
    rounds = round_dirs(a.dir)
    if not rounds:
        print("還沒有任何回合資料夾，先執行 loop.py next。")
        return 2
    n = a.round or rounds[-1]
    rd = os.path.join(a.dir, "round-%d" % n)
    rp = os.path.join(rd, "review.json")
    if not os.path.exists(rp):
        print("找不到 %s：先完成審查再跑閘門。" % rp)
        return 2
    try:
        review = read_json(rp)
    except ValueError as e:
        print("review.json 不是合法 JSON：%s" % e)
        return 2
    sp = os.path.join(rd, "scan.json")
    scan = read_json(sp) if os.path.exists(sp) else None
    ev = evaluate(review, scan)
    prev = [r for r in st["rounds"] if r["round"] < n]
    findings = [f for f in review.get("findings", []) if isinstance(f, dict) and f.get("id")]
    cur_all = [f["id"] for f in findings if not f.get("waiver")]
    cur_ids = [f["id"] for f in findings if f.get("severity") in GATE["blocking"] and not f.get("waiver")]
    sev = {f["id"]: f.get("severity", "") for f in findings}
    history = [set(r.get("all_ids", r.get("ids", []))) for r in prev]
    regressions = presence_regressions(history, cur_all) if ev["result"] != "INVALID" else {}
    final = decide(ev, n, st.get("max_rounds", GATE["max_rounds"]), regressions, set(cur_ids))
    diff = None
    if prev and final != "INVALID":
        last_sev = prev[-1].get("sev", {})
        last = set(prev[-1].get("all_ids", prev[-1].get("ids", [])))
        cur = set(cur_all)
        tag = lambda i, m: "%s（%s）" % (i, m.get(i)) if m.get(i) else i  # noqa: E731
        diff = {"resolved": [tag(i, last_sev) for i in sorted(last - cur)],
                "persisting": [tag(i, sev) for i in sorted(last & cur)],
                "new": [tag(i, sev) for i in sorted(cur - last)]}
    target = st.get("target") or (scan or {}).get("target", "")
    pf = os.path.join(a.dir, "round-%d" % (n - 1), "fixes.md")
    prev_fixes = open(pf, encoding="utf-8").read() if n > 1 and os.path.exists(pf) else None
    report = render_report(n, target, scan, review, ev, final, diff, regressions,
                           st.get("max_rounds", GATE["max_rounds"]), prev_fixes)
    with open(os.path.join(rd, "report.md"), "w", encoding="utf-8") as f:
        f.write(report)
    if final != "INVALID":
        rec = {"round": n, "result": final, "time": time.strftime("%Y-%m-%dT%H:%M:%S"), "ids": sorted(cur_ids),
               "all_ids": sorted(cur_all), "sev": {i: sev[i] for i in cur_all},
               "counts": {s: sum(1 for f in review["findings"] if f["severity"] == s and not f.get("waiver")) for s in SEVERITIES},
               "scores": {p: _score(review["scores"][p]) for p in PRINCIPLES},
               "tests": {t: review["tests"][t]["pass"] for t in GATE["tests"]}}
        st["rounds"] = [r for r in st["rounds"] if r["round"] != n] + [rec]
        st["rounds"].sort(key=lambda r: r["round"])
        save_state(a.dir, st)
    # 主控台摘要
    print("第 %d 回合閘門：%s" % (n, RESULT_NAMES[final]))
    for e in ev["errors"]:
        print("  錯誤：" + e)
    for w in ev["warnings"]:
        print("  提醒：" + w)
    if final != "INVALID":
        if ev["blocking"]:
            print("  待修：" + "、".join("%s(%s)" % (f["id"], f["severity"]) for f in ev["blocking"]))
        if ev["low_scores"]:
            print("  分數不足：" + "、".join(ev["low_scores"]))
        if ev["failed_tests"]:
            print("  測試不通過：" + "、".join(TEST_NAMES[t] for t in ev["failed_tests"]))
        if regressions:
            print("  回歸：" + "、".join("%s×%d" % kv for kv in regressions.items()))
    print("報告：" + os.path.join(rd, "report.md"))
    punct = os.path.join(HERE, "validate_punct.py")
    if os.path.exists(punct):
        r = subprocess.run([sys.executable, punct, os.path.join(rd, "report.md")], capture_output=True, text=True)
        if r.returncode != 0:
            print("  報告標點未通過（交付前要修，改 review.json 的文字後重跑 gate）：")
            print("    " + "\n    ".join(r.stdout.strip().splitlines()[:8]))
    return EXIT[final]


BRIEF_TEMPLATE = """你是獨立的設計審查者，沒有參與這個設計。只審查，不要修改任何檔案（{review} 除外）。

請依序讀：
1. 產品事實：{product}{design}
2. 規則：{skill}/references/principles.md、{skill}/references/antipatterns.md、{skill}/references/review-rubric.md；
   品味基準：{skill}/references/craft.md（版面、字體、色彩、元件是否做到位），以及符合這次畫面類型的 {skill}/references/platforms.md 段落
3. 本回合掃描結果：{scan}
4. 截圖：{shots}
{prev}5. 程式碼只用來定位問題、寫出精確的修改位置，不要用來推測設計意圖：{src}

要做的事：
A. 第一層：依 principles.md 給四原則打 0 到 3 分並寫理由；執行三秒測試、換名測試、核心任務測試。
B. 第二層：逐條處理 scan.json 的每一筆命中，確認就放進某個 finding 的 scan_ids，誤報就寫進 dismissed 並說明理由；
   再對照 antipatterns.md 中標「人工」的規則與四原則，補上機器抓不到的問題。
C. 每個 finding 都要寫出能直接動手的改法（改哪個元素、改成什麼），優先考慮「刪除」。
   fix 只寫對畫面的具體改法，不要寫「先回到步驟 2」這類流程指令；方向有問題就照實打分、寫 D5 或「原則」finding。
D. 列出 positives：做對的地方，避免修正時被破壞。
E. 依 review-rubric.md 的格式寫入 {review}，round 填 {n}，reviewer 填 subagent。
F. 回報：預估閘門結果、P0／P1 數量、最關鍵的三個問題。

編號規則：{numbering}
文字規範：中文用全形標點，不用破折號；選擇器、檔名、程式碼用反引號包起來。
"""


def _max_fid(review):
    nums = [int(f["id"][1:]) for f in review.get("findings", []) if isinstance(f, dict) and FINDING_ID.match(str(f.get("id", "")))]
    return max(nums) if nums else 0


def cmd_brief(a):
    rounds = round_dirs(a.dir)
    if not rounds:
        print("還沒有任何回合資料夾，先執行 loop.py next。")
        return 2
    n = a.round or rounds[-1]
    rd = os.path.abspath(os.path.join(a.dir, "round-%d" % n))
    project = os.path.dirname(os.path.abspath(a.dir))
    skill = os.path.dirname(HERE)
    product = os.path.abspath(a.product) if a.product else os.path.join(project, "PRODUCT.md")
    if not os.path.exists(product):
        product += "（不存在：請先完成步驟 0 或 1，沒有產品事實就無法判斷量身打造）"
    design = os.path.join(project, "DESIGN.md")
    design = "；視覺契約：" + design if os.path.exists(design) else ""
    sp = os.path.join(rd, "scan.json")
    scan = read_json(sp) if os.path.exists(sp) else {}
    shots = "、".join(os.path.join(rd, x) for x in scan.get("screenshots", [])) or "（本回合沒有截圖：請用瀏覽器工具截圖，或使用使用者提供的截圖）"
    src = a.src or scan.get("src") or scan.get("target") or "（未提供）"
    if src and not re.match(r"^https?://", src) and not os.path.isabs(src):
        src = os.path.join(project, src) if os.path.exists(os.path.join(project, src)) else src
    prev, numbering = "", "第一回合從 F01 開始。"
    if n > 1:
        pd = os.path.abspath(os.path.join(a.dir, "round-%d" % (n - 1)))
        pr = os.path.join(pd, "review.json")
        pf = os.path.join(pd, "fixes.md")
        if os.path.exists(pr):
            prev = "   上一回合審查：%s%s\n" % (pr, "；上一回合的修正紀錄：" + pf if os.path.exists(pf) else "")
            numbering = ("同一個問題沿用上一回合的 F 編號；新問題從 F%02d 開始。"
                         "上一回合 fix 明確要求、而且已經照做的改法，除非違反原則，否則不要列成新問題；"
                         "真的要推翻時，沿用原本那個 F 編號並在 why 說明為什麼要改回（這樣閘門才抓得到來回打轉）。") % (_max_fid(read_json(pr)) + 1)
    if prev:
        prev = "4b. " + prev.lstrip()
    text = BRIEF_TEMPLATE.format(review=os.path.join(rd, "review.json"), product=product, design=design, skill=skill,
                                 scan=sp if scan else "（本回合沒有 scan.json）", shots=shots, prev=prev, src=src,
                                 n=n, numbering=numbering)
    with open(os.path.join(rd, "brief.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    return 0


def cmd_status(a):
    st = load_state(a.dir)
    print("模式 %s，回合上限 %d，目標：%s" % (st.get("mode"), st.get("max_rounds"), st.get("target") or "（未記錄）"))
    if not st["rounds"]:
        print("尚無回合紀錄。")
    for r in st["rounds"]:
        c = r.get("counts", {})
        print("  第 %d 回合：%s｜P0 %d、P1 %d、P2 %d｜分數 %s" % (
            r["round"], RESULT_NAMES.get(r["result"], r["result"]), c.get("P0", 0), c.get("P1", 0), c.get("P2", 0),
            "、".join("%s %s" % (k, v) for k, v in r.get("scores", {}).items())))
    return 0


def cmd_extend(a):
    st = load_state(a.dir)
    st["max_rounds"] = st.get("max_rounds", GATE["max_rounds"]) + a.by
    save_state(a.dir, st)
    print("回合上限延長為 %d。" % st["max_rounds"])
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Tailored 設計審查迴圈")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init")
    p.add_argument("dir")
    p.add_argument("--mode", choices=("review", "full", "lite"), default="review")
    p.add_argument("--max-rounds", type=int, default=GATE["max_rounds"])
    p.add_argument("--target", default="")
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("next")
    p.add_argument("dir")
    p = sub.add_parser("gate")
    p.add_argument("dir")
    p.add_argument("--round", type=int)
    p = sub.add_parser("brief")
    p.add_argument("dir")
    p.add_argument("--round", type=int)
    p.add_argument("--product")
    p.add_argument("--src")
    p = sub.add_parser("status")
    p.add_argument("dir")
    p = sub.add_parser("extend")
    p.add_argument("dir")
    p.add_argument("--by", type=int, default=2)
    a = ap.parse_args(argv)
    return {"init": cmd_init, "next": cmd_next, "gate": cmd_gate, "brief": cmd_brief,
            "status": cmd_status, "extend": cmd_extend}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
