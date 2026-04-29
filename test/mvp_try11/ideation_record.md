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

## 4. 既存手法サーベイ

VPP / DER aggregation の reliability 問題に対して、既存研究は概ね 4 系統に分類される。本提案 (S8 = trigger-orthogonal portfolio) との関係を表に整理:

| 系統 | 代表手法 | 代表文献 (調査要) | 強み | 限界 (S8 制約に対して) |
|---|---|---|---|---|
| **A. 確率計画 (Stochastic Programming, SP)** | 二段階 SP、Sample Average Approximation | Conejo 2010, Wang 2019 | シナリオで不確実性を表現 | 重尾分布のシナリオは少数では再現不能 (S3 違反) |
| **B. 分布ロバスト最適化 (DRO)** | Wasserstein-ball DRO, moment-based DRO | Esfahani 2018, Liu 2021 | 過去データへの過適合を回避 | ball 内で **暗黙の i.i.d.**、causal 構造を扱わない (S7 違反) |
| **C. ロバスト最適化 (RO) / Reserve sizing** | Bertsimas-Sim、LOLP-based reserve | Ortega-Vazquez 2009, Zhang 2017 | uncertainty set を陽に設計 | 集合設計に causal 視点なし、保守的 (S6 設計面が薄い) |
| **D. 学習ベース** | DQN, PPO, multi-agent RL | 2018 以降多数 | データ駆動、適応的 | ブラックボックス → SLA 保証なし、新規トリガー OOD (S4 違反) |
| **E. 相関 portfolio** | CVaR-based DER portfolio, factor model | Mathieu 2015 | 過去 correlation で分散 | 相関は **後ろ向き**、未観測トリガーに脆弱 (S7 違反) |
| **F. ゲーム理論 / coalition** | Shapley value DER aggregation | Akhter 2020 | 公平な利益配分 | 運用 reliability に踏み込まず |

### 4.1 提案との差分 (S8 制約での positioning)

**全系統が S7 (causal trigger orthogonality) を扱っていない**。最も近いのは **B (DRO)** だが、Wasserstein ball は確率分布の "近傍" を扱うのみで、**何が変動するか (どの因果ドライバーか)** の構造を入れない。

近年金融分野で **causal portfolio construction** (Lopez de Prado 2019, López de Prado & Lewis 2020) が登場しており、ファクター露出の因果同定を portfolio 構築に組み込む流れがある。本提案はこれを **VPP の文脈に明示的に持ち込む** 初の試み (= 隣接分野の方法論を borrowing する正当な positioning)。

### 4.5 金融 causal portfolio との差分 — 「単純な domain transfer ではない」根拠

**懸念**: もし金融 causal portfolio をそのまま VPP に置けば本提案になるなら、それは単なる domain transfer であり novelty が弱い。

**回答**: 構造が **3 点で異なる**。

#### 差分 (1): 因果関係の所在

| | 金融 causal portfolio | VPP trigger-orthogonal portfolio (本提案) |
|---|---|---|
| 因果グラフのノード | **資産 (assets)** | **DER × 外部トリガー** (二部グラフ) |
| 因果の発見方法 | データから causal discovery (PC アルゴリズム / NOTEARS 等) | **物理 / 契約型から enumerate** (commute, weather, market は既知) |
| 隠れ confounder | 大量に存在 (株価には未観測 driver) | 限定的 (物理的トリガーは枚挙可能) |

→ 金融は「**何が原因か分からないが因果構造を推定する**」問題、VPP は「**因果トリガーは枚挙可能、各 DER の曝露を構造から導く**」問題。**因果同定の困難さの所在が異なる**。

#### 差分 (2): 不確実性の性質

| | 金融 | VPP |
|---|---|---|
| トリガー集合 | open (新規 macro factor が常時出現) | semi-closed (commute / weather / market / comm fault が支配的、新規は稀) |
| トリガー観測可能性 | 部分観測 (factor 取り出しに統計操作要) | **直接観測可能** (時刻・気温・電力市場価格・通信状態は計測機で取得可) |
| 損失の制約形式 | utility / variance / VaR | **SLA tail 確率** (規制と契約で外部固定) |

