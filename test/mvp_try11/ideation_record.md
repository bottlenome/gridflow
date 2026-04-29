# try11 Phase 0.5 — アイデア創出記録

実施: 2026-04-29
準拠: `docs/mvp_review_policy.md` §2.5 (Rules 1-9)
方針: try10 phyllotactic charging が **Rule 9 v1 (単一遠隔ドメインのワンショット移植)** で実験後に invariant 不一致を発見した教訓を踏まえ、try11 では **Rule 9 v2** (≥3 候補 + invariant 検査 + 機械的脱落) を最初から適用する。

---

## 0. try10 から引き継ぐ教訓

| try10 の失敗 | try11 で守るルール |
|---|---|
| Phyllotactic 1 個だけ採用 (step 5 skip) | ≥3 候補を並列抽象化 |
| 表層 invariant ("non-resonance") のみ確認 (step 6 skip) | 元ドメイン暗黙前提を全て列挙 |
| 実験後に MILP 比 6% 劣を発見 | 実験前に invariant 検査で予測脱落 |

---

## 1. Rule 7 — 乱数アンカリング

**目的**: AI の「無難な答えに収束する」傾向を断つために、起点を意図的に **乱数で選ぶ**。

### 1.1 乱数列の生成

頭の中で 10 個の浮動小数を順に思い浮かべる (transparent に記録):

```
0.7234, 0.1156, 0.4498, 0.9012, 0.0034,
0.6781, 0.3325, 0.8807, 0.2463, 0.5519
```

### 1.2 アンカー先 domain pool (15 個、power system から遠いもの)

| # | 領域 |
|---|---|
| 1 | Glaciology (氷河流動) |
| 2 | Cetacean acoustics (鯨歌) |
| 3 | Origami mathematics (折紙数学) |
| 4 | Mycology (菌類学) |
| 5 | Hieroglyphic decipherment (象形文字解読) |
| 6 | Tide prediction (潮汐予測) |
| 7 | Kabuki theater conventions (歌舞伎演技規範) |
| 8 | Wave-particle duality (波動粒子二重性) |
| 9 | Pollen morphology (花粉形態学) |
| 10 | Cardiac rhythm (心臓拍動律) |
| 11 | Sundial design (日時計設計) |
| 12 | Calligraphy stroke order (書道筆順) |
| 13 | Beekeeping management (養蜂学) |
| 14 | Lithic technology (石器剥離) |
| 15 | Bird migration navigation (鳥類渡航) |

### 1.3 乱数 → アンカー写像

`floor(rand × 15) + 1` で 3 個選ぶ:

| 乱数 | 計算 | 選択された anchor |
|---|---|---|
| 0.7234 | floor(10.85) + 1 = 11 | **Sundial design** |
| 0.1156 | floor(1.73) + 1 = 2 | **Cetacean acoustics** |
| 0.4498 | floor(6.74) + 1 = 7 | **Kabuki theater** |

これら 3 つは Rule 9 v2 step 5 の **遠隔候補プール** の seed として使用する。
(Rule 8 で問題を深掘りした後、追加候補を投入する)

### 1.4 アンカー解説 (transparent)

| Anchor | 中核機構 (この時点での理解) |
|---|---|
| Sundial | 局所の太陽角だけで時刻を読む。**観測者間の通信ゼロ**で全員一致 |
| Cetacean acoustics | 海中で **数十秒〜数分の遅延を伴う** 長距離音響通信。歌の階層構造で identity 共有 |
| Kabuki theater | 役者間の発話タイミングが **見得 (キメポーズ)** で同期。台詞を待つのでなく型で同期 |

3 つに共通する性質: **遅延 / 通信制約があっても協調が成立**。これが try11 の問題深掘りで重要な軸になる予感がある (Rule 8 で確認)。

---
