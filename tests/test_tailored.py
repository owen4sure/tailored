#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""回歸測試：Tailored。執行：python tests/test_tailored.py（或 pytest）
純邏輯、凍結契約、閘門、靜態掃描不需重相依；畫面掃描在 playwright 可用時才跑。"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPTS = os.path.join(ROOT, "scripts")
FIX = os.path.join(HERE, "fixtures")
sys.path.insert(0, SCRIPTS)

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  [PASS] " + name)
    else:
        FAIL += 1
        print("  [FAIL] " + name)


import rules  # noqa: E402
import loop  # noqa: E402
import scan  # noqa: E402
import roll  # noqa: E402

# ------------------------------------------------------------ 1) 凍結契約
print("1) 凍結契約")
check("GATE_V1 最低分 2", loop.GATE_V1["min_score"] == 2)
check("GATE_V1 三項測試", loop.GATE_V1["tests"] == ("three_second", "name_swap", "core_task"))
check("GATE_V1 擋 P0、P1", loop.GATE_V1["blocking"] == ("P0", "P1"))
check("GATE_V1 回合上限 3", loop.GATE_V1["max_rounds"] == 3)
check("GATE_V1 回歸上限 2", loop.GATE_V1["regress_limit"] == 2)
check("GATE_V1 標記凍結", "GATE_V1" in loop.FROZEN)
check("退出碼凍結", loop.EXIT == {"PASS": 0, "FAIL": 1, "INVALID": 2, "ESCALATE": 3})
expected_ids = {"A%d" % i for i in range(1, 6)} | {"B%d" % i for i in range(1, 6)} | \
    {"C%d" % i for i in range(1, 13)} | {"D%d" % i for i in range(1, 6)} | {"E%d" % i for i in range(1, 6)}
check("規則編號 v1.0 完整（新增可以，不能少）", expected_ids <= set(rules.RULES))
check("四原則順序", rules.PRINCIPLES == ("符合預期", "主次分明", "克制", "量身打造"))
check("每條規則的原則都在四原則內", all(r["principle"] in rules.PRINCIPLES for r in rules.RULES.values()))
ap_md = open(os.path.join(ROOT, "references", "antipatterns.md"), encoding="utf-8").read()
missing_doc = [k for k in rules.RULES if not re.search(r"\*\*%s " % k, ap_md)]
check("antipatterns.md 涵蓋每個規則編號（缺：%s）" % "、".join(missing_doc), not missing_doc)

# ------------------------------------------------------------ 2) 閘門判定
print("2) 閘門判定")


def good_review():
    return {
        "round": 1, "reviewer": "subagent",
        "scores": {p: {"score": 2, "note": "理由"} for p in rules.PRINCIPLES},
        "tests": {t: {"pass": True, "note": "看到了"} for t in loop.GATE_V1["tests"]},
        "findings": [{"id": "F01", "rule": "C1", "principle": "克制", "severity": "P2", "location": "主標",
                      "problem": "漸層字", "fix": "改單色", "scan_ids": ["S01"]}],
        "dismissed": [{"scan_id": "S02", "reason": "品牌指定漸層"}],
    }


SCAN = {"hits": [{"id": "S01", "rule": "C1"}, {"id": "S02", "rule": "C2"}], "layers": {"static": True, "dom": True}}
check("合格審查 → 通過", loop.evaluate(good_review(), SCAN)["result"] == "PASS")
r = good_review()
r["findings"][0]["severity"] = "P0"
r["findings"][0]["fix"] = "刪除 h1 的漸層，改成單色 #fff"
check("有未修 P0 → 未通過", loop.evaluate(r, SCAN)["result"] == "FAIL")
r = good_review()
r["dismissed"] = []
ev = loop.evaluate(r, SCAN)
check("掃描命中沒處理 → 審查不完整", ev["result"] == "INVALID" and any("S02" in e for e in ev["errors"]))
r = good_review()
r["scores"]["克制"]["score"] = 1
check("分數低於 2 → 未通過", loop.evaluate(r, SCAN)["result"] == "FAIL")
r = good_review()
r["tests"]["name_swap"]["pass"] = False
check("換名測試失敗 → 未通過", loop.evaluate(r, SCAN)["result"] == "FAIL")
r = good_review()
r["findings"][0].update(severity="P1", fix="刪除 h1 的漸層，改成單色", waiver={"by": "user", "reason": "品牌規定"})
check("使用者豁免 P1 → 通過", loop.evaluate(r, SCAN)["result"] == "PASS")
r["findings"][0]["waiver"] = {"by": "agent", "reason": "我覺得還好"}
check("非使用者豁免 → 審查不完整", loop.evaluate(r, SCAN)["result"] == "INVALID")
r = good_review()
r["findings"][0].update(severity="P1", fix="改")
check("P1 的改法太空泛 → 審查不完整", loop.evaluate(r, SCAN)["result"] == "INVALID")
r = good_review()
del r["tests"]["core_task"]
check("缺一項測試 → 審查不完整", loop.evaluate(r, SCAN)["result"] == "INVALID")
r = good_review()
r["findings"].append(dict(r["findings"][0]))
check("F 編號重複 → 審查不完整", loop.evaluate(r, SCAN)["result"] == "INVALID")
check("沒有 scan.json 也能判定", loop.evaluate(good_review(), None)["result"] == "PASS")