→ VPP は「観測可能な exogenous トリガーへの曝露」を **物理ベクトル化** する形に翻訳できる。金融はこれが (隠れ confounder が多すぎて) できない。**問題の structural decomposition が VPP 側で固有に成立** する。

#### 差分 (3): ロバスト性保証の達成方法

| | 金融 causal portfolio | VPP 本提案 |
|---|---|---|
| 保証の根拠 | 因果グラフの正しさに依存 (誤りなら保証崩壊) | トリガー基底の **網羅性**に依存 (基底が exhaustive なら保証成立) |
| 新規トリガー耐性 | 因果グラフ再学習が必要 | 既存基底の線形結合として表現可能なら再設計不要 |
| 実装難度 | 因果同定 (高難度) + portfolio 最適化 | 物理曝露ラベリング (中難度) + portfolio 最適化 |

→ 金融版は **データ駆動の弱点** (causal discovery の不安定性) を継承する。VPP 版は **物理事前知識** で causal discovery 部分を bypass できる、これが **転用ではなく独立 contribution** となる根拠。

### 4.6 まとめ: positioning ステートメント

> 金融 causal portfolio は本提案の **概念的祖先** だが、(a) causal graph の所在 (資産間 vs DER × トリガー)、(b) トリガーの observability (隠れ vs 物理計測可能)、(c) 保証の根拠 (グラフ精度 vs 基底網羅性) の 3 点で構造的に異なる。VPP の物理計測可能性と外部トリガーの enumerable 性が、causal discovery を回避した **structural causal portfolio** を可能にする。

### 4.7 Phase 1 比較実験で要する baseline

Phase 1 では以下を baseline として実装する:

| Baseline | 目的 |
|---|---|
| 静的過剰契約 (active の +30%) | 業界実装の lower bound |
| 確率計画 (SP, シナリオ N=200) | 系統 A の代表 |
| Wasserstein DRO (radius τ) | 系統 B の代表 |
| 相関 portfolio (Markowitz on hist. corr.) | 系統 E の代表 |
| **金融 causal portfolio (PC アルゴリズム)** | §4.5 への直接反証 baseline (= "金融転用と何が違うか" を示す) |
| **提案: trigger-orthogonal portfolio** | 本研究 |

評価指標は §後述 (Phase 1 計画) で確定。

---

## 5. Naive NN baseline はなぜ不十分か

「単純にニューラルネットで churn 量を予測して standby 量を反応的に決めればよいのでは?」 という reviewer 的疑問に **事前** に答える。これは Phase 2 査読で確実に問われる質問なので、ideation で論理を確定しておく。

### 5.1 Naive NN の構成 (想定)

```
入力: t 時点での観測ベクトル
       (時刻、気象、市場価格、過去 60 分の churn 履歴、ほか)
出力: t+5 分の churn rate 予測
ロス: MSE または quantile loss
動員: 予測値に応じて standby 動員量を決定
```

### 5.2 5 つの根本問題

| # | 問題 | S 制約と対応 |
|---|---|---|
| **1** | **MSE は平均に収束、重尾の tail を過小評価する**。quantile loss でも訓練データに含まれる tail しか捉えない | S3 (重尾) 違反 |
| **2** | **OOD トリガー** (新規 market rule、initial 観測の cold snap) は学習分布外 → 予測値が外れる | S4 (新規トリガー) 違反 |
| **3** | **相関 vs 因果の混同**: 学習時に dinner-cook (時刻トリガー) と price spike (市場トリガー) が同時刻に起きる場合、NN は 2 つを区別できない。1 つだけ起きる新規シナリオで予測崩壊 | S7 (因果独立) 違反 |
| **4** | **SLA 保証不能**: NN は点推定または confidence interval を返すが、SLA は **tail 確率** の制約。点推定 → SLA 換算が非自明、保守側補正で過剰契約に逆戻り | S6 (動員) で fail |
| **5** | **設計を解いていない**: NN は予測機。**誰を standby に置くべきか** (= S6 設計問題) は別の最適化が要る。NN 単独では問題の 1/2 しか解いていない | S6 (設計) で fail |

