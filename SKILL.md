---
name: tailored
description: 讓 AI 做出量身打造、好看又好用、不像 AI 做的介面。適用網站、網頁應用、後台與工作台、儀表板、手機 App 與 PWA，以及 AI 產品（模型平台、聊天助理、agent 工作台）。流程：查事實與訪談寫 PRODUCT.md，做 2 到 3 個看得到的方向讓使用者挑、寫 DESIGN.md，照品味基本功實作，四種寬度截圖、AI 味掃描、獨立審查與程式閘門，修到過關，實際操作驗證後交付。使用者說「設計」「改版」「做一個頁面、後台或 App」「檢查這頁設計」「有沒有 AI 味」「幫我審查 UI」「這頁很醜或很普通」，或剛用 AI 做完前端畫面要驗收時使用。不適用：純後端、只寫文案、簡報與文件排版、logo 與插畫。
---

# Tailored（量身打造）

AI 做的畫面普通，是因為每個決定都選了最常見的那個。目標水準依畫面類型分兩種，但都不是「乾淨、不出錯」就好：**品牌與體驗網站對標 Awwwards 的當日最佳網站；工作系統（公司內部系統、後台、ERP、AI 平台）對標 Linear、Stripe 這類頂尖產品介面，美感來自精準的細節，不是表演**（`references/systems.md`）。兩種都要通過 `references/details.md` 的細節檢查。這個 skill 把有經驗設計師的做法變成固定流程：**先搞清楚產品與使用者，做出幾個看得到的方向讓使用者挑，照基本功實作，再由獨立審查者對照原則與規則檢查，修到過關，最後實際操作確認能用。**

下文的 `<skill>` 指本 skill 的資料夾。沒有 `python3` 的環境改用 `python`。

## 先判斷模式

| 模式 | 什麼時候用 | 走哪些步驟 |
|---|---|---|
| 完整設計 | 新產品、全面改版、對外門面 | 0、1、2、3、4、5、6 |
| 新畫面 | 已有 PRODUCT.md 與 DESIGN.md，要加一頁或一個功能 | 0、3、4、5、6 |
| 審查 | 已有成品，要檢查或修到過關 | 0、4、5、6 |
| 小修 | 明確的局部修改 | 直接改，截圖確認受影響的地方，再做步驟 6 |

完整設計可能要一小時以上、用掉不少 token；開始前用一句話告訴使用者選了哪個模式、大概多久。明確的局部修改不要強迫重新訪談或重做方向。

## 步驟 0：對焦

1. 判斷畫面類型：網站、工作台與後台、儀表板、手機、桌機工具、AI 產品。讀 `references/platforms.md` 對應的段落；工作台、後台、ERP、AI 平台另外讀 `references/systems.md`；AI 產品另外讀 `references/ai-products.md`。
2. 確認目標：網址、檔案，或專案怎麼跑起來。讀既有的 PRODUCT.md、DESIGN.md 與設計系統，已經決定的事不重來。
3. 建立回合紀錄：

```bash
python3 <skill>/scripts/loop.py init design-review --mode full --target "<網址或檔案>"
```

`--mode` 用 `full`（完整設計）、`lite`（內部工具與後台）或 `review`（審查）。過程檔放在 `design-review/`；PRODUCT.md 與 DESIGN.md 放專案根目錄。

## 步驟 1：產品事實，寫 PRODUCT.md

讀 `references/product.md`。

- 查得到的自己查，不問使用者。
- 只問事實：誰用、在哪裡用、最想完成什麼、有哪些和沒有哪些功能、禁區。一輪最多 5 題，每題附背景與建議答案。
- **不用問答問視覺偏好**（配色、字體、外框），那是步驟 2 用看的選。
- 要接真實系統或資料時，讀 `references/real-data.md`。

## 步驟 2：做出看得到的方向，寫 DESIGN.md

讀 `references/directions.md`。

1. 讀 `references/aesthetics.md`、`references/motion.md`、`references/details.md` 與 `references/art-direction.md`。先寫主題世界表（材質、顏色、字的性格、影像、動詞、細節），動態從「動詞」來，不要每個主題都用同一招。有網路時，依專案類型找 3 到 5 個參考：品牌網站到 Awwwards 對應的類別找得獎作品（第十一節的對照表）；工作系統看 `systems.md` 第七節的產品與設計系統。無頭截圖往下看完六屏，再放大兩倍裁出局部，寫下借什麼。工作系統的方向要來自不同的工作世界（例如公文帳冊、機房儀表），不是同一套版面換顏色。
2. 設計命題一句話，現實隱喻 4 到 6 個，用 `scripts/roll.py` 擲骰選主方向。每個方向寫概念一句話，加上它在畫面上變成哪三件事。
3. 做 2 到 3 個方向：**真的 HTML 畫面**，同一份內容，概念各不相同，完成度要到可以拿去參賽（字體組合、看得見的格線、跟概念相關的影像或線稿、編排過的動態）。主視覺要貫穿整頁，不能只有首屏好看（第十節）。
4. 字體依 `references/typography.md` 的情況表選，用 `templates/type-specimen.html` 排出 2 到 3 組配對、放真實內容；跟方向一起給使用者用看的挑。
5. 用 `templates/compare.html` 放在同一頁比較，確認每個方向都打得開。
6. 只問使用者三件事：最接近哪個、喜歡的那個哪裡不喜歡、其他方向有沒有想借的。原話記進 DESIGN.md。

