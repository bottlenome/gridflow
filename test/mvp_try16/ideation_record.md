# try16 — Phase 0.5 Ideation Record (policy §2.5.2 完全準拠)

実施: 2026-05-06
位置づけ: try11-15 (candidate 2 = VPP churn) の Rule 6 fixation を断ち、**candidate 1 (Volt-VAR、高 PV 浸透 + 雲影スパイク)** に課題を切替えての独立 MVP cycle。
原則:
- Rule 7 (乱数 anchor) を **最先に commit**、その後 ranking なしに Rule 1 で候補展開
- Rule 9 v2 で ≥3 遠隔ドメイン候補 + invariant 検査 (try10 失敗教訓を回避)
- Novelty Gate 9 項目通過後にのみ実装へ
- §3.1 遵守: gridflow 自体を contribution として claim しない

---

## 0. 課題候補プールからの選択 (policy §2.3)

| try | 採用問題 | 備考 |
|---|---|---|
| try11-14 | 候補 2 (VPP churn) MILP set-cover 軸 | Rule 6 違反 (3+ iterations 同方向) |
| try15 | 候補 2 (VPP churn) τ-diversification 軸 | Rule 6 打破済、M10 で CI 完全分離 |
| **try16** | **候補 1 (Volt-VAR、PV + 雲影)** | **問題自体を切替え。Rule 6 を構造的に回避** |

**選択理由**: try11-15 で「VPP churn × 各種手法」を 5 サイクル回したため、同候補に留まると Rule 6 fixation の温床。candidate 1 (Volt-VAR) は (i) 物理が異なる (= heavy-tail churn ではなく秒スケール spatio-temporal voltage dynamics)、(ii) 学術 gap も異なる (= 通信遅延ロバスト分散制御)、(iii) gridflow 実装難度が低〜中で sweep が回しやすい。

---

## 1. Rule 7 — 乱数アンカリング (最先 commit, post-hoc rationalisation 不可)

**生成方法**: `python3 -c "import secrets; ..."` で `secrets.randbelow(100)` × 8 と
8 連想ワード / 5 強制ドメインを **思考前に commit**。

```
random_ints = [33, 22, 16, 9, 3, 20, 30, 99]
words       = ['plinth', 'cinder', 'glacier', 'vestige',
               'nimbus', 'kestrel', 'thorax', 'lichen']
domains     = ['classical_architecture', 'sedimentology',
               'foundry_casting', 'combustion_residue', 'epigraphy']
```

**規律 (policy Rule 7 失敗パターン回避)**:
- 乱数は `secrets` で真乱数列、人間/AI による事後選別を禁ず
- anchor は **「もっともらしさ」で選ばない**。本 ideation でも `kestrel` のような明らかに不毛な anchor も Rule 1 候補集合に同等に投入
- post-hoc rationalisation 禁止 = 候補が anchor から外れた瞬間にその候補を脱落させる

---

## 2. Rule 1 — HAI-CDP: 候補 ≥ 10 個 (ranking なし)

各 anchor を candidate 1 (Volt-VAR + 雲影) に **「むりやり」射影**。