### 5.3 提案手法 (trigger-orthogonal portfolio) がなぜ各問題を解くか

| # | NN の問題 | 提案手法の対応 |
|---|---|---|
| 1 | 重尾 tail 過小評価 | **予測しない**。trigger-orthogonal 設計は「どんな 1 トリガーに対しても残る」構造的保証で、tail の大きさを直接予測しない |
| 2 | 新規トリガー OOD | DER を **トリガー基底ベクトル** で表現するため、新規トリガーは既存基底の線形結合として表現可能 (基底次元自体が新規でない限り) |
| 3 | 相関と因果の混同 | DER の **因果トリガー曝露** を明示的にラベル付け (DER 種別 × 既知トリガー)。学習データの spurious 相関に依存しない |
| 4 | SLA tail 制約への翻訳 | portfolio 制約は「任意の 1 トリガー失効下でも sum standby capacity ≥ max burst」 = **直接 SLA に翻訳可能** |
| 5 | 設計を解いていない | 提案手法の出力 = **standby DER 選択そのもの**。設計と動員を分離した S6 構造を直接解く |

### 5.4 NN との **混合** は使えないか

「naive NN は不十分でも、tail を捉える NN + 提案手法 = 強い」案も検討:

- ✅ NN を **動員フェーズ** (= 今補充するか) の検出器として使うのは合理的 (point estimate でもトリガー成立判定は可能)
- ❌ NN を **設計フェーズ** に入れると S7 違反が再発 (NN は因果を学ばない)

つまり提案手法の **portfolio 設計を NN に置き換える** ことはできない。動員は NN または閾値法でよく、研究 contribution はあくまで **設計フェーズ** にある。

### 5.5 (Phase 1 で要検証) 反証可能性

NN baseline と提案手法を実 trace で比較するとき、提案手法が勝つには **以下の条件が trace に含まれる必要**:

- (a) burst churn の trigger が複数種類 (時刻、気象、市場)
- (b) 一部 trigger が **訓練/検証で異なる頻度** (= OOD 状況の擬似)

trace 設計でこの 2 条件を担保しないと、NN が偶然 trace を覚えて勝つ可能性がある。Phase 1 の trace synthesis でこれを反映する。

---

## 6. Rule 9 v2 — 遠隔ドメイン候補生成と invariant 検査

S8 (= trigger-orthogonal portfolio under heavy-tailed burst churn) を解く手法を、Power system / 金融以外の遠隔ドメインから生成する。Rule 9 v2 (step 5-9) に従い、**5 候補を並列で抽象化** し、invariant 検査で機械的に脱落させる。

### 6.1 step 5 — 候補列挙 (5 個並列)

「**外的トリガーで一斉撤退する母集団 + その損失を補う予備機構**」を持つ自然/社会現象を 5 個選定:

| # | 領域 | 機構の core (1 文) |
|---|---|---|
| **A** | 鳥群 sentinel behavior (動物行動) | 採餌者と歩哨に役割分離。歩哨は捕食者警報トリガーを共有する位置にいない |
| **B** | 種子バンクの dormancy heterogeneity (生態学) | 種ごとに異なる活性化トリガー (火・光・温度) を持つ種子が土中に共存、撹乱後に時系列分散して発芽 |
| **C** | 免疫系メモリ細胞 (免疫学) | リンパ節の保護 niche に多様な receptor を持つメモリ細胞が常駐 |
| **D** | 真社会性昆虫の age polyethism (社会生物学) | 同じ巣の働き蜂が齢で task 分担 (若 = 育児、老 = 採餌) |
| **E** | 雪崩 anchor (= 雪面に立つ巨木・地形) (地形学) | 不動の anchor が局所応力を分散、雪崩伝播を抑制 |

### 6.2 step 6 — 各候補の invariant 列挙と target 保存検査

各候補について:
- **(s)** 元ドメインで保存される暗黙前提 (5 項目)
- **(t)** target (VPP churn) で各前提が保存されるか

#### 候補 A: 鳥群 sentinel

