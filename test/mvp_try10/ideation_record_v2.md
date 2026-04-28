# try10 ideation v2 — 課題の深掘りによる新規性判定

実施: 2026-04-28 (v1 から)
動機: ユーザー指摘 — 「課題が十分に詳細にできていて、手法が課題を深掘りしないと出てこない課題なら同じようなテーマでも十分新規性がある」

v1 (`ideation_record.md`) では Novelty Gate #2 (先行文献) を「未検索だから判定不能」として停止した。これは判断軸として誤り。**新規性は先行有無ではなく、課題が必要な解像度で記述されているかで決まる**。 v2 ではこの軸で候補 #1 (stochasticity collapse) を深掘りする。

---

## 1. 課題の深掘り (Dig 1〜8)

### Dig 1 (起点)
HC は stochastic factor (PV 配置) に依存する分散を持つ。

### Dig 2 (try9 の経験)
try9 で **CIGRE MV @ load=1.0 で 256 全 random placement が violation_ratio = 0.600 (stdev=0.000)** を観測。これは「stochastic HCA を回しても情報がない領域」が存在することを実証。

### Dig 3 (現象の物理)
高負荷下では base voltages の下限 violation 集合が PV 配置に **不変** になる。理由:
- 9/15 buses が PV 投入前に既に < 0.94 pu
- PV 容量 50-500 kW の電圧上昇は < 0.005 pu (R·P / V_base 概算)
- → 違反集合 (= 9 buses) が変わらない

### Dig 4 (実務上の決定問題)
配電事業者・研究者は **HCA の手法選択** を直面する:

| 選択 | 計算コスト | 取得情報 |
|---|---|---|
| Stochastic HCA | N=500-1000 simulation (~分) | placement 不確実性込みの分布 |
| Deterministic HCA | 1 simulation (~ミリ秒) | base + worst case の単一値 |

現状はこの選択が **慣習** で決まる:
- "Stochastic 信奉派": 常に N=1000 → load-dominated regime で **計算 1000 倍 waste**
- "Deterministic 派": 常に 1 → placement-dominated regime で **重要分散を見逃し** policy 誤判断

### Dig 5 (新たな問い)
> 「与えられた feeder + load profile で、stochastic HCA が **意味のある分散を返すか** を、power flow を 1 回も走らせずに事前判定できるか?」

これは「新しい metric 提案」でも「新しい sensitivity 手法」でもなく、**手法選択の事前判定** という別カテゴリの問題。

### Dig 6 (cost asymmetry)
Decision の error cost は非対称:

| 真値 | 予測 | 損失 |
|---|---|---|
| stochastic 必要 | "deterministic でいい" と誤判定 | 重要分散見逃し → policy 誤判断 (高コスト) |
| deterministic で十分 | "stochastic 必要" と誤判定 | 計算 N 倍 waste (低コスト) |

→ **safety-critical な false negative を抑える** 損失関数が必要。precision より recall を重視。

### Dig 7 (制約: 特徴量は power flow を走らせない)
予測器が power flow を要求するなら、本末転倒 (= だったら最初から stochastic 走らせればいい)。

許容される特徴量:
- **トポロジカル**: 各 bus から source までの抵抗距離、eigenvector centrality、network diameter
- **基底負荷由来 (analytic)**: closed-form の最悪パス電圧降下 ΔV_max = (R·P + X·Q) / V_base ─ 1 線形計算で済む
- **集約量**: total load / total line capacity、最大負荷集中度
- **NG**: 任意の数値 power flow 結果

### Dig 8 (validation criterion)
- K 個の標準 feeder で訓練、M 個の hold-out で検査
- 評価: confusion matrix at CV threshold = 0.1、PR-AUC、recall@precision=0.9
- **解釈性**: feature importance を出して「どの feeder 属性が予測の主要因か」を抽出
- これがあれば **practitioner の判断ルール** が抽出できる

---

## 2. 課題からしか出てこない手法

上記 Dig 1〜8 の結果として **唯一**導かれる手法:

> **K 個の標準配電 feeder × Q 個の load level × N 個の placement realisation で Stochasticity-Collapse Threshold (SCT) を構築し、CV(violation_ratio) ≥ 0.1 を「stochastic HCA が必要」と定義した binary label を取る。Power-flow-free な feeder/load 特徴量からこの label を予測する分類器を訓練・hold-out 検証し、配電事業者の HCA 手法選択ルールを抽出する。**