# ------------------------------------------------------------ 3) 回歸與停止條件
print("3) 回歸與停止條件")
reg = loop.presence_regressions([{"F01"}, set()], ["F01"])
check("出現→消失→出現 算一次回歸", reg == {"F01": 1})
reg2 = loop.presence_regressions([{"F01"}, set(), {"F01"}, set()], ["F01"])
check("回歸兩次", reg2 == {"F01": 2})
check("持續存在不算回歸", loop.presence_regressions([{"F01"}, {"F01"}], ["F01"]) == {})
fail_ev = {"result": "FAIL"}
check("第 1 回合未通過 → 繼續修", loop.decide(fail_ev, 1, 3, {}) == "FAIL")
check("達回合上限 → 停下", loop.decide(fail_ev, 3, 3, {}) == "ESCALATE")
check("回歸兩次 → 停下", loop.decide(fail_ev, 2, 5, {"F01": 2}) == "ESCALATE")
check("回歸的是已不擋閘門的 P2 → 不停下", loop.decide(fail_ev, 2, 5, {"F09": 2}, {"F01"}) == "FAIL")
check("通過時不因回合數停下", loop.decide({"result": "PASS"}, 3, 3, {}) == "PASS")

# ------------------------------------------------------------ 4) 指令整合（init／next／gate）
print("4) 指令整合")
tmp = tempfile.mkdtemp(prefix="drl-")
d = os.path.join(tmp, "design-review")
LOOP = [sys.executable, os.path.join(SCRIPTS, "loop.py")]


def run(*args):
    return subprocess.run(LOOP + list(args), capture_output=True, text=True)


check("init 成功", run("init", d, "--target", "fixtures/slop.html").returncode == 0)
r1 = run("next", d).stdout.strip()
check("next 建立 round-1", r1.endswith("round-1") and os.path.isdir(r1))
json.dump(SCAN, open(os.path.join(r1, "scan.json"), "w", encoding="utf-8"), ensure_ascii=False)
bad = good_review()
bad["findings"][0].update(severity="P1", fix="刪除漸層，改成單色白字")
json.dump(bad, open(os.path.join(r1, "review.json"), "w", encoding="utf-8"), ensure_ascii=False)
g1 = run("gate", d)
check("第 1 回合有 P1 → 退出碼 1", g1.returncode == 1)
check("產出 report.md", os.path.exists(os.path.join(r1, "report.md")))
rep = open(os.path.join(r1, "report.md"), encoding="utf-8").read()
check("報告列出 F01 與怎麼改", "F01" in rep and "怎麼改" in rep)
check("報告通過全形標點檢查", "報告標點未通過" not in g1.stdout)
r2 = run("next", d).stdout.strip()
json.dump(SCAN, open(os.path.join(r2, "scan.json"), "w", encoding="utf-8"), ensure_ascii=False)
json.dump(good_review(), open(os.path.join(r2, "review.json"), "w", encoding="utf-8"), ensure_ascii=False)
g2 = run("gate", d)
check("第 2 回合修好 → 退出碼 0", g2.returncode == 0)
rep2 = open(os.path.join(r2, "report.md"), encoding="utf-8").read()
check("比較含 P2（F01 第 2 回合降為 P2 → 仍存在）", "仍存在：F01（P2）" in rep2)
st = json.load(open(os.path.join(d, "state.json"), encoding="utf-8"))
check("state 記了兩回合", [x["result"] for x in st["rounds"]] == ["FAIL", "PASS"])
check("重跑同回合 gate 不重複記錄", run("gate", d).returncode == 0 and
      len(json.load(open(os.path.join(d, "state.json"), encoding="utf-8"))["rounds"]) == 2)
