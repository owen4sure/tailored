# 來源與取捨

Tailored 整理並改寫了下列來源的方法，不是任何上游作品的原版或官方整合；沒有打包上游的程式、資料庫、圖片或品牌資產。授權與權利聲明見 `THIRD_PARTY_NOTICES.md` 與 `NOTICE`。外部工具都不是必要依賴。

## 借了什麼

| 來源 | 授權 | 借用的做法 |
|---|---|---|
| [Matt Pocock／grilling](https://github.com/mattpocock/skills) | MIT | 訪談跟著決策依賴走；事實自己查、決定交給使用者；每題附建議答案 |
| [Leonxlnx／taste-skill](https://github.com/Leonxlnx/taste-skill) | MIT | 先發幾個方向再挑一個；用真的瀏覽器在多種寬度檢查；每輪修最嚴重的問題、設回合上限 |
| [OpenDesign](https://github.com/nexu-io/open-design) | Apache-2.0 | 從需求到設計契約、可操作的原型、實際預覽與修正的流程 |
| [UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | MIT | 可用性與無障礙優先；交付前檢查清單與多種寬度；有安裝時可查它的資料庫當候選 |
| [Anthropic frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design) | Apache-2.0 | 動手前先做設計計畫；大膽只留一處；具體點名常見的 AI 套版；介面文字的寫法 |
| [Impeccable](https://github.com/pbakaus/impeccable) | Apache-2.0 | 產品資訊與視覺系統分開存；改完自動掃描 AI 味；「再大膽一點」「再安靜一點」這類調整指令 |
| 專案擁有者的 design-review-loop | 本專案 | 四原則與評分錨點、AI 味規則表與掃描程式、兩層獨立審查、閘門與回合上限、擲骰選方向（整份合併進本 skill） |
| 擁有者的實際專案回饋（已一般化） | 本專案 | 見 `references/lessons.md` |

## 刻意不繼承的部分

- 不沿用任何來源的固定色票、字體、圓角、陰影、框架或圖示套件。craft.md 裡的數值是可讀性與秩序的起點，不是風格；風格由使用者看過方向後選定。
- 不沿用行銷頁專用的規則到工作台與後台（例如一定要不對稱、禁止等大格子）。
- 不把「看起來真實」解讀成可以編造數據。
- 不依賴安裝整套外部平台。工具存在時用符合任務的部分，不存在就說明替代方式與限制。

## 有裝 UI UX Pro Max 時

定位它的 skill 資料夾，用它的 `scripts/search.py` 查本案的產品類型、單一 UX 問題或實際使用的技術。查到的配色與字體只是候選，要放進方向裡讓使用者用看的選，不能直接鎖定。