この方法が **課題の深掘りなしには出てこない**理由:

| Dig | この方法に効いた制約 |
|---|---|
| 2 | stdev=0 regime の存在 ─ 観測なしには問題自体が成立しない |
| 4 | 「method selection」という枠 ─ metric/sensitivity の枠では出てこない |
| 6 | 損失非対称性 ─ 単純な regression では捕えられない (recall 重視) |
| 7 | "no power flow" 制約 ─ 既存の "Sobol on HCA" / "GNN for HCA" 系では緩い制約 |
| 8 | hold-out + feature importance ─ "fit on one feeder" 系では出ない |

**特に Dig 7 は決定的**: 既存の HCA 関連 ML 手法 (GNN for power flow, surrogate models) は「power flow を高速化 / 代替する」のが目的。本手法は「power flow を **走らせるべきか否か** を決める」のが目的。これは別カテゴリの問題で、別カテゴリの制約 (no power flow at decision time) を持ち、別カテゴリの method (cheap classifier on cheap features) を要求する。

---

## 3. ユーザー判定基準による新規性 self-judge

> **基準** (ユーザー曰く): 「課題が十分に詳細にできていて、手法が課題を深掘りしないと出てこない課題なら同じようなテーマでも十分新規性がある」

| 観点 | 評価 |
|---|---|
| 課題の解像度 | ✅ Dig 1〜8 で 8 段階深掘り。表層 ("HC stochastic") から実務 decision、損失非対称、計算制約、検証基準まで一貫した物語 |
| 手法の課題依存性 | ✅ Dig 7 (no power flow) が緩いと "Sobol on HCA" や "GNN for HCA" に collapse する。本手法は Dig 7 に固有 |
| 似ているテーマでの差分 | ✅ "HCA + ML" 領域は surrogate / accelerator 系。本手法は **method-choice classifier** で射程が違う。たとえ surface 類似手法があっても問題定義が異なる |

→ **新規性あり** と self-judge できる (= ユーザー基準による)。

文献検索による確証は依然欠けるが、課題-手法の coupling が明示されていれば、仮に類似研究が出てきても「我々の問題定義はこう、彼らの問題定義はこう、ここが違う」と即座に positioning できる。

---

## 4. v1 で挙げた他候補の再評価

同じ基準で再評価:

| 候補 | Dig 適用後 | 再評価 |
|---|---|---|
| #5 Topology predictor for HC | 課題深掘り = 「power flow が高い場面で代理推定したい」 → **代理推定 framework に collapse** | 既存と区別できない (= GNN for HCA と射程が同じ) |
| #9 Multi-DER interaction | 課題深掘り = 「DER class 同時導入時の violation 寄与を分解したい」 → 薬学 Loewe additivity の直接転用 | 課題具体化次第で新規性 plausible だが本 try で 2 候補同時推進は scope outside |
| #1 Phase transition | 上記 ✅ | **採用** |

---

## 5. 結論

**try10 は候補 #1 で実験フェーズに進む。**

v1 の保留判断は「文献検索なしには決められない」だったが、ユーザー指摘により **「課題深掘りによる手法強制力」を新規性根拠に採用** することに方針変更。問題-手法の coupling が明示されているため、surface-level の類似研究があっても positioning 可能。

実験設計は v1 §9 を継承しつつ、本 v2 の Dig 5〜8 制約を反映:

1. K = 7+ の標準配電 feeder (CIGRE LV/MV + Kerber × 4 + Dickert)
2. Q = 7 load levels (0.1, 0.3, 0.5, 0.7, 0.9, 1.0, 1.1)
3. N = 50 random PV placements per (feeder, load) cell
4. Total = 7 feeder × 7 load × 50 = 2450 power flow runs (n ≥ 1000 ✅)
5. Per cell の CV(violation_ratio) → SCT 判定 (≥ 0.1 = stochastic-needed)
6. Power-flow-free 特徴量を計算 (Dig 7)
7. 分類器訓練 (logistic regression、解釈性のため線形)
8. Leave-one-feeder-out cross validation
9. Feature importance + actionable rule extraction

Phase 1 実装に進む。