br = run("brief", d, "--round", "2")
check("brief 產生提示詞並存檔", br.returncode == 0 and os.path.exists(os.path.join(r2, "brief.md")))
check("brief 帶上一回合審查與下一個 F 編號", "round-1" in br.stdout and "F02" in br.stdout)
check("brief 路徑已填好（沒有殘留 <…>）", "<round>" not in br.stdout and "<skill>" not in br.stdout)
r3 = run("next", d).stdout.strip()
json.dump({"scores": {}}, open(os.path.join(r3, "review.json"), "w", encoding="utf-8"))
check("審查檔格式錯 → 退出碼 2", run("gate", d).returncode == 2)
json.dump(SCAN, open(os.path.join(r3, "scan.json"), "w", encoding="utf-8"), ensure_ascii=False)
ok3 = good_review()
ok3["findings"] = []
ok3["dismissed"] = [{"scan_id": "S01", "reason": "已改單色"}, {"scan_id": "S02", "reason": "品牌指定漸層"}]
json.dump(ok3, open(os.path.join(r3, "review.json"), "w", encoding="utf-8"), ensure_ascii=False)
open(os.path.join(r2, "fixes.md"), "w", encoding="utf-8").write("- F01：主標漸層改成單色\n")
check("補好審查檔後第 3 回合通過", run("gate", d).returncode == 0)
rep3 = open(os.path.join(r3, "report.md"), encoding="utf-8").read()
check("比較列出已解決的 P2", "已解決：F01（P2）" in rep3)
check("報告帶出上一回合的 fixes.md", "主標漸層改成單色" in rep3)
check("extend 延長上限", run("extend", d, "--by", "2").returncode == 0 and
      json.load(open(os.path.join(d, "state.json"), encoding="utf-8"))["max_rounds"] == 5)
shutil.rmtree(tmp, ignore_errors=True)

# ------------------------------------------------------------ 5) 靜態掃描與文字規則
print("5) 靜態掃描")
slop = os.path.join(FIX, "slop.html")
clean = os.path.join(FIX, "clean.html")
from pathlib import Path  # noqa: E402
s_hits, s_text = scan.run_static([Path(slop)], dom_ran=False)
s_rules = {h["rule"] for h in s_hits}
check("slop 靜態命中 C1、A3、C4、C6、C8", {"C1", "A3", "C4", "C6", "C8"} <= s_rules)
t_rules = {h["rule"] for h in scan.run_text_rules(s_text, "原始碼文字")}
check("slop 文字命中 D1、D2、C9", {"D1", "D2", "C9"} <= t_rules)
check("行銷詞合成一筆", sum(1 for h in scan.run_text_rules(s_text, "x") if h["rule"] == "D2") == 1)
c_hits, c_text = scan.run_static([Path(clean)], dom_ran=False)
check("clean 靜態零命中", c_hits == [])
check("clean 文字零命中", scan.run_text_rules(c_text, "原始碼文字") == [])
s_hits_dom, _ = scan.run_static([Path(slop)], dom_ran=True)
check("有畫面掃描時，靜態只跑畫面看不到的規則（slop 沒有空 onClick → 零命中）", s_hits_dom == [])
fin = scan.finalize([{"rule": "E1", "where": "p%d" % i, "evidence": "x%d，y≈1px" % i, "layer": "dom", "viewport": "1440"}
                     for i in range(12)], 8)
check("每條規則最多 8 筆＋1 筆彙整", len(fin) == 9 and fin[-1]["where"] == "（彙整）")
agg = scan.finalize([{"rule": "A3", "where": "nav > a%d" % i, "evidence": "死連結 %d" % i, "layer": "dom", "viewport": "1440"}
                     for i in range(6)], 8)
check("A3 死連結合成一筆並註明數量", len(agg) == 1 and agg[0].get("count") == 6)
same = scan.finalize([{"rule": "E1", "where": "div.stat > span", "evidence": "對比 4.0：1，文字「%d」，y≈1px" % i, "layer": "dom",
                       "viewport": "1440"} for i in range(3)], 8)
check("同規則同位置合成一筆", len(same) == 1 and same[0].get("count") == 3)
check("掃描編號從 S01 起", fin[0]["id"] == "S01")