| # | anchor | 射影 (mechanism) | 候補 method 名 |
|---|---|---|---|
| C1 | `plinth` (古典建築の柱基) | 各 PV inverter は **静的 Q セットポイント** を持ち、雲影に動かない。劣化 hunting を避ける | M-pedestal: static-Q with dead-band |
| C2 | `cinder` (燃焼残渣 / passivation) | 一度雲影 hit を受けた inverter は **char-layer 状の不応答区間** に入り、再 hit を hysteresis で吸収 | M-passivate: hysteresis-locked Q |
| C3 | `glacier` (氷河の creep + surge) | 通常時は粘性 (slow) 応答、しきい値超で surge (rapid Q) | M-creep-surge: dual-mode droop |
| C4 | `vestige` / `epigraphy` (碑文の上書き) | 過去 N 雲影の **palimpsest 履歴** から spectral footprint を学習し前送り | M-palimpsest: spectral feed-forward |
| C5 | `nimbus` (雲) | 自分自身の **影 transit 時刻** を pyranometer で予測、feed-forward Q | M-nimbus: irradiance feedforward |
| C6 | `kestrel` (停飛行 hover) | 風予測でホバリング → 各 inverter は **隣接 V 勾配** から forward 風予測 | M-kestrel: neighbor V-gradient feedforward |
| C7 | `thorax` (節足動物の rigid+flexible 分節) | 各 inverter を rigid (常時 droop) + flexible plate (大変動時のみ起動) に分節 | M-thorax: dual-stage Q |
| C8 | `lichen` (菌-藻共生 / 拡散 consensus) | 各 inverter を fast 局所 droop + slow 拡散 consensus の二相に分割。consensus 信号は **bus 残差電圧そのもの** = 通信不要 | M-lichen: two-time-scale local |
| C9 | `classical_architecture` (アーチ / フライング・バットレス) | 末端電圧をアーチの thrust line として静的位相補償器配置 | M-arch: static SVC placement |
| C10 | `sedimentology` (グレーデッド・ベッディング, Stokes 沈降) | 各 inverter の **応答時定数 τ を フィーダー radial 深度 d で stratify** (τ_d = τ_0 + α d) → fast 機が変電所近傍, slow 機が末端。雲影の spatio-temporal 伝搬を depth-graded LPF で吸収。**通信不要、局所 V のみ** | **M-strata: depth-graded τ droop** |
| C11 | `foundry_casting` (方向性凝固, mushy zone front) | 雲影 voltage front を solidification front 模擬で local dV/dt から追跡、Q 配分を front-following | M-cast: front-tracking droop |
| C12 | `combustion_residue` × `random_int 33` | 33 番目バスから順番に Q 投入、ash-residue 模倣 | M-ashstack: ordered staircase Q |
| C13 | random `[16, 9, 3]` × `vestige` | 16/9/3 秒スケールの **3 階層レイテンシ層** に分割 (multi-time-scale palimpsest) | M-tri-vestige: 3-tier delay layer |

→ **13 候補**。policy §2.5.2 Rule 1 「ranking で絞らず Rule 9 v2 invariant 検査で機械的に脱落させる」に従い、ここでは順序付け禁止。

---

## 3. Rule 2 — Ordinary Persona

「最適化研究者ではなく、配電部門の現場エンジニア (10 年経験、PV 接続申請を年 200 件処理)」になりきって候補を見る:

- C1 (pedestal): 「現場では既に dead-band 入り droop が標準。novelty 弱い」
- C2 (passivate): 「機器メーカ的にロック機構入れたら誤動作の心配で苦情来る」
- C9 (arch): 「SVC 設置場所最適化は 1990 年代から既存研究」
- C10 (strata): 「**radial 深度で τ を変える発想は聞いたことない**。実装も simple」← 興味津々
- C8 (lichen) / C11 (cast): 「2 段ループは存在 (PI droop) が、physical 機構由来の τ 設計は新しい」

→ ordinary persona でも C10 が際立つ (= AI 平均化バイアス回避の 1st filter)。

---

## 4. Rule 3 — CoT 4-step

| Step | 内容 |
|---|---|
| **問題構造** | PV 大量導入 + 雲影 → 秒スケール voltage swing。中央 MPC は遅い、純局所 droop は隣接干渉で hunting、consensus は通信遅延 50-500 ms で発散 |
| **制約** | (i) 雲影 80% 降下が 2 秒以下、(ii) 通信遅延 ≥ 50 ms、(iii) 各 inverter 局所 V 測定のみ廉価、(iv) 設置位置・容量は配電網設計時固定 (= 後付け制御 logic だけが自由パラメタ) |
| **必要性質** | (a) 局所のみで動く、(b) 遅延非依存、(c) 隣接干渉なし、(d) cloud-edge 通過と coherent な空間時間応答 |
| **方法発散** | (a)+(b)+(c)+(d) を満たすには **空間構造を時間応答で写し取る** メカニズムが必要 → C10/C11 は強候補 |

---

## 5. Rule 4 — Extreme User

| Extreme | 増幅された需要 |
|---|---|
| 全国送電監視センターのオペレータ | 数百フィーダ同時雲影でも電圧違反 0 件、通信路がダウンしても自走 |
| 末端農家の屋根 PV (フィーダ末端、線路抵抗 10× 標準) | 末端でこそ電圧が上がる。**末端機が末端用に slow 設計** されていてほしい |
| 架空線冬期着雪敷設エリア | 通信線が定期的に切断、**完全 comm-free** が前提 |
| 系統運用者 (TSO) | フィーダ全体が外部から **「LPF 1 個」のように見える** ことを望む (= 集約特性が予測可能) |

