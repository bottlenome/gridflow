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

> **注**: 採用問題が決定した後に Rule 8 を進めた結果、anchor の核軸は問題の真の難所 (= 重尾的バースト離脱) と部分的にしか合わなかった。Rule 9 v2 で **追加 anchor** (バースト排出系の自然現象) を投入する。

---

## 2. 採用問題 (Phase 0 → MVP 問題候補プール参照)

`docs/mvp_problem_candidates.md` の **候補 2: VPP の補助サービス提供 (機器流出入 churn ロバスト性)** を採用。

### 2.1 問題の表層 (one-paragraph)

仮想発電所 (VPP) は数百〜数千の小規模 DER (EV、住宅蓄電池、エコキュート) を束ね、系統運用者に補助サービス (周波数調整 5 MW / 30 秒等) を契約供給する。問題はメンバー機器が常時入れ替わる (churn) こと。独立 1 台の離脱は集約 SLA で吸収できるが、**バースト同時離脱** (夕方通勤・厳冬朝・市場価格 spike 等) で SLA 違反 → ペナルティ発生。

### 2.2 既存対処の限界

| 方式 | 限界 |
|---|---|
| 静的予備容量 (常時 20-30% 過剰契約) | 余分機器への報酬コスト膨大 |
| 確率的計画 (churn を Markov モデル化) | バースト分布が **重尾 (heavy-tailed)** で平均ベースモデルが外れる |
| 強化学習動的補充 | ブラックボックス、SLA 保証なし、契約交渉に使えない |

---

## 3. Rule 8 — 課題の深掘り (S0 → S8)

| Step | 課題の表現 |
|---|---|
| **S0** | 「VPP の SLA 達成」 |
| **S1** | 集約 SLA (5MW/30s 等) を満たすには、pool 内の active DER の合計出力が常に >= 契約量 |
| **S2** | active DER 数は churn (流出入) で変動。平均的な churn rate なら確率的に対処可能 |
| **S3** | 実 trace では離脱が **時間相関** を持つ: 夕方 EV 出発、厳冬朝の電気給湯機自動運転、市場価格 spike の応動 |
| **S4** | 同期離脱 (cluster) は **共通の外部トリガー** に駆動される: ① 時刻 (commute, dinner cooking)、② 気象 (cold snap)、③ 市場 (price signal)、④ 通信障害 |
| **S5** | バースト時、pool 内 N 機器が秒〜分単位で同時離脱。残存 active DER だけで SLA 維持不能 → 即補充が要 |
| **S6** | 補充候補 (= **standby DER**) は契約上 active 集合の外側に存在。問題は: standby 集合をどう設計し、いつ動員するか。**設計 = 静的問題、動員 = 動的問題** に分割 |
| **S7** | standby 設計の鍵: standby 集合が active 集合と **同じトリガーを共有しない** こと。共有していれば一緒に離脱して補充に間に合わない |
| **S8** | ⇒ **「重尾 burst churn を駆動する外部トリガーに対して、standby 集合を *trigger-orthogonal* に設計する portfolio 問題」** = 解くべき問題の核 |

### 3.1 S8 が「課題深掘りなしには出てこない」根拠

| Dig | この最終形に効いた制約 |
|---|---|
| S3 | 離脱の時間相関 ─ i.i.d. 仮定では出ない |
| S4 | トリガーの分類 ─ 「churn = 外生 driver の relat」と捉える視座 |
| S6 | 設計と動員の分離 ─ どちらか単独では本質を捉えない |
| S7 | トリガー orthogonality ─ 「相関」でなく「**因果トリガー独立性**」を要求 |

**特に S7 が決定的**: 既存 portfolio 系手法 (correlation matrix ベースの DER 配分) は **相関統計** で対処する。本問題は「相関」ではなく「**共通因果ドライバー**」が問題なので、causal characterization が要る。

---