# ------------------------------------------------------------ 6) bootstrap（不觸發真實安裝）
print("6) bootstrap")
import bootstrap  # noqa: E402
calls = []
orig = (bootstrap._pip, bootstrap._install_chromium, bootstrap._have_py)
bootstrap._pip = lambda *p: calls.append(p)
bootstrap._install_chromium = lambda: calls.append(("chromium",))
bootstrap._have_py = lambda m: True
check("已安裝 → 不重裝", bootstrap.ensure_dom(log=lambda *a: None) and calls == [])
bootstrap._have_py = lambda m: False
calls.clear()
bootstrap.ensure_dom(log=lambda *a: None)
check("缺少 → 嘗試安裝 playwright 與 chromium", ("playwright",) in calls and ("chromium",) in calls)
calls.clear()
check("指定不安裝 → 回報不可用且不安裝", bootstrap.ensure_dom(no_install=True, log=lambda *a: None) is False and calls == [])
bootstrap._pip, bootstrap._install_chromium, bootstrap._have_py = orig

# ------------------------------------------------------------ 7) 擲骰與標點
print("7) 擲骰與標點")
check("同一個 seed 結果相同", roll.roll(["甲", "乙", "丙"], 7) == roll.roll(["甲", "乙", "丙"], 7))
try:
    roll.roll(["只有一個"])
    check("候選少於兩個要報錯", False)
except ValueError:
    check("候選少於兩個要報錯", True)
PUNCT = [sys.executable, os.path.join(SCRIPTS, "validate_punct.py")]
docs = [os.path.join(ROOT, "SKILL.md"), os.path.join(ROOT, "FROZEN.md")] + \
    [os.path.join(ROOT, "references", f) for f in sorted(os.listdir(os.path.join(ROOT, "references")))]
bad_docs = [os.path.basename(p) for p in docs if subprocess.run(PUNCT + [p], capture_output=True).returncode != 0]
check("SKILL.md 與 references 全形標點、無破折號（未過：%s）" % "、".join(bad_docs), not bad_docs)
tmpf = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8")
tmpf.write("這是錯的,半形逗號\n還有破折號——不行\n")
tmpf.close()
check("髒文字會被擋", subprocess.run(PUNCT + [tmpf.name], capture_output=True).returncode == 1)
os.unlink(tmpf.name)

# ------------------------------------------------------------ 8) 畫面掃描（需要 playwright）
print("8) 畫面掃描")
_DOM_OK = bootstrap._have_py("playwright")
if _DOM_OK:
    out = tempfile.mkdtemp(prefix="drl-scan-")
    SCAN_CMD = [sys.executable, os.path.join(SCRIPTS, "scan.py"), "--no-install"]
    rs = subprocess.run(SCAN_CMD + ["--file", slop, "--out", os.path.join(out, "slop")], capture_output=True, text=True)
    rc = subprocess.run(SCAN_CMD + ["--file", clean, "--out", os.path.join(out, "clean")], capture_output=True, text=True)
    sj = json.load(open(os.path.join(out, "slop", "scan.json"), encoding="utf-8"))
    cj = json.load(open(os.path.join(out, "clean", "scan.json"), encoding="utf-8"))
    got = {h["rule"] for h in sj["hits"]}
    want = {"A1", "A2", "A3", "B1", "B2", "C1", "C2", "C3", "C4", "C5", "C9", "D1", "D2", "E1", "E3"}
    check("slop 畫面掃描退出碼 1", rs.returncode == 1)
    check("slop 命中數合併後不超過 32 筆（實得 %d）" % len(sj["hits"]), len(sj["hits"]) <= 32)
    check("slop 命中關鍵規則（缺：%s）" % "、".join(sorted(want - got)), want <= got)
    check("slop 有畫面層且有 4 張截圖", sj["layers"]["dom"] and len(sj["screenshots"]) == 4)
    check("clean 零命中、退出碼 0（命中：%s）" % "、".join(h["rule"] for h in cj["hits"]), rc.returncode == 0 and cj["hits"] == [])
    shutil.rmtree(out, ignore_errors=True)
else:
    print("  [SKIP] 沒有 playwright，畫面掃描測試略過")


def test_all_checks_passed():
    """pytest 收集點：上方檢查已於 import 時執行，這裡守門總結果。"""
    assert FAIL == 0, "%d failed（詳見上方 [FAIL] 列）" % FAIL


if __name__ == "__main__":
    print("\n結果：%d passed, %d failed" % (PASS, FAIL))
    sys.exit(0 if FAIL == 0 else 1)