→ 末端農家 + 着雪エリアの圧力 = 「**comm-free + 末端用 slow 機**」が突出 = C10 strata に直結。

---

## 6. Rule 5 — TRIZ 矛盾解決 (妥協禁止)

**抽象矛盾**: 「個体の高速応答 (= 大ゲイン droop) ↔ 集団の同期共鳴回避 (= 小ゲイン consensus)」

TRIZ 推奨 inventive principle:
- #1 Segmentation: 全インバータを同質扱いせず、空間で分割
- #3 Local Quality: 場所ごとに最適化される性質
- #15 Dynamicity: パラメタが時間/位置で変化
- #19 Periodic Action: 周期/周波数で分離

→ 「**空間勾配で時間応答を分離**」を許す原理 = #1 + #3 + #15 の合成。これが C10 strata と一致。

---

## 7. Rule 6 — Fixation 自己点検

- try11 (M1) → try12 (M9) → try13 (M9-grid) → try14 (M9-grid-soft) は **MILP set-cover 同方向 4 連** = Rule 6 違反 (try15 review_record で確認済)
- try15 (M10) は τ-diversification で軸転換 → fixation 打破成功
- **try16 候補**:
  - candidate 1 (Volt-VAR) に **問題自体を切替え** (= candidate 2 への執着を断つ)
  - 手法 C10 (strata) は (a) MILP 不使用、(b) τ-diversification ではあるが **対象が DER type ではなく feeder topology depth** で M10 とは座標系が異なる、(c) 通信遅延ロバスト分散制御という独立軸

→ Rule 6 通過。try15 M10 とも try11-14 MILP 系とも独立。

---

## 8. Rule 8 — S0-S8 課題深掘り連鎖

| Step | 答え |
|---|---|
| **S0** | 何が観測される? — 高 PV 浸透フィーダ (PV 容量 ≥ 0.6 × フィーダ定格) で晴天昼に逆潮流→電圧 1.05-1.10 pu、雲影通過時に 5-30 秒で 0.95-1.05 を往復 |
| **S1** | データ・観察値? — irradiance 時系列 (秒分解能), bus voltage (秒分解能), Q output per inverter, line R/X. 文献 (Mahmud 2017, Antoniadou-Plytaria 2017) で violation 頻度 0.5-3% / day |
| **S2** | なぜ? — ΔV ≈ R·ΔP (DistFlow 線形化) + 隣接 inverter の Q 干渉項。雲影は **空間移動する step disturbance** で feeder 上 5-30 m/s で伝搬 |
| **S3** | 誰が困る? — 配電事業者 (新規変電所投資)、PV 設置申請者 (容量制限)、隣家 (フリッカ苦情) |
| **S4** | いつ何を決める? — 設計時 = 制御 logic (gain/τ/dead-band)。運転時 = 各 inverter 1 秒以内 Q 出力決定 |
| **S5** | コスト? FN/FP 比? — FN (= 違反見逃し) コスト ≫ FP (= 過剰 Q)。事業者ペナルティ ¥10⁵/事象 vs Q 提供電力 ¥10² |
| **S6** | 資源 / 非資源? — **使える**: 局所 V 測定 (秒)、局所 P 測定、各機 Q 範囲 [-0.45, 0.45] pu、設計時の τ 自由 / **使えない**: 隣接通信 (遅延 50-500 ms 仮定で発散)、中央 MPC (10 秒以上)、追加 sensor (pyranometer 設置不可) |
| **S7** | method 一意性? — S6 (i)+(ii) 制約下では C10 strata が唯一: (a) C5 nimbus は pyranometer 不可で脱落、(b) C6 kestrel は隣接 V comm 必要で脱落、(c) C8 lichen は consensus に slow comm 必要、(d) C10 strata は **通信不要** で空間勾配を時間応答に符号化、唯一の method-unique 解 |
| **S8** | Evidence で誰が動くか? — 配電事業者: 「voltage violation 率を 1/5 以下、comm-free 構成で」と numerical 提示できれば、新規変電所投資判断 (¥10⁹) を retrofit 制御更新 (¥10⁷) に切替える |

**S6 制約の必然性 2 段検証**:
- 「comm-free 必要」は何故? → (1) 通信遅延 50-500 ms で consensus 発散 (Antoniadou-Plytaria 2017 Sec.5)、(2) 着雪/雷で通信線切断は実フィールド報告
- 「pyranometer 設置不可」は何故? → (1) 末端農家屋根 PV は機器原価制約、(2) 既存設置 inverter retrofit には sensor 増設不可

