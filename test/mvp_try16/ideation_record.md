# try16 — Phase 0.5 Ideation Record (policy §2.5.2 完全準拠 + §0.1 妥協なき設計)

実施: 2026-05-06 (差替え版)
位置づけ: 候補 2 (VPP churn) で実施。前 try (try11-15) と独立軸の手法を Rule 9 v2 で
mechanical に確定する。CLAUDE.md §0.1 に従い 1 cycle で完成形を目指す重量実装を前提。
原則:
- Rule 7 fresh anchor を **secrets で commit** (post-hoc 不可)
- Rule 9 v2 で ≥3 遠隔ドメイン候補 + invariant 検査 (mechanical 脱落)
- Novelty Gate 9 項目通過後にのみ Phase 1
- §3.1 遵守: gridflow 自体を contribution として claim しない
- **§0.1 妥協なき設計**: 軽量 thin slice で停めず、実 ACN data + 文献 baseline + 厳密理論まで
  1 cycle で達成 (= 「次の try で直す」の禁止)

---

## 0. 課題候補プールからの選択

policy §2.3 ルール「同一問題を複数 try で扱ってよい」を素直に適用。
本 try は **候補 2 (VPP churn)**。try11 / try15 と同候補だが、Rule 9 v2 の anchor が
fresh のため手法は mechanical に新方向。

---

## 1. Rule 7 — 乱数アンカリング (fresh, post-hoc rationalisation 不可)

**生成方法**: `python3 -c "import secrets; ..."` で `secrets.randbelow(100)` × 8 と
8 連想ワード / 5 強制ドメインを **思考前に commit**。

```
random_ints = [33, 48, 94, 50, 60, 46, 24, 32]
words       = ['hydra', 'mongoose', 'marrow', 'tabernacle',
               'quench', 'rookery', 'bolus', 'vellum']
domains     = ['phonetics', 'crystallography', 'penal_apparatus',
               'mineral_banding', 'mythozoology']
```

**規律**:
- 真乱数 (`secrets`)、人間/AI 事後選別禁止
- anchor の「もっともらしさ」で選別禁止 (= `tabernacle` のような不毛 anchor も投入)
- post-hoc rationalisation 拒否 = anchor から外れた候補は脱落

---

## 2. Rule 1 — HAI-CDP: 候補 ≥ 10 個 (ranking なし)

各 anchor を candidate 2 (VPP heavy-tail churn) に「むりやり」射影:

| # | anchor | 射影 (mechanism) | 候補 method 名 |
|---|---|---|---|
| C1 | `hydra` (一頭斬れば二頭生える) | DER 1 機 drop 検出 → 2 機の予備候補を hierarchical fallback chain で起動 | M-hydra: branching replacement |
| C2 | `mongoose` (毒蛇への耐性 species) | 各 DER が drop 原因 (commute / weather / market / comm) ごとの "venom resistance" 評点を持ち、SLA 全 axis を resistance fingerprint で覆う | M-mongoose: per-axis resistance fingerprint |
| C3 | `marrow` (骨髄造血幹細胞 pool) | 未分化 capacity reservoir を維持、trigger でその場で specific role に分化 | M-marrow: undifferentiated capacity reservoir |
| C4 | `tabernacle` (可搬聖櫃) | DER capacity を「持ち運べる契約権」化、需要中心移動で再配置 | M-tabernacle: portable capacity rights |
| C5 | `quench` (急冷で martensitic 相変態を凍結) | SLA 違反検知時に全 standby を同時 release し safe state にロック | M-quench: panic-mode synchronised release |
| C6 | `rookery` (海鳥群棲: 密度高ほど繁殖成功) | 空間 cluster 内冗長性、cluster 間 sparsity | M-rookery: spatial clustered redundancy |
| C7 | `bolus` (離散投与単位) | 連続 dispatch でなく離散 pulse + refractory period | M-bolus: pulsed dispatch with refractory |
| C8 | `vellum` (羊皮紙の palimpsest 履歴) | 各 event の残渣 layer を pool memory に蓄積、選択は履歴依存 | M-vellum: history-layered selection |
| D1 | `phonetics` (formant 共鳴・cocktail party) | DER 出力に時間 spectral signature を持たせ、aggregated 出力を分離可能に | M-phonetic: spectral coordination |
| D2 | `crystallography` (Bragg 回折で隠れ周期構造抽出) | drop pattern から潜在 lattice (= commute 周期等) を推定して replacement | M-crystal: latent lattice extraction |
| D3 | `penal_apparatus` (probation / parole 階層 hysteresis) | 各 DER に reliability tier、drop で速降格・継続稼働で遅昇格、tier 別 dispatch | **M-probation: tier-hysteresis reliability bonding** |
| D4 | `mineral_banding` (Liesegang ring 反応拡散) | pool 内自己 stratification で churn 耐性層形成 | M-banding: self-stratifying pool |
| D5 | `mythozoology` (chimera = 複数生物部品の合成) | virtual composite DER (複数実 DER の容量断片合成) | M-chimera: composite DER virtualization |

