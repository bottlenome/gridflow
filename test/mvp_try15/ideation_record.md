# try15 — Phase 0.5 Ideation Record (mvp_review_policy.md 完全準拠)

実施開始: 2026-04-30 後段
シナリオ: VPP の補助サービス契約 — 機器流出入 churn ロバスト性 (`docs/mvp_problem_candidates.md` 候補 2、try11 から継続採用)
立ち上げ理由: try11→12→13→14 が **policy §2.5.2 Rule 6 (同方向 3 連続で強制転換) に違反**していた事実を try15 立ち上げ時に発見 (`test/mvp_try12/13/14/review_record.md` 末尾参照)。本 cycle で Rule 7 (乱数アンカリング) からやり直す。

---

## 0. 自己診断: なぜ try12-14 が違反だったか

| try | 提案手法 | 直前 try との差 |
|---|---|---|
| try11 | M1 = trigger-orth MILP set-cover | 起点 (適正な ideation) |
| try12 | M9 = M1 + Bayes 制約 1 行追加 | **同 MILP に制約 +1** |
| try13 | M9-grid = M9 + DistFlow 制約 | **同 MILP に制約 +1** |
| try14 | M9-grid-soft = M9-grid を slack 化 | **同 MILP の制約を緩和** |

**4 連続「set-cover MILP に制約族を 1 個ずつ操作」**。Rule 6 が想定する fixation の典型 (policy 例: try5→6→7 = HC curve 統計量を 3 連続)。

---

## 1. Rule 7 (乱数アンカリング) — 本セッションで commit 済み

policy §2.5.2 Rule 7 に従い、**Rule 1 候補生成の前** に anchors を commit する。**ranking や pre-screening をしない (= 一見不毛な anchor も commit)**。

### 1.1 Random integers (8 個、`secrets.randbelow(100)` で取得、再振りなし)

```
[98, 21, 99, 3, 32, 76, 72, 28]
```

### 1.2 Forced association words (8 個、領域横断、辞書から半ば強制で固定 — 後続で正当化しない)

```
sponge, kintsugi, glacier, espresso, parallax, jetlag, marbling, scaffold
```

### 1.3 Forced remote domains (5 個、本問題 = 電力系統 / 配電網 / DER 設計から **意図的に最遠**)

```
1. 古生物学 (paleontology / fossilisation taphonomy)
2. 楽器修復 (luthiery / instrument restoration)
3. 民俗学 (ethnology / folkloristic field-collection methods)
4. 海綿生物学 (poriferan biology / sponge filtration ecology)
5. 製陶 (ceramics / glaze chemistry)
```

**禁止**: 後続で「本当はこの anchor が筋良くて...」と post-hoc rationalisation しない。anchor は単に出発点を **平均から離す** 機能のみ。

---

## 2. Rule 1 (HAI-CDP) — anchors を本問題に「むりやり射影」して **≥ 10 候補** を生成、ranking しない

問題 (try11 から継続): VPP の active pool member が共通因果トリガー (commute / weather / market / comm_fault) で同期離脱、SLA tail 違反のリスク。

各 anchor を **無理やり** 投影して標準的でない候補を作る:

| # | anchor | 投影による candidate (= "むりやり接続") |
|---|---|---|
| 1 | sponge (スポンジの濾過) | **濾過階層型 VPP**: 各 DER に「目の細かさ」を割り当て、trigger 強度ごとに段階的に発動。微小 trigger は粗目層が吸収、大 trigger だけが細目層に到達。階層段差が **時間でなく粒度** で並ぶ |
| 2 | kintsugi (金継ぎ; 破損部を金で接合し美にする) | **破損可視化 standby**: SLA 違反が起きた step を「金継ぎ点」として記録、次回 contract で **その時刻に専用 standby を予約**。違反履歴を asset 化 |
| 3 | glacier (氷河の年層) | **多年層 VPP contract**: 月次でなく **年層構造** で contract を積層、「今年層の active 不足を昨年層 standby が補う」型。time-vintage 直交 |
| 4 | espresso (圧力 vs 抽出) | **圧力依存パケット dispatch**: trigger 発火時の grid-side 圧力 (= ATS 余力) に応じて dispatch 量を 9bar 圧縮的に絞る。常時 dispatch でなく event-locked 圧縮抽出 |
| 5 | parallax (視差) | **二観測所 VPP 設計**: 同 DER pool を 2 つの time horizon (= 短/長) で並列に SLA 契約、視差 (= 短長で違う violation pattern) から trigger 軸を **データ駆動で再推定** |
| 6 | jetlag (時差ぼけの非対称) | **東西 phase 配分**: pool 内 DER を **異なる timezone phase** に割り当て (residential commute は site location dependent)、commute trigger の同期を物理的にずらす |
| 7 | marbling (大理石の脈) | **再帰 fractal active 配置**: pool を 3 層 fractal (active / sub-standby / standby) に再帰分割。各層が次層の trigger 受け持ち、同期同時離脱を 1 / fractal_depth に圧縮 |
| 8 | scaffold (足場の組立順) | **時刻依存組立 standby**: standby を contract 期間内で **組み替え可** にし、active drop 予測時刻の前にだけ集中配備。年契約でなく weekly contract |
| 9 | 古生物学 (taphonomy = 化石化のバイアス) | **観測バイアス補正 churn model**: ACN/Pecan データの観測条件依存性を taphonomy 風に分解、trigger 軸の **観測欠損を補正**して MILP に入力 |
| 10 | 楽器修復 (= 木材の応力史を読む) | **応力履歴ベース DER selection**: 各 DER の過去 churn 履歴を「応力史」として個別評価、active には**応力疲労 score 低い** DER を推奨 |
| 11 | 民俗学 (口伝の field collection) | **オペレータ口伝 trigger 基底**: trigger basis を `commute/weather/market` の固定でなく、**配電事業者オペレータへのインタビュー** で feeder 固有 axis を抽出 (= 物理計測でなく現場知) |
| 12 | 海綿生物学 (sponge は collar cells で粒子径選別) | **粒子径選別 contract**: VPP DER を「容量 cap_j」だけでなく「**応答粒度**」(= 反応速度 × 持続時間) で 2D 評価、burst の **粒度プロファイル** に合わせて選別 |
| 13 | 製陶 (= 釉薬は焼成温度で結晶化、温度カーブが命) | **焼成カーブ contract**: SLA を時刻平均でなく **時刻別 envelope** で契約、特に commute time 帯は厳しく、夜間は緩く。温度プロファイル状の SLA |
| 14 | 数字 99 (= 99 percentile) | **99-th percentile worst-case contract**: SLA を mean でなく 99-th worst step で契約、そのための standby は通常 over-provision でなく **violation-locked dispatch** |
| 15 | 数字 3 (= cube root) | **cube root scaling**: pool 数 N → standby 数 ~ ∛N、trigger 数 K → 対象軸 ~ ∛K。粗 scaling 構造で大規模化に備える |

**確認 (Rule 1 違反監視)**: 候補 1〜15 のうち **MILP set-cover paradigm にすぐ落とせる** のは #2, #4, #8, #14 程度 (= 4/15)。**残り 11 個は MILP 以外の paradigm** を要する → fixation 脱却の証拠。

---

## 3. Rule 2 (Ordinary Persona) — 候補に新 persona でコメント

policy §2.5.2 Rule 2: 電力専門家でなく無関係職業の persona で考える。同候補集合を 3 persona で再評価。

### 3.1 Persona A: 「保険のアクチュアリー」(actuary)

- 候補 #14 (99-th percentile contract): tail risk 評価が core competence、**親和性高い**。アクチュアリー的には「tail VaR contract」に該当
- 候補 #5 (parallax): re-insurance 業界の「複数視点リスク評価」と同型、**親和性中**
- 候補 #9 (taphonomy 観測バイアス): claim history bias 補正の経験あり、**親和性高い**

### 3.2 Persona B: 「農業の品種改良者」(plant breeder)

