# 課題深掘り階層 (Depth Framework)

ユーザー指摘に基づく自己判定軸の明文化:
> 「課題が十分に詳細にできていて、手法が課題を深掘りしないと出てこない課題なら同じようなテーマでも十分新規性がある」

これを運用可能にするには **「どこまで深掘りしたか」を測る scale** が必要。

---

## 1. 深掘り 8 レベル

| Level | 名称 | 答えるべき問い | 失敗の典型 |
|---|---|---|---|
| **L1** | **現象の特定** | 何が観測されるか? どんな事象が disagreeable なのか? | 抽象スローガンだけ ("HC は不確実") |
| **L2** | **機構の説明** | なぜその現象が起こる? 物理 / 数学的に何が効いている? | "そういうものだから" で止まる |
| **L3** | **当事者特定** | 誰がこの現象に困っている? 困らない人は誰? | 仮想ユーザーで終わる、実 stakeholder 不在 |
| **L4** | **決定文脈** | その当事者は具体的に何を判断する必要がある? いつ? | 「知見が得られる」止まり、判断に接続しない |
| **L5** | **誤差の非対称コスト** | 判断を間違えると何が起きる? 過剰側と不足側のコストは同じ? 違う? | 単純な精度競争 |
| **L6** | **制約の明示化** | この判断に使える資源 / 時間 / 情報は何が、何が使えない? | 制約を書かず「何でもいい」 |
| **L7** | **手法の強制力** | L1〜L6 を全部満たす方法は何通りある? 1 通りなら強い、複数なら制約が緩い | 「機械学習を使います」と言って終わる |
| **L8** | **検証基準の操作可能化** | どんな evidence が出れば当事者が行動を変えるか? 数値・図表の形式まで | "性能を評価する" で具体性なし |

### 深掘りスコア

| 達成 Level | 解釈 |
|---|---|
| L1-2 のみ | 表層問題 (スローガン)。手法の novelty 主張不可 |
| L3 まで | 関心はあるが decision に接続せず。survey paper 止まり |
| L4-5 まで | 応用研究の入口。method を選ぶ余地が広く、surface 類似研究と区別困難 |
| L6 まで | 制約が手法選択を絞る。**ここから novelty 主張が可能** (= ユーザー基準) |
| L7-8 まで | 手法が課題から **強制** される。surface 類似があっても positioning 可能 |

---

## 2. 各 Level で書くべき具体内容 (template)

### L1 現象の特定
- 観測した事象 (測定値 / 図 / 数値例)
- 「ふつうの予想からずれている」点を 1 行で

### L2 機構の説明
- 物理 / 数学の用語で機構を 2-3 文
- 「なぜ A→B が起こるか」を式 or 直感で

### L3 当事者特定
- 名前付きで 2-3 種の stakeholder
- 「この人がこれで困っている」具体例 (= 動詞で書く)
- 困らない / 関係ない人も書く (反面)

### L4 決定文脈
- 当事者が直面する binary / discrete choice
- いつ / どこで / なんのために決めるか

### L5 誤差非対称コスト
- 過剰側エラー (false positive) と不足側エラー (false negative) のコスト比較
- 単位 (時間 / 金 / 政策影響) で

### L6 制約
- 計算予算
- 利用可能データ
- "使えないもの" を明示
- 倫理 / 規制 / 商習慣

### L7 手法の強制力
- L1〜L6 全部を満たす method 候補を 3 つ列挙
- 各候補がどの制約を満たさないか (= 不採用理由)
- 残った 1 つが採択 method

### L8 検証基準
- 出力する図・表の形式 (header まで)
- 当事者が「これなら行動を変える / 変えない」と言う数値の閾値
- p-value / 効果量 / 信頼区間の形式

---

## 3. ユーザー基準による Novelty 判定の条件

> 「課題が十分に詳細にできていて、手法が課題を深掘りしないと出てこない課題」

これを上記 Level scale で書き直す:

> **L7 まで到達していて、かつ L7 で残った 1 method が L1〜L6 の制約 (特に L5 cost 非対称、L6 計算制約、L8 検証基準) のいずれかを緩めると別の method に collapse するなら、その問題-手法 pair は novelty を主張できる。**

### この基準で否定される候補の例

| 候補 | 理由 |
|---|---|
| 「HC を Sobol で分解」だけ | L4-5 が空欄、L6 緩い → 同型の method が 5 通り出てくる |
| 「GNN で HC 推定」だけ | L1-3 で止まり、L4 (誰が GNN をいつ使う?) が薄い |

### この基準で許容される候補の例

| 候補 | 理由 |
|---|---|
| 候補 #1 (try10) — phase transition | 後述、L8 まで到達確認 |

---

## 4. 候補 #1 の Level 別記述

### L1 現象の特定
**観測**: try9 の results/raw_results.json にて、CIGRE MV @ load_level=1.0 の 256 random PV placement で **violation_ratio が全 256 件で 0.600**、stdev=0.000。一方、CIGRE LV @ load_level=1.0 では 0.382-0.548 mean、stdev≈0.12 で realisation 間で大きく異なる。

**ふつうの予想とのズレ**: 「stochastic HCA は分散を返す」前提が、ある regime では崩れる。

### L2 機構の説明
高負荷下では base voltages の下限 violation 集合が PV 配置に **不変**:

- 9/15 buses が PV 投入前に既に < 0.94 pu (R·P_load / V_base ≈ 0.06 pu drop)
- PV 容量 50-500 kW の電圧上昇 ΔV_PV ≈ R·P_pv / V_base ≈ 0.005 pu (上昇方向)
- |ΔV_PV| << |V_base - 0.94| なので置く位置を変えても 9 buses は変わらず違反

**スカラー式**: stdev[V_b]_placement → 0 if E[V_b] - threshold > sup_placement(ΔV_PV) for all b ∈ 違反集合。

### L3 当事者特定
- **配電事業者の HCA レビュアー**: 受領した HCA レポートが 5 MW と書いてあるとき「この数字は brittle なのか robust なのか」を判定したい
- **スタートアップ HCA SaaS 事業者**: 1000 customer feeder を毎日処理。常に N=1000 stochastic を回すと予算超過
- **困らない人**: deterministic load-flow しかしない伝統的計画者 (本問題に該当しない)

### L4 決定文脈
事業者が新規 feeder を受け取ったとき、**HCA を回す前に**:

> **決定**: この feeder で stochastic HCA (N=500) を回すべきか、deterministic load-flow (N=1) で十分か?

タイミング: feeder の構成情報 (topology + base load 想定) を入手した直後、power flow を 1 回も実行する前。

### L5 誤差非対称コスト

| 真値 | 予測 | 誤差種 | コスト |
|---|---|---|---|
| 分散有り (stochastic 必要) | "deterministic で十分" | False Negative | **重要分散見逃し → policy 誤判断** (例: 規制当局への報告で誤った robust 性主張、訴訟リスク) |
| 分散なし (load-dominated) | "stochastic 必要" | False Positive | 計算 N=500 倍 waste (~分単位 / feeder × 1000 feeder/day = 2-3 日 / 日 → 累積し infrastructure scale 問題) |

→ FN コスト >> FP コスト (規制 / 訴訟 vs 計算予算)。**recall@precision=0.9 重視**の損失関数を採用すべき。

### L6 制約

| 制約 | 内容 |
|---|---|
| 計算予算 | 判定そのものは **power flow 0 回** で行う。1 回でも回したら "じゃ最初から stochastic HCA でいい" になる |
| データ | feeder の topology graph + 推定 base load profile のみ。実測電圧時系列は使えない (ない) |
| 解釈性 | linear / logistic regression / decision tree など、規格委員会が読める形 |
| 計算時間 | 判定 ≤ 1 秒 / feeder (実用要件) |
| 倫理 | 過小評価 (FN) を回避する操作可能なメカニズムが必要 (= 損失関数の調整) |

### L7 手法の強制力 (3 候補から 1 つに絞る)

| 候補 method | L1〜L6 のどれを破る? | 採否 |
|---|---|---|
| (a) GNN with electrical features (run pp once) | L6 計算予算 (= power flow 0 回) を破る | 不採用 |
| (b) Surrogate model trained on past stochastic HCA results | L6 解釈性 (black box) を破る | 不採用 |
| (c) **Logistic regression on power-flow-free features (analytic ΔV, topology metrics)** | 全制約 OK | **採用** |

→ method が **唯一**に絞られる。これが課題深掘りによる強制。

### L8 検証基準

- **出力**: confusion matrix at CV threshold = 0.1
  - rows: true label (CV ≥ 0.1 / CV < 0.1)
  - cols: predicted
- **配電事業者が行動を変える条件**: recall (true CV ≥ 0.1 を逃さない率) ≥ 0.9 かつ precision ≥ 0.6 (FP コストは高くないが ≥ 0.6 を欲しい)
- **leave-one-feeder-out CV 検証**: K 個の feeder を training、1 個を hold-out。順番に全 K feeder を hold-out にして K runs
- **feature importance**: top-3 feature の係数 + 物理解釈
- **失敗モード分析**: misclassify した feeder/load を一覧表示

---

## 5. Level 別の自己採点

| Level | 候補 #1 達成 | 採点根拠 |
|---|---|---|
| L1 | ✅ | try9 raw_results.json の具体数値で示す |
| L2 | ✅ | スカラー式で機構を説明 |
| L3 | ✅ | 3 つの stakeholder を動詞付きで具体化、関係ない人も明示 |
| L4 | ✅ | binary decision、タイミング明示 |
| L5 | ✅ | FN/FP の単位を時間 / 政策で書き分け、recall 重視 |
| L6 | ✅ | "power flow 0 回" を明示、解釈性 / 時間 / 倫理 全列挙 |
| L7 | ✅ | 3 候補を制約で絞り 1 つに **強制** |
| L8 | ✅ | 図表 schema、行動変更の数値閾値 |

→ **L8 達成** = ユーザー基準で novelty 主張可能。

---

## 6. 「他の候補も同様に深掘りすれば novelty 出るのでは」という反論

その通り。各候補について同じ Level 1〜8 を埋められれば novelty 主張可能。
ただし **本 try10 のスコープでは候補 #1 のみ** に絞る (1 セッション 1 候補)。残り候補の深掘りは PO 判断で並行 / 順次。

---

## 7. この framework を `mvp_review_policy.md` に取り込むべきか?

私の推奨: ✅ §2.5.3 Novelty Gate に **「深掘り Level チェックリスト」** を追加する PR を別途出す。
ただし実施は PO 承認後。本 try10 の中では既存 Novelty Gate を本 framework で **補完** して使う。