| 元 (s) | target (t) | 保存? |
|---|---|---|
| s1: sentinel と forager が functional に分離 | t1: 標準 DER と standby DER が役割分離 | ✅ |
| s2: 役割割当は動的 (満腹個体が交代) | t2: 契約交代可能 (本質的でないが可能) | ✅ |
| s3: sentinel の警戒トリガー ≠ forager の採餌トリガー | t3: standby のトリガー曝露 ≠ active のトリガー曝露 | ✅ **(本質)** |
| s4: sentinel は forager に見えない threat space を観測 | t4: standby は active と異なる物理 context | ✅ |
| s5: sentinel コスト = 採餌時間損失 → 配分問題 | t5: standby 契約コスト → 最適化変数 | ✅ |

→ **5/5 保存。最強**

#### 候補 B: 種子バンク dormancy heterogeneity

| 元 (s) | target (t) | 保存? |
|---|---|---|
| s1: dormancy は **遺伝的決定** (個体は変えられない) | t1: DER の "dormancy" 型は契約で固定 | ⚠️ 弱 (契約再交渉可能) |
| s2: 活性化トリガーが種ごとに異なる (火/光/温度) | t2: トリガー曝露が DER 種別ごとに異なる | ✅ |
| s3: bank 構成が遷移系列を決める | t3: pool 構成が応答 sequence を決める | ✅ |
| s4: 土中 persistence が年〜十年単位 | t4: 契約 persistence は月〜年単位 | ✅ |
| s5: 休眠コスト = 種子産生エネルギー | t5: 予備契約コスト | ✅ |

→ 4.5/5 保存。s1 が**遺伝決定 vs 契約決定**で本質的弱さあり (= 「永続性」が遺伝で保証される自然系と、契約で保証される人為系の差)。ただし s2 (トリガー多様性) は強く保存され、**latency tranches** という別解として残し得る

#### 候補 C: 免疫メモリ細胞

| 元 (s) | target (t) | 保存? |
|---|---|---|
| s1: メモリ細胞は protected niche (lymph node) に物理的隔離 | t1: standby DER は契約上隔離 (active と独立 dispatch) | ✅ |
| s2: 受容体多様性が広範な抗原カバー | t2: トリガー曝露多様性 | ✅ |
| s3: **2 度目の感染で速応答** (somatic hypermutation 履歴) | t3: DER は過去 event から学習しない | ❌ |
| s4: メモリ細胞は長寿命 (年単位) | t4: 契約持続 | ✅ |
| s5: クローン維持エネルギーコスト | t5: 契約コスト | ✅ |

→ 4/5 保存。**s3 が core mechanism (= immunological memory)**。これが落ちると「免疫」を移植する意味が大きく失われる。**partial 保存、要再解釈**

#### 候補 D: 真社会性昆虫の age polyethism

| 元 (s) | target (t) | 保存? |
|---|---|---|
| s1: 齢ベースの task 分担 | t1: DER 型ベースの分担 (齢ではない) | ⚠️ 異次元 |
| s2: task 割当は **endogenous** (中央計画なし) | t2: VPP は **中央管理** (operator 計画) | ❌ |
| s3: 個体は **遺伝的にほぼ同一** (姉妹) | t3: DER は **異種** (heterogeneous) | ❌ |
| s4: task 切替は physiological cost | t4: 契約変更は契約コスト | ⚠️ |
| s5: colony robustness は task 比率に依存 | t5: pool 比率重要 | ✅ |

→ 2/5 保存。**s2, s3 が決定的に target で成立しない**。脱落

#### 候補 E: 雪崩 anchor 構造

| 元 (s) | target (t) | 保存? |
|---|---|---|
| s1: anchor は不動 | t1: 系統運用者所有蓄電池等は不変 | ✅ |
| s2: 空間分散 | t2: 空間 (フィーダー) 分散可能 | ⚠️ |
| s3: anchor は雪崩の **応力伝播を分断** | t3: VPP の SLA 失敗は **伝播しない** (DER 個別、非 cascade) | ❌ |
| s4: anchor は雪崩の一部ではない | t4: anchor DER は churning pool 外 | ✅ |
| s5: anchor 設置コスト | t5: 蓄電池設置コスト | ✅ |