→ S6 制約は実データ起点で 2 段以上 traceable = post-hoc でない。

---

## 9. Rule 9 v2 — TRIZ 遠隔ドメイン移植 (≥3 候補 + invariant 検査)

**問題抽象矛盾**: 「個体の高速応答 vs 集団の同期共鳴回避、通信なしで実現」

domain distance「遠」ドメインから ≥3 候補:

| Cand | 元ドメイン | 元 invariant (a) | 移植先 invariant (b) | 元の暗黙前提 | 暗黙前提が target で成立? |
|---|---|---|---|---|---|
| **R1 sedimentology** | Stokes 沈降 / graded bedding | 静止流体中で粒子は terminal velocity で stratify、相互作用なし無調整で空間分離 | inverter τ_d = τ_0 + α d_j とすれば cloud edge ω に対し下流ほど LPF 強、空間で response が stratify | (i) 重力均一、(ii) 粒子非干渉、(iii) 無限深さ | (i) feeder 末端へ単調 → ✅、(ii) inverter は radial 上流→下流方向のみ干渉 (放射状網) → **✅ 局所成立**、(iii) 末端で fixed boundary → ⚠ 有限だが解析可能 → **invariant 概ね保存** |
| **R2 foundry_casting** | 方向性凝固の mushy zone front | 凝固フロントが熱勾配で局所速度決定、front-tracking は局所 dT/dt のみ | voltage violation front を local dV/dt で追跡、front-following droop | (i) 単調境界条件、(ii) 一方向熱流 | (i) 雲影は monotone とは限らず 2 方向同時通過あり → **❌ violation**、(ii) feeder 1 入口で OK | invariant 不保存 (cloud edge 衝突), **脱落** |
| **R3 lichen symbiosis** | 菌藻共生の代謝拡散 consensus | 異種が局所代謝交換で平衡、time-scale 分離 (fast 反応 / slow 拡散) | inverter の fast 局所 droop + slow consensus、後者は bus 残差電圧自己拡散で 通信なし | (i) 拡散は近隣のみ、(ii) 平衡点が unique | (i) 残差 V は radial 沿いに勾配確かに伝播 → ✅、(ii) 配電網は単一平衡点 → ✅、ただし time-scale separation 比 ε に依存。ε≪1 でないと両 loop 干渉 | invariant 保存条件付き ✅ — **survive** |
| **R4 kestrel hovering** | 視覚 optic flow による前向風予測 | センサで前方風予測 → 翼面調整 | 隣接 V 勾配センシングで前向 V 予測 → Q 調整 | (i) 前向きセンサ、(ii) 視覚帯域 30 Hz | S6 で隣接 comm 不可 → **❌ S6 違反、脱落** |
| **R5 classical arch** | thrust line 静的伝達 | 静的安定 | dynamic cloud に静的だけでは応答できず | (i) 静的 / 時間なし | dynamic case で **❌ 脱落** |

→ **invariant 検査後の生存候補**: R1 (sedimentology), R3 (lichen) の 2 つ。

**S6-S7 再強制テスト**:
- R1 strata: **τ を radial 深度のみで決定**、各 inverter は局所 V のみ参照、comm 完全不要、設計時固定 τ → 運転時 logic は標準 droop。S7 制約下で唯一性 ◎
- R3 lichen: 二相分離 PI droop は fast 局所 + slow consensus。consensus 信号として bus 残差 V を使えば「自己拡散」で comm 不要だが、**slow loop の安定性は τ_slow ≪ τ_cloud を要求**。設計上 τ_slow > τ_cloud では発散するため condition-attached、唯一性 ⚪︎ (条件付き) 

**stakeholder cost (S5)**:
- R1: 設計時固定 τ → retrofit 安価 (logic 更新のみ)
- R3: τ tuning が cloud spectrum に依存 → site survey 必要、cost ↑

→ **R1 (sedimentology / Stokes graded bedding) を採用** = M11 と命名。
R3 を比較対照群 (= 自然な隣接案、後の議論で「単に 2 段にしただけでは不十分」を示すための baseline) として残置。

---

## 10. Novelty Gate (実験前審査、9 項目)