- 候補 #7 (marbling fractal): 育種学の **層構造 selection** (= 集団 → 系統 → 個体) と同型、**親和性高**
- 候補 #11 (オペレータ口伝): 在来品種の field-collection 方法そのもの、**親和性高**
- 候補 #1 (sponge 濾過階層): 育種学の **多形質階層選抜** に対応、**親和性高**

### 3.3 Persona C: 「都市渋滞研究の交通工学者」

- 候補 #4 (espresso 圧力依存 dispatch): 渋滞圧力 → 信号制御の dynamic gating と同型、**親和性高**
- 候補 #8 (scaffold weekly contract): 工期短縮の crash schedule と同型、**親和性中**
- 候補 #6 (jetlag phase 配分): 渋滞の time-of-day desynchronisation と同型、**親和性高**

**観察**: persona 越しに評価すると **#1/#7/#11 (階層 / 多層構造)** と **#4/#6 (時刻 phase 制御)** が persona-independent に高評価 → 候補集合が persona-anchor に過度に依存していないことを確認。

---

## 4. Rule 3 (CoT 4-step) — 解の前に問題構造を分析

### 4.1 (Step 1) 何と何の間にどんな矛盾があるか

VPP の中心的矛盾:
- **個体最適** (= 各 DER の所有者は自分の都合で離脱) **vs 集団同期** (= 集約 SLA は全 DER 集合の和)
- **平均的可用性高** (= 平時は十分余力) **vs 同期離脱で tail 違反** (= 共通 trigger で一斉離脱)
- **ラベル記述の単純さ** (= type ごとの default exposure) **vs 個体異質性** (= label 不確実、prior dependent)

### 4.2 (Step 2) この問題構造が出現する他分野 ≥ 5

| 分野 | 同型 |
|---|---|
| 銀行 bank run | 個体は預金者意思で引き出し、集団は流動性切れ。共通因果 (= 風説) で同期 |
| 海綿の filtration | 個体細胞は粒子選別、集団は流量、共通因果 (= 潮流) で全停止 |
| 漁網 (gillnet) | 個体糸は耐荷重、集団は破網、共通因果 (= 大物) で全切断 |
| 通信網 BGP | 個体 router は経路、集団は到達性、共通因果 (= mis-config) で同期 down |
| 神経網の synchrony | 個体細胞は発火、集団は同期発火、共通因果 (= rhythm input) で seizure |

### 4.3 (Step 3) 各分野でどう解かれているか

| 分野 | 解法 |
|---|---|
| 銀行 | 預金保険、stress test、tier 別資本要件 (= 健全性に応じ層化) |
| 海綿 | choanocyte の **粒子径選別**、阻害物質発生時に **流路切替** |
| 漁網 | 異なる強度の網を **層別** に並列、破網時に層が分担 |
| 通信網 | route flap damping、AS path diversity、anycast |
| 神経網 | inhibitory interneuron による **negative feedback**、 **cross-frequency coupling** で同期防止 |

### 4.4 (Step 4) 最遠アナロジー選択

VPP との distance 最大は **海綿 (filtration ecology)** と **神経網 (synchrony / inhibition)**。

- 海綿: Rule 1 候補 #1, #12 の起点
- 神経網: 新候補発見 — **#16: inhibitory pool**: pool に "inhibitor DER" を陽に置く (= 通常の active/standby と独立な、active 同期傾向を抑える層)

#16 を Rule 1 候補集合に追加 → **計 16 候補**。

---

## 5. Rule 4 (Extreme User) — 4 名の極端ユーザーから逆算