→ 4/5 保存。**s3 (cascade propagation 制御) は target で成立しない** (VPP SLA は個別 trigger に独立 fail)。**partial 保存、機構の core が target に存在しない**

### 6.3 step 7 — 機械的脱落

invariant 完全保存 (5/5):
- **A: 鳥群 sentinel** ✅

部分保存 (4-4.5/5、core が部分的に target に成立):
- B: 種子バンク (dormancy の永続性が target で弱い)
- C: メモリ細胞 (memory mechanism が target で不在)
- E: 雪崩 anchor (cascade propagation が target で不在)

完全脱落 (≤2/5):
- D: 真社会性昆虫 (中央管理 / heterogeneity 不一致で脱落)

**残候補: A, B, C, E (ただし A 以外は core mechanism に懸念)**

### 6.4 step 8 — Rule 8 S6-S7 強制テスト

S6 (stakeholder cost) と S7 (trigger-orthogonal の機構直結度) で残候補を再評価:

| 候補 | 機構の VPP 翻訳 | S7 (trigger-orthogonal) 直結度 |
|---|---|---|
| **A 鳥群 sentinel** | DER をトリガー曝露でラベル付け、standby = active の曝露集合の補集合 | **直結 (mechanism そのもの)** |
| B 種子バンク | DER を活性化 latency でラベル付け、tranche 構成 | 間接 (時間多様性 ≠ トリガー直交) |
| C メモリ細胞 | DER を受容体多様性 (= 全トリガー網羅) でラベル付け | 間接 (broad coverage ≠ trigger-orthogonal) |
| E 雪崩 anchor | 不動 anchor DER を確保 (= 全トリガー独立) | 間接 (universal coverage ≠ orthogonal) |

→ **A だけが S7 を直接 captures する**。B/C/E は alternative mechanism (latency tranche / broad coverage / fixed reserve) を提供するが、**S7 の核心 (因果トリガー直交性) を捕捉していない**

### 6.5 step 9 — 最終選定

> **採用候補: A — 鳥群 sentinel mechanism の VPP への structural transposition**

```
最終手法名: Sentinel-DER Portfolio (SDP)
   active pool = forager flock (採餌)
   standby pool = sentinel pool (歩哨)
   設計原理: standby のトリガー曝露ベクトルが active の補空間にある
   動員原理: active 側のトリガーが発火したら、orthogonal な standby を呼ぶ
```

#### 6.5.1 数式化 (Phase 1 詳細設計の起点)

DER j のトリガー曝露ベクトル: $\mathbf{e}_j \in \{0, 1\}^K$ (K = トリガー基底次元数、commute / weather / market / comm 等)

集合 $A$ (active) に対する集合 $S$ (standby) の **trigger-orthogonality**:

$$
\text{TriOrth}(A, S) := \forall k \in [K]: \left( \sum_{j \in A} e_{j,k} > 0 \right) \Rightarrow \left( \sum_{j \in S} e_{j,k} = 0 \right)
$$

= 「active 側で曝露している全トリガー軸について、standby 側は曝露ゼロ」

設計問題:

$$
\min_{S \subseteq \mathcal{D} \setminus A} \sum_{j \in S} c_j \quad \text{s.t.} \quad \text{TriOrth}(A, S) \;\land\; \forall k: \text{Cap}_S^{(\bar{k})} \geq B_k
$$

ここで:
- $c_j$ = DER j の standby 契約コスト
- $\text{Cap}_S^{(\bar{k})}$ = トリガー k で **失われない** standby 容量 (= k で曝露しない standby DER の容量和)
- $B_k$ = トリガー k 発火時の最大 burst 規模 (要観測または事前推定)

これは **整数計画問題 (binary 選択 × 複数 constraint)**。Phase 1 で PuLP/CBC または Gurobi で実装可能。

#### 6.5.2 弱保存候補 (B, C, E) の役割

B/C/E は脱落させるが、**論文ではその脱落理由を明示** (= 「latency tranche や fixed reserve が trigger-orthogonality に劣る」根拠) して positioning 強化に使う。

---