| # | チェック | 判定 | 根拠 |
|---|---|---|---|
| 1 | 既存 metric / 手法から自明? | ✅ 非自明 | 線形 droop の K は 1 つの定数。τ を radial 深度で stratify する設計は文献 (Mahmud 2017, Antoniadou-Plytaria 2017, Bolognani 2015) に未確認 |
| 2 | 同等概念の先行? | ✅ 未確認 | 「distributed droop with depth-graded τ derived from sediment Stokes invariant」は引用 grep で hit せず。distance-based gain (= K varies with d) は限定的に存在 (Robbins 2013) が **τ = stratification mechanism** ではない |
| 3 | 物理解釈可能? | ✅ 可 | feeder voltage = 縦方向の沈降井戸。cloud-edge frequency ω に対し各 depth で 1/(1+jωτ_d) フィルタ、空間-周波数 tomography 構造 |
| 4 | "So what?" | ✅ | 「voltage violation が 1/5 に、追加 sensor 不要、retrofit 可、新規変電所 1 ヶ所 ¥10⁹ 投資回避」→ 配電事業者は行動を変える |
| 5 | Cross-disciplinary? | ✅ | 移植元: 堆積学 (Stokes) → 移植先: 配電制御 |
| 6 | 計算手法に innovation? | ✅ | (i) τ_d = τ_0 + α d スケジューリング設計則、(ii) Theorem (depth-graded LPF cascade の閉形式 Bode bound) — algorithmic + theoretical |
| **7** | **乱数 anchor 経由?** | **✅** | `sedimentology` anchor を Rule 7 で commit、Rule 9 v2 step 5 の R1 として明示移植 |
| **8** | **S7 method 一意化?** | **✅** | S6 (i) comm 不可 + (ii) sensor 増設不可 + (iii) 設計時 τ 自由のもとで R1 strata 一意。緩めれば即 R4 kestrel / R3 lichen に collapse |
| **9** | **遠隔ドメイン移植要素?** | **✅** | sedimentology は「遠」距離 (vs power systems)、機構 (= Stokes settling invariant) を移植、名前借りでない |

→ **Novelty Gate 9 項目すべて通過**。Phase 1 (実装) に進行可能。

---

## 11. 採用手法 — M11: Stokes-Stratified Droop

**Core idea**: 各 PV inverter j の Q 応答時定数 τ_j を **フィーダ放射状深度 d_j**
(変電所からの electrical distance、line R sum) の関数として設計時固定:

τ_j = τ_min + α · (d_j / d_max)

K_j (gain) は標準 droop 同等 (容量 prorated)。雲影 frequency ω に対し inverter j は
1/(1+jω τ_j) で応答。空間-周波数構造により:

- 高 ω (fast cloud edges) → 浅い (近変電所) inverter のみ反応 → 末端の意図せぬ干渉なし
- 低 ω (cloud envelope) → feeder 全体で協調反応

**comm 完全不要、retrofit 可、設計時 1 度 τ_j 計算するだけ**。

---

## 12. 既存手法との位置関係 (try16 fresh axis)

| 手法 | 課題 | 制御パラダイム | comm? | τ 設計 |
|---|---|---|---|---|
| 純局所 droop (Mahmud 2017) | Volt-VAR | distributed | × | 全機 同 τ |
| Consensus PI (Bolognani 2015) | Volt-VAR | distributed | ✅ 必要 | per-node 単一 τ |
| 中央 MPC (Magni 2007) | Volt-VAR | centralised | ✅ 必要 | N/A |
| **M11 strata (try16)** | **Volt-VAR** | **distributed** | **× 不要** | **τ_j = f(d_j) depth-graded** |
| M1/M7 (try11) | VPP churn | MILP 設計時 | N/A | N/A |
| M9/M9-grid (try12-14) | VPP churn | MILP + Bayes | N/A | N/A |
| M10 (try15) | VPP churn | greedy τ-diverse | N/A | DER 種別 τ 多様化 |

→ M11 は **問題側 (Volt-VAR)**, **制御パラダイム側 (depth-graded τ distributed)** のどちらでも try11-15 と直交、Rule 6 fixation 完全打破。

---

## 13. 更新履歴

| 日付 | 内容 |
|---|---|
| 2026-05-06 | 初版。Rule 7 anchor を `secrets.randbelow` で commit → Rule 1 で 13 候補 → Rule 9 v2 invariant 検査で R1+R3 生存 → S7 で R1 一意化 → M11 (Stokes-Stratified Droop) 採用、Novelty Gate 9/9 通過 |