| extreme user | amplified need |
|---|---|
| 1000 feeder を 1 日で監査する utility のオペレータ | candidate を **MILP-free で 1 sec/feeder 実行可** な手法 (= 候補 #14 99-percentile contract、#11 口伝 axis 抽出が筋良) |
| 10 年 1 feeder だけ追い続ける PhD 学生 | **長期 vintage** が活きる手法 (= 候補 #3 glacier 年層 contract が筋良) |
| ANSI 規格改訂委員会の委員長 | 現行規格 envelope を **再定義** する根拠を要求 (= 候補 #13 焼成カーブ envelope が筋良 = 規格自体を時刻別に refining) |
| DER を一切信用しない保守的計画者 | DER 個別 churn でなく **集約挙動**で安全保証する手法 (= 候補 #7 fractal、#16 inhibitory pool が筋良) |

→ 候補 #3, #11, #13, #14, #16 が extreme-user 観点で立つ。

---

## 6. Rule 5 (TRIZ 妥協なし)

「**コスト最小** AND **tail 違反保証** AND **計算量小**」を **全部同時** に満たす方法は?

- 既存 baseline (B1-B6) は cost-tail trade-off を受容する → 失格
- M1-M9 系は cost-tail-grid 3 軸の 2 軸まで → 失格 (= try11-14 の限界)
- 候補 #14 (99-percentile contract): tail 保証 + 計算量小、cost は dispatch-locked で最小化可能 → **3 軸同時候補**
- 候補 #16 (inhibitory pool): 集団同期同期回避が機構レベル → tail 保証、cost は inhibitor の追加分のみ、計算量は MILP 不要(= analytical) → **3 軸同時候補**

---

## 7. Rule 6 (Fixation 監視) — 自己診断

- try11→14 = MILP 制約族 +1 を 4 連続 (違反検出)
- try15 = 候補 #3 / #14 / #16 のうち、MILP-free なものは #14 (= dispatch-locked) と #16 (= analytical pool composition)
- → **候補 #16 (inhibitory pool) を採用候補とすると MILP set-cover paradigm から確実に脱却**

---

## 8. Rule 8 (S0-S8 課題深掘り連鎖)

候補 #16 (inhibitory pool) で S0-S8 を埋める。

| Step | 内容 |
|---|---|
| S0 | trigger 発火時に pool 内 active が同期離脱、SLA tail 違反。**観察事象**: 5 分間隔で commute (PT 17:00) cluster が発火し、active EVs の availability が 75% → 35% に落ちる、N=200 で 50 機が一斉 drop |
| S1 | データ: ACN-Data 4242 sessions (try11/13 取得済)、kerber_dorf trafo 0.4 MVA、SLA 200 kW、burst 200 kW。**実測**: try11 §8.7.5 で M1 SLA 71% violation、M9-grid で 0% に低減 |
| S2 | 物理: 共通 trigger (commute) が **同種 DER** (residential_ev) の **同時刻離脱** を causally drive。Bernoulli with 共通入力 → covariance > 0 |
| S3 | 困る人: VPP 事業者 (= 規制ペナルティ)、系統運用者 (= reserve 不足)、契約 customer (= 補助 service 失敗)。困らない人: independent DER provider (= aggregator 経由でない事業者) |
| S4 | 決定 timing: 月次 contract design (年に 12 回)、weekly re-contract (= 候補 #8 で柔軟化可) |
| S5 | FN cost (= tail 違反見逃し): 規制ペナルティ + 契約失効、桁で言うと 100x 月次 contract cost。FP cost (= 過剰 standby 契約): 単純 cost 上昇、桁で言うと 1.5x。**FN/FP ratio ~ 60-70** |
| S6 | 使える: ACN/Pecan 等の per-DER log、pandapower simulation、PuLP MILP solver。**使えない** (= 制約): MILP は cost 最小化なので **selection bias** を持つ (try11 N-2)。線形計算量 (= 1000 feeder × 1 day を要求) |
| S7 | S6 制約下で何 method 残る?
- MILP-set-cover 系 (M1-M9-grid): selection bias → 失格
- B1 over-buy: cost-FN trade-off 受容 → 失格 (S5 FN/FP=60 で許容できない)
- B5 causal portfolio: correlation backward-looking → 失格
- **Inhibitory pool 構築 (= 候補 #16)**: 集団同期そのものを mechanism level で抑え、MILP 不要 → 生存
- **99-percentile dispatch-locked (= 候補 #14)**: tail に直接対応、線形計算 → 生存
→ **2 method 残存**。S5 FN/FP 比でさらに絞るには #16 (= 同期回避が機構レベル) が #14 (= dispatch-locked、結局 contract 増) より cost 軸で優位 |
| S8 | stakeholder 行動変化の閾値: VPP 事業者は SLA 違反 < 0.1% で 規制 audit pass。閾値の根拠は ANSI / IEEE 1547 / 日本調整力公募の現行規制値 (= **0.1% は推定、実 stakeholder elicitation 必要**) |

**S6 制約の自己テスト** (policy §2.5.2 Rule 8 失敗パターン回避):

> Q: 「MILP は selection bias を持つ」制約は **なぜ** 必要か?

- 1 段さかのぼり: MILP の cost 最小化は label-flipped outliers を picks する (try11 N-2 で実測)
- 2 段さかのぼり: label noise 5% per axis は pool generation で導入された heterogeneity モデルだが、実 ACN data では 50% posterior という別 mechanism で reproduce される

→ 制約は **後付けでない** (= try11 で empirical 発見済)、根拠 2 段。Rule 8 通過。

---

## 9. Rule 9 v2 (TRIZ 遠隔ドメイン移植 — 並列 ≥ 3 候補 + invariant 検査)

候補 #16 を「inhibitory mechanism による同期回避」と抽象化し、複数遠隔ドメインから並列に該当機構を回収する。

### 9.1 候補 (≥ 3 並列)

| # | 元ドメイン | 機構 (動作原理) | invariant (保存される性質) |
|---|---|---|---|
| α | 神経網 inhibitory interneuron | excitatory pool に対して inhibitory pool (~10-20% of cells) が **負のフィードバック** で同期発火を抑制 | (a) inhibitory delay 充分小、(b) inhibitory threshold が excitatory threshold に近い |
| β | 銀行 stress-test tier-2 capital | 個別預金者の引き出し意思を変えず、集団の流動性層を tier 別に積層して同時不足を回避 | (a) tier 間で response time が階層的、(b) tier-2 cost が tier-1 より高い |
| γ | 海綿 choanocyte の流路切替 | 1 channel 詰まれば隣接 channel が圧力で開く受動的切替、active control 不要 | (a) channel 間の通水抵抗が等しい、(b) 切替に外部 control なし |
| δ | 神経網 cross-frequency coupling | 高周波と低周波振動で位相結合、同位相同期を阻害 | (a) 2 周波数が non-commensurate、(b) coupling 強度が中庸 |
| ε | 物理: damper 並列 | 振動 mass に複数 damper 並列、共振周波数を ban | (a) damper 周波数特性 distinct、(b) total damping 充分 |

### 9.2 invariant 検査 — 移植先 (VPP) で **元ドメインの暗黙前提が成立するか**

| 候補 | VPP target で invariant 成立? |
|---|---|
| α (神経 inhibitory) | (a) **delay 小**: VPP の dispatch lead time は秒級、inhibitory delay 機構の必要 delay (~ms) より大幅に長い → **❌ 不一致**。(b) threshold 近接: 不明、Phase 1 で確認 |
| β (銀行 tier capital) | (a) **tier response time 階層的**: VPP DER は active/standby の 2 層しかなく、tier-2 (= slower) の物理対応物が不在 → **❌ 不一致** |
| γ (海綿 choanocyte) | (a) **通水抵抗等しい**: VPP DER 間の "resistance to dispatch" は cap_j で大きく異なる → **❌ 不一致**。(b) 外部 control なし: VPP は dispatch がまさに external control → **❌ 二重不一致** |
| δ (cross-frequency coupling) | (a) **non-commensurate 2 周波数**: VPP commute と weather は 24h 周期で commensurate (両者とも daily) → **❌ 不一致** |
| **ε (damper 並列)** | (a) **distinct 周波数特性**: DER type ごとに **応答時定数**が大きく異なる (residential_ev 30s, heat_pump 60s, utility_battery 1s) → ✅ **成立**。(b) **total damping 充分**: pool 全 cap = 数 MW で SLA target と同オーダー → ✅ **成立** |

→ **候補 ε (物理 damper 並列) のみ invariant 検査を passed**。残り 4 候補は失格。

### 9.3 採用: 候補 ε = "応答時定数並列" approach

**M10 (仮称): Time-Constant Diversified VPP Pool**

機構: pool を **応答時定数 τ_j で分類**、active pool に τ の **異なる値** を意図的に混在。trigger 発火時:
- short-τ DER (utility_battery, ~1s) は瞬時に立つが容量限定
- mid-τ DER (heat_pump, ~60s) は次に立つ
- long-τ DER (residential_ev, ~30s-数 min) は遅れて立つ

→ **同期 drop も同期 recovery も時定数で散る** = burst tail を時間方向に拡散。MILP 不要、analytical (= τ 分布の畳み込み) で SLA tail を計算可能。

これは try11-14 の **MILP set-cover paradigm から完全に独立した方向**。

---

## 10. Novelty Gate (policy §2.5.3) — 実験前の新規性審査

### 10.1 Novelty Gate 9 観点

| # | 観点 | 判定 |
|---|---|---|
| 1 | 課題が research_landscape の Future Work 由来 | ✅ try11 (候補 2) 継続、`mvp_problem_candidates.md` 記載 |
| 2 | Rule 7 (random anchor) を **候補生成前** に commit | ✅ §1 で commit 済 |
| 3 | Rule 1 で ≥ 10 候補 + ranking なし | ✅ §2 で 16 候補 (Rule 3 step 4 で +1)、ranking なし |
| 4 | Rule 2 の persona 多様性 | ✅ §3 で 3 persona、parameter-independent な高評価候補を識別 |
| 5 | Rule 3 の CoT 4-step (隣接 5 分野 + 最遠 analogy) | ✅ §4 で 5 分野、最遠 = 海綿 / 神経網 |
| 6 | Rule 4 の extreme user 4 名以上 | ✅ §5 で 4 名 |
| 7 | Rule 5 の TRIZ 妥協なし (3 軸同時) | ✅ §6 で 3 軸同時候補を識別 |
| 8 | Rule 8 S0-S8 全埋まり、S6 制約が後付けでない | ✅ §8 で S6 制約根拠 2 段確認 |
| 9 | Rule 9 v2 ≥ 3 候補 + invariant 検査 | ✅ §9 で 5 候補、invariant 検査で 4 候補脱落、1 候補生存 |

→ **Novelty Gate 9/9 通過**。

### 10.2 採用案 (= 単一候補に絞る)

**M10: Time-Constant Diversified VPP Pool** (= response time constant 並列、§9.3)

理由:
- Rule 9 v2 invariant 検査で唯一生存
- Rule 8 S7 で MILP-set-cover と独立
- Rule 6 fixation 脱却の決定的証拠 (= MILP 不要 paradigm)
- Persona 横断で扱える機構
- TRIZ 3 軸 (cost / tail / 計算量) を **MILP 不要で同時** に攻める

---

## 11. Phase 1 への引継 (= implementation_plan.md 別 file)

実装する内容:
- (a) DER pool に response time constant τ_j を追加
- (b) **dispatch dynamics simulator**: trigger 発火 → DER drop の **時間方向** modelling、時定数の畳み込みで tail 評価
- (c) 解析的 SLA tail 計算 (= τ 分布の Laplace 変換、または Monte Carlo)
- (d) 既存 M1/M7/M9-grid との empirical 比較 (= 同 trace 上で M10 vs 既存)

これは別 file (`implementation_plan.md`) で MS-1〜MS-N に展開。

---

## 12. 更新履歴

| 日付 | 内容 |
|---|---|
| 2026-04-30 後段 | 初版。policy 完全準拠で Rule 7 → 1 → 2 → 3 → 4 → 5 → 6 → 8 → 9 v2 を実行、候補 ε (= 応答時定数並列、M10) を採用 |