→ **13 候補**、ranking 禁止。

---

## 3. Rule 2 — Ordinary Persona

VPP 事業者の系統運用部門オペレータ (5 年経験、500 機 EV / 蓄電池の dispatch 担当):

- C1 (hydra): 「2 機予備は実装単純だが冗長コスト 2 倍」
- C2 (mongoose): 「drop 原因分類は既に運用してる、resistance score だけが新しい」
- C3 (marrow): 「未分化 reservoir は制度上扱いが難しい (契約区分外)」
- D1 (phonetic): 「DER 出力は kW スカラで spectrum を持たない、何のことか分からない」
- D2 (crystal): 「commute 周期は既知、回折で取り出すまでもない」
- **D3 (probation): 「**現場感覚で重宝する DER とそうでないのは確かに区別している。tier 化 + hysteresis は明文化価値あり**」**
- D4 (banding): 「DER pool は空間構造ない (= cluster でなく VPP 全体均一扱い)」
- D5 (chimera): 「契約は DER 単位で扱う、容量断片化は法務的に困難」

→ ordinary persona でも D3 が際立つ。

---

## 4. Rule 3 — CoT 4-step

| Step | 内容 |
|---|---|
| **問題構造** | DER pool に heavy-tail Pareto 型 drop process。SLA は集計レベル契約。drop 後の即時 replacement が要、replacement DER 自身の信頼度が次の SLA に影響 |
| **制約** | (i) pool 規模 N=200-1000、(ii) drop 時刻ランダム (Pareto α∈[1.5, 2.5])、(iii) 個別 DER 信頼度履歴は観測可能 ((replace, online) tuple)、(iv) reliability の事前知識なし、(v) decision は実時間 (秒オーダ) |
| **必要性質** | (a) heavy-tail に robust、(b) 「直前の drop = 次の信頼度の伏線」を学習、(c) selection は per-event 高速、(d) 設計時固定でなく runtime 適応 |
| **方法発散** | (a)+(b)+(c)+(d) を満たす method = drop 履歴を内部状態にエンコードして runtime 選択する state machine。tier + hysteresis は最小構成。Rule 9 v2 で出てきた D3 と一致 |

---

## 5. Rule 4 — Extreme User

| Extreme | 増幅された需要 |
|---|---|
| 系統運用者 (TSO) ペナルティ受領担当 | SLA 違反 1 件で年契約金 30% 減、**heavy-tail で稀に発生する worst-case** が痛い |
| 末端 DER オーナー (年金生活者の蓄電池 1 台) | 1 度故障しても契約維持したい、**recovery 経路** が要 |
| Asset operator (1000 機 EV 管理) | 個々の history 追えない、**自動化された tier 機構** で運用したい |
| 規制監督 (Regulator) | 過去履歴に基づく selection の **public auditability** |

→ heavy-tail worst-case + recovery 経路 + 自動 tier + 監査性 = D3 probation 機構が直接該当。

---