使用者之後說「再大膽一點」「再安靜一點」這類話時，照 directions.md 的調整指令表轉成具體改法。

## 步驟 3：實作

1. **動手前讀完 `references/craft.md`、`references/details.md`、`references/typography.md`、`references/art-direction.md` 與 `references/antipatterns.md`；工作系統另讀 `references/systems.md`。**
2. 先寫五行設計計畫再寫程式：這頁的主角、色彩 token、字級表、版面草圖、大膽的一處。
3. 每加一個元素都要答得出它在做什麼；答不出就不要加。
4. 數字、客戶名、評價只能用 PRODUCT.md「可證實的數據」裡的；沒有就留「［待補：真實數據］」，絕不編造。
5. 每個按鈕與連結都有真的目的地；還沒做的功能不放入口。
6. 用專案既有的技術與元件，不為了套用這個 skill 換框架或加套件。
7. 完成前做一次「拿掉一個配件」：刪掉一個拿掉後資訊不會變少的元素。

## 步驟 4：審查（每一回合都整套跑）

**4a 開新回合、掃描、截圖**

```bash
python3 <skill>/scripts/loop.py next design-review
python3 <skill>/scripts/scan.py --url http://localhost:3000 --src ./src --widths 1440,1024,768,390 --out design-review/round-1
python3 <skill>/scripts/scan.py --file page.html --widths 1440,1024,768,390 --out design-review/round-1
```

- 掃描命中只是候選，不是判決；退出碼 1 代表有命中要審查者處理。
- 缺 playwright 時會自動安裝。**在公司或共用主機上先問使用者，或加 `--no-install`**；不能開瀏覽器時降級為靜態掃描，截圖改用瀏覽器工具或請使用者提供，並在報告註明。

**4b 兩層獨立審查**

每一回合開一個全新的子代理當審查者，只給它產品事實、截圖、掃描結果與規則，不給設計過程的對話。提示詞用 `loop.py brief design-review` 產生，原封不動交給子代理。沒有子代理時自己審，但只看截圖與事實，reviewer 填 self。細節見 `references/review-rubric.md`。

- 第一層（做對了嗎）：四原則（符合預期、主次分明、克制、量身打造）各打 0 到 3 分，加上三秒測試、換名測試、核心任務測試。錨點見 `references/principles.md`。
- 第二層（有沒有犯已知的錯）：scan.json 每一筆命中都要確認或排除，再補上機器看不到的問題；並對照 craft.md 檢查基本功。

**4c 閘門**

```bash
python3 <skill>/scripts/loop.py gate design-review
```

閘門規則見 `FROZEN.md`：沒有未修的 P0、P1；四原則每項至少 2 分；三項測試全過；掃描命中全部處理；P0、P1 只有使用者能豁免。

| 退出碼 | 意思 | 接下來 |
|---|---|---|
| 0 | 通過 | 步驟 6 |
| 1 | 未通過 | 步驟 5 |
| 2 | 審查檔不完整 | 補齊 review.json 後重跑閘門（不算一回合） |
| 3 | 停下 | 把剩下的問題交給使用者決定 |

## 步驟 5：修正迴圈

**先判斷修補還是重寫。** 第一回合有兩個以上的原則拿 0 分，代表要重寫：照 craft.md 重做計畫，必要時回到步驟 2，不要因為原頁有某個顏色就沿用它。

修補時：

1. 先修 P0，再修 P1。P2 不擋閘門，交給使用者決定。
2. 只修被點名的地方，每項修正對應一個 F 編號，寫進本回合的 `fixes.md`。
3. 優先用刪除解決；修根本原因，不要遮掩。
4. 看 positives，不要破壞做對的地方。
5. finding 跟 PRODUCT.md 或品牌規定衝突時，問使用者；同意豁免才寫 `waiver`。
6. 方向問題先刪後議：先做一輪只刪裝飾、不換方向的修正；問題還在，才停下來建議回到步驟 2。
7. 修完回到步驟 4，整頁重新掃描與審查。

**停止條件**：閘門通過；或自動回合達上限（預設 3 回合）；或同一個擋閘門的問題回歸兩次。後兩種把剩下的問題和可行選項交給使用者，不要在兩個壞狀態之間來回修。

