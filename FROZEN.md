# 凍結紀錄

## v1.0｜2026-10-04｜已鎖定

- **GATE_V1**（`scripts/loop.py`）：四原則每項至少 2 分（滿分 3）；三項測試（three_second、name_swap、core_task）全過；P0、P1 未修即不通過；自動回合上限 3；同一問題回歸 2 次即停下。
- **閘門退出碼**：0 通過、1 未通過、2 審查檔不完整、3 停下交給使用者。
- **P0／P1 豁免權**：只有使用者（`waiver.by == "user"`）。
- **規則編號**（`scripts/rules.py`，RULESET 1.0）：A1 到 A5、B1 到 B5、C1 到 C12、D1 到 D5、E1 到 E5。既有編號的意義不得改作他用。
- **review.json 格式 v1**：見 `references/review-rubric.md`。
- 定版檔：`tests/fixtures/slop.html`（應被大量命中）、`tests/fixtures/clean.html`（應零命中），皆由回歸測試守門。

要調整門檻 → 另開 GATE_V2，並在本檔新增一節；不動 GATE_V1。
要新增規則 → 往 RULES 加新編號，升 RULESET 版本（minor）；不改既有編號。

## RULESET 1.1｜2026-10-26

- 新增 C13（AI 主控台預設樣）、D6（介面用語不白話）、E6（中文排版錯誤），三條都是人工判斷，掃描程式不偵測。既有編號與 GATE_V1 未動。