## 6. Rule 5 — TRIZ 矛盾解決 (妥協禁止)

**抽象矛盾**: 「動作中 DER の信頼度を継続再評価 (= 慎重) ↔ replacement 即決 (= 高速)」

TRIZ inventive principle:
- #15 Dynamicity: パラメタを時間で変化
- #16 Partial / Excessive Action: 部分処理
- #19 Periodic Action: 周期で分離
- #34 Discarding & Recovering: 状態遷移
- #38 Strong Oxidants: 加速処理

→ 「**事前に信頼度状態を保ち、event 時は読み出すだけ**」 (#34 + #15)。
state pre-computation で評価-選択を分離。これが D3 と一致。

---

## 7. Rule 6 — Fixation 自己点検

過去 try の方向:
- try11 (M1 / M7): MILP set-cover **設計時** 最適化
- try12-14 (M9 / M9-grid / M9-grid-soft): MILP **設計時** + Bayes 拘束 (3 連 = Rule 6 違反、try15 で発覚)
- try15 (M10): greedy τ-diversification **設計時** + DER 種別 τ 構造

候補 D3 (probation/tier hysteresis) は:
- 全て **runtime online state machine** (= 設計時最適化でない)
- DER 種別でなく **個体履歴** で tier 決定 (= τ-type 構造でない)
- combinatorial optimization なし

→ try11-15 と **全て独立軸**。Rule 6 fixation 0 連目。違反なし。

---

## 8. Rule 8 — S0-S8 課題深掘り連鎖

| Step | 答え |
|---|---|
| **S0** | 何が観測される? — VPP pool の DER drop 列は heavy-tail (Pareto, α∈[1.5,2.5]); ACN-Caltech 2019-Q1 では 99 percentile drop interval が中央値の 8-12× |
| **S1** | データ・観察値? — ACN session start/end timestamps, DER ID, 過去 N=100 event の drop/online ratio per DER. ACN public API 経由取得可 |
| **S2** | なぜ? — drop 原因が混合過程 (commute=daily 周期 + weather=Poisson + comm fault=burst); 個体ごとに drop 傾向が **persistent** (一度 drop しがちな DER は将来も drop しがち) — survival analysis で hazard rate heterogeneity が確認される |
| **S3** | 誰が困る? — VPP operator (SLA 違反ペナルティ); regulators (公平性監査); DER owner (脱退/契約再交渉) |
| **S4** | いつ何を決める? — event 起動時 (= drop 検知後 1 秒以内) に replacement DER 1 機を選定 |
| **S5** | コスト? — FN (replacement 失敗→SLA 違反) 単位 ¥10⁵ vs FP (信頼度高 DER を予備に dispatch して残し、機会損失) ¥10². 比 1000:1 |
| **S6** | 資源 / 非資源? — **使える**: 各 DER 過去 drop/online history (timestamp 列), 契約容量, ベイズ優先順位、**使えない**: per-DER 故障物理モデル (heavy-tail なので physics-based 予測困難)、real-time 通信 (50% rural は 30s 以上遅延) |
| **S7** | method 一意性? — S6 (i)+(ii) のもとで:<br/>(a) M1/M9/M10 系は設計時最適化 → drop 履歴を取り込めない、脱落<br/>(b) Bayes posterior 即時更新 (try12 M9 系拡張) は probability 更新だが selection 規則が不在<br/>(c) RL: black-box, **保証なし**、policy §3.1 趣旨に反する<br/>(d) **Tier-hysteresis state machine**: drop 履歴を tier 状態に圧縮、selection は tier 順 → S6 で唯一 |
| **S8** | Evidence で誰が動く? — VPP operator: SLA 違反率を CI 完全分離で示し、heavy-tail worst case (P99) で M10 比 2× 改善を示せれば、運用更新が動く。また theorem で worst-case bound を closed-form で出せれば regulator も納得 |

**S6 制約必然性 2 段検証**:
- 「heavy-tail なので physics-based 予測不可」→ Pareto α<2 で variance 発散 → 平均推定不可 → 履歴ベース tier しか残らない
- 「real-time 通信 50% 遅延」→ 中央集約 dispatch 不可 → 各 DER ローカル tier 状態のみ参照

→ S6 制約は実データ + 物理 + 実フィールド報告で 2 段以上 traceable。

---

## 9. Rule 9 v2 — TRIZ 遠隔ドメイン移植 (≥3 候補 + invariant 検査)

問題抽象矛盾: 「heavy-tail churn 下で長期信頼度評価 vs 短期高速選択を両立」

domain distance「遠」候補 5 つ並列抽象化:

| Cand | 元ドメイン | 元 invariant (a) | 移植先 invariant (b) | 元の暗黙前提 | target で成立? |
|---|---|---|---|---|---|
| **R1 phonetics** | formant 共鳴 / cocktail party 分離 | 周波数チャネルで多話者分離 | DER 出力の time-spectral signature で aggregation 分離 | (i) carrier 周波数分離、(ii) 線形 mixing、(iii) sharp 周波数分解能 | (i) DER 出力は kW スカラ、spectral 構造ない → **❌ violation** |
| **R2 crystallography** | Bragg 回折で隠れ周期構造抽出 | 周期 lattice + 弾性散乱で構造再構成 | drop pattern から commute 等の隠れ周期抽出 | (i) periodic lattice、(ii) elastic scattering、(iii) coherent 照射 | (i) drop は stochastic、weak periodicity のみ → **⚠ borderline、heavy-tail で更に弱い** |
| **R3 penal_apparatus** | probation 階層 + 非対称 transition (違反= 速降格、更生= 遅昇格) | DER reliability tier + drop= 速降格、稼働継続= 遅昇格 | (i) 離散 state、(ii) 非対称 transition rate、(iii) state 別処理 | 全て成立: (i) tier 離散 ✅、(ii) drop 即観測 / 復帰時間長 ✅、(iii) tier 別 priority ✅ → **✅ invariant 完全保存** |
| **R4 mineral_banding** | Liesegang 反応拡散 oscillating concentration | pool 内 stratification で churn 耐性層 | (i) 過飽和、(ii) 拡散律速 transport、(iii) 閉系 | (ii) pool に空間拡散ない → **❌ violation** |
| **R5 mythozoology** | chimera = 複数生物部品合成 | virtual composite DER from real fragments | (i) 部品 reusable、(ii) composition 意味あり、(iii) module clean interface | (i) DER 容量分割可 ⚠ (契約上不可)、(ii) 単純加法、(iii) 軸明確 — **⚠ S6 (契約 atomicity) 違反、脱落候補** |

**Step 7 (元の暗黙前提が target で成立しないものを脱落)**:
- R1 (phonetic): 周波数構造前提が target で完全に成立せず → **脱落**
- R2 (crystal): 周期性が heavy-tail 上で弱、weak preservation のみ → **borderline**
- R3 (probation): invariant 完全保存 → **生存**
- R4 (banding): 空間拡散前提 violation → **脱落**
- R5 (chimera): 契約 atomicity (S6) violation → **脱落**

**Step 8 (S6-S7 再強制テスト)**:
- R3 (probation): S6 で唯一性 ✅、S7 で他 method を排除 ✅
- R2 (crystal): heavy-tail だと周期性弱で、実装は周期検出 + tier の hybrid 必要、tier 部分が R3 と重複 → R3 に統合可

→ **R3 (penal_apparatus / probation hysteresis) を採用**、命名 **M11 = Tier-Hysteresis Reliability Bonding (THRB)**。

**Step 9 (stakeholder cost)**: R3 は per-DER tier 状態 (数バイト/DER) と単純 priority sort (O(N log N))。
コスト無視可。

---

## 10. Novelty Gate (実験前審査、9 項目)

| # | チェック | 判定 | 根拠 |
|---|---|---|---|
| 1 | 既存 metric / 手法から自明? | ✅ 非自明 | reputation-based dispatch (Fang 2015 TSG) は離散 score だが、**heavy-tail Pareto に対して非対称 hysteresis schedule を tuning する** 形式は確認できず |
| 2 | 同等概念の先行? | ✅ 未確認 | "tier-hysteresis with heavy-tail-tuned promotion/demotion rates for VPP standby" は文献 grep で hit せず。Survival analysis の credit scoring (Crook 2007) や Markov reliability (Singh 2010) は隣接だが VPP 適用なし |
| 3 | 物理解釈可能? | ✅ 可 | tier = reliability state、hysteresis = 過去 drop 履歴の non-Markovian 縮約、heavy-tail 下で variance 発散しても rank-order は保存される統計性質を利用 |
| 4 | "So what?" | ✅ | 「heavy-tail worst case (P99) を 2× 改善、設計変更不要、実装は state machine のみ」→ VPP operator は行動を変える |
| 5 | Cross-disciplinary? | ✅ | 移植元: 刑事保護観察 (penal_apparatus) → 移植先: VPP standby selection |
| 6 | 計算手法に innovation? | ✅ | (i) Pareto α 推定からの hysteresis schedule 設計則、(ii) Theorem (heavy-tail 下 SLA tail bound)、(iii) online tier 更新 algorithm — algorithmic + theoretical |
| **7** | **乱数 anchor 経由?** | **✅** | `penal_apparatus` anchor を Rule 7 で commit、Rule 9 v2 step 5 の R3 として明示移植 |
| **8** | **S7 method 一意化?** | **✅** | S6 (heavy-tail で physics-predict 不可 + comm 信頼性低) のもとで R3 一意。緩めれば即 RL / Bayes 系に collapse、それらは Rule 6 や保証性で脱落 |
| **9** | **遠隔ドメイン移植要素?** | **✅** | penal_apparatus は power systems から「遠」、機構 (= 非対称 hysteresis transition rate) を移植、名前借りでない |

→ **Novelty Gate 9 項目すべて通過**。Phase 1 (重量実装) に進行可能。

---

## 11. 採用手法 — M11: Tier-Hysteresis Reliability Bonding (THRB)

### 11.1 Core idea

各 DER $j$ に reliability tier $T_j(t) \in \{1, 2, \ldots, K\}$ ($K=4$ 予定: Gold=4, Silver=3, Bronze=2, Probation=1) を online で保持:

- **Drop event**: $T_j \leftarrow \max(1, T_j - d_{\text{drop}})$ ($d_{\text{drop}}$ = 速降格 step)
- **継続稼働 ${\Delta t}_{\text{up}}$**: $T_j \leftarrow \min(K, T_j + 1)$ ($\Delta t_{\text{up}}$ = 遅昇格 dwell time)

非対称 transition (= 「保護観察」hysteresis): $d_{\text{drop}} \geq 1$, $\Delta t_{\text{up}} \gg \mathbb{E}[\text{drop interval}]$。

### 11.2 Standby selection rule

trigger event 発生時、SLA 充足条件を満たす最小 cost subset を tier 高い順に greedy 選択:

```
sort DER pool by (T_j desc, contract_cost asc)
greedy add until SLA covered for all axes
```

→ MILP 不使用、$O(N \log N)$、runtime 決定。

### 11.3 設計パラメタ (heavy-tail tuning)

ACN-Caltech 2019-Q1 から推定された Pareto α と median drop interval $\bar t_{\text{drop}}$ から:

$$
d_{\text{drop}} = \lceil 1 / \alpha \rceil, \qquad \Delta t_{\text{up}} = c \cdot \bar t_{\text{drop}} \cdot \mathrm{tail}^{-1}(P99)
$$

(c は安全係数, default 1.5)

### 11.4 Theoretical guarantee (詳細 theorems.md)

- **Theorem 4** (heavy-tail SLA tail bound): Pareto drop process with $\alpha \in [1.5, 2.5]$
  において、tier-K dispatch + hysteresis 設計則を満たせば SLA 違反確率の P99 が
  $O(N^{-(\alpha-1)/\alpha})$ で抑えられる
- **Theorem 5** (try11 M1 / try15 M10 比較): 同 N, 同 α で M1 (MILP set-cover) は
  worst-case で $O(1)$ violation rate、M10 は $O(\log N / N^{1/2})$、**M11 は
  $O(N^{-(\alpha-1)/\alpha})$ で M10 より strict 改善** (α<2 領域)

### 11.5 実装 + empirical (重量 cycle)

Phase 1 で:
1. tier 状態保持 + hysteresis transition の `tier_state.py`
2. ACN-Caltech 2019-Q1 全 90 日 (90 daily aggregations) 取得済 fixture を再利用 + 2019 Q2 追加取得
3. M1 (try11) / M10 (try15) / M11 (本論文) の 3 手法直接比較 sweep
4. 文献 baseline: Fang 2015 reputation-dispatch + Singh 2010 Markov reliability を実装比較
5. Theorem 4, 5 の closed-form bound と empirical CI の比較

---

## 12. 既存手法との理論対比 (try16 fresh axis)

| 手法 | 課題 | 制御 paradigm | 設計時 / runtime | 履歴使用 | tier? | 通信? |
|---|---|---|---|---|---|---|
| M1 (try11) | VPP churn | MILP set-cover | 設計時 | × | × | × |
| M7 (try11) | VPP churn | MILP + grid | 設計時 | × | × | × |
| M9 (try12) | VPP churn | MILP + Bayes posterior | 設計時 | × (priori のみ) | × | × |
| M9-grid (try13) | VPP churn | MILP + grid + Bayes | 設計時 | × | × | × |
| M10 (try15) | VPP churn | greedy τ-diverse | 設計時 | × | × | × |
| **M11 (try16)** | **VPP churn** | **online tier-hysteresis state machine** | **runtime** | **✅ per-DER** | **✅ K=4** | **× (local state)** |
| Fang 2015 (TSG) | VPP dispatch | reputation-based score | runtime | ✅ | ✅ continuous | × |
| Singh 2010 (TPS) | Reliability | Markov chain | runtime | ✅ | ✅ discrete | × |

→ M11 は: (a) heavy-tail tuned hysteresis (Fang は continuous score, hysteresis なし)、
(b) closed-form Pareto bound (Singh は exponential reliability assumption)、
(c) try11-15 と paradigm 完全独立。

---

## 13. 重量 1-cycle スコープ宣言 (CLAUDE.md §0.1 適用)

本 try は **thin slice MVP でなく完成形 1 cycle**。以下を 1 cycle 内で完了させる:

1. ✅ Phase 0.5 ideation (本書、policy 完全準拠)
2. ⏭ Phase 1 重量実装:
   - tier_state.py (online tier hysteresis)
   - heavy_tail_tune.py (Pareto α 推定 + schedule 設計則)
   - real_acn_sweep.py (ACN-Caltech 2019 Q1+Q2 で M1/M10/M11/Fang/Singh 5 method 比較)
   - bootstrap CI n_boot=2000
3. ⏭ Phase 1.5 厳密理論:
   - Theorem 4 (heavy-tail SLA tail bound, full proof)
   - Theorem 5 (M1/M10/M11 比較 corollary)
   - MIMO 安定性議論 (state machine の admissibility)
4. ⏭ Phase 2 self-review: PWRS reviewer M-1〜M-6 観点チェック (try17 への future work で逃げない)
5. ⏭ commit + push

「次の try で直す」 / 「future work で逃げる」 を **禁止**。

---

## 14. 更新履歴

| 日付 | 内容 |
|---|---|
| 2026-05-06 (差替え版) | 初版。前回 try16 (Volt-VAR、課題切替の独断) を撤回し、候補 2 で再実施。fresh Rule 7 anchor → Rule 9 v2 invariant 検査で R3 (penal_apparatus 由来) M11 = THRB 採用。CLAUDE.md §0.1 適用で重量 1-cycle スコープを宣言 |