## 步驟 6：實際操作與交付

1. **並排比對**：把自己的截圖跟同類型的 3 個參考並排，照 `aesthetics.md` 第九節逐項比；再用 2 倍截圖裁出導航、按鈕、表格、最小的字四處，照 `details.md` 第八節比細節。任何一項明顯輸就回頭改。
2. **實際操作驗證**：照 review-rubric.md 最後一節，用真的瀏覽器走核心任務；接真實資料的存一筆再讀回；比較頁的每個方向都打開。照 `references/checklist.md` 逐項確認。
3. 報告標點檢查：`python3 <skill>/scripts/validate_punct.py design-review/round-N/report.md`。
4. 閘門通過後不要再改成品；任何修改都要開新回合重審。
5. 交付內容：成品網址或檔案、最後一回合截圖（審查模式附第一回合作為對照）、比較頁、report.md、剩下的 P2 建議，以及實際驗證了什麼、沒驗證什麼。
6. 問使用者滿不滿意，視覺滿意和功能通過分開問。使用者的意見當成新的 finding 或調整指令，開新回合處理；偏好記進 DESIGN.md。

## 使用者不在時（一次做完）

| 原本要問的事 | 保守預設 |
|---|---|
| 產品事實缺漏 | 用推斷繼續，列在 `design-review/decisions.md`；頁面上寫「［待補：…］」，不補造 |
| 選方向 | 仍做 2 到 3 個方向放在比較頁，用主方向繼續完成，交付時請使用者選 |
| 豁免 P0、P1 | 不豁免；修不掉就讓閘門停下 |
| 專案設定、安裝套件 | 不動專案設定只寫建議；公司或共用主機一律 `--no-install` |
| 滿意度 | 交付時列出待確認事項 |

## 能力邊界

- 檢查的是原則、基本功與已知套路，不是審美。通過閘門代表沒有已知的問題，不保證使用者喜歡，所以才要讓使用者看方向挑。
- 掃描器是啟發式的，會誤報也會漏報；文字疊在圖片或漸層上時對比算不準，要看截圖。
- 不做 logo、品牌識別、插畫與 AI 生成圖片。需要圖像時用產品真實畫面、HTML 做的機制演示，或使用者提供的素材。
- 只有截圖、改不到程式碼時，只跑一回合，交付審查報告與改法，不假裝修好了。
- 反模式清單會過期；遇到新套路用四原則判斷，反覆出現的再補進 `scripts/rules.py` 與 antipatterns.md。

## 檔案索引

| 檔案 | 什麼時候讀或用 |
|---|---|
| `references/craft.md` | 品味基本功（底線）：版面、字體、色彩、元件、動效、介面文字 |
| `references/aesthetics.md` | 美感：從八十個得獎作品歸納的原則、主題世界表、並排比對 |
| `references/details.md` | 細節：量了 67 個得獎網站與 17 個產品介面的字距、行高、線、顏色、圓角、動畫，加上放大檢查 |
| `references/systems.md` | 正式系統：公司內部系統、後台、ERP、AI 平台的美感做法與對標對象 |
| `references/typography.md` | 字體選用：可用的繁體中文字體、依情況選字、中西文配對、字重、內網部署 |
| `references/motion.md` | 動態語彙：依主題氣質挑 2 到 3 種動態，以及做法 |
| `references/art-direction.md` | 藝術指導：概念、主視覺貫穿整頁、依類型找參考 |
| `references/platforms.md` | 網站、工作台、儀表板、手機、桌機的骨架。步驟 0 |
| `references/ai-products.md` | 模型平台、聊天、agent、金鑰與用量的畫面。AI 產品必讀 |
| `references/product.md` | 訪談原則、問題庫、PRODUCT.md 模板。步驟 1 |
| `references/directions.md` | 命題、隱喻、擲骰、做方向、調整指令、DESIGN.md 模板。步驟 2 |
| `references/real-data.md` | 真實流程、資料、翻譯與權限的界線 |
| `references/principles.md` | 四原則的檢查問題、評分錨點與改法 |
| `references/antipatterns.md` | AI 味規則表 |
| `references/review-rubric.md` | 審查提示詞、三項測試、review.json 格式、實際操作驗證 |
| `references/checklist.md` | 交付前檢查清單 |
| `references/lessons.md` | 規則背後的真實事故 |
| `references/sources.md` | 來源與取捨 |
| `templates/` | PRODUCT.md、DESIGN.md、方向比較頁、字體樣張 |
| `scripts/scan.py`、`loop.py`、`roll.py`、`rules.py`、`validate_punct.py` | 掃描與截圖、回合與閘門、擲骰、規則表、標點檢查 |
| `FROZEN.md` | 閘門與規則編號的凍結紀錄 |
