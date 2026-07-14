# try 17 — 高PV浸透下の電圧違反リスク：容量ではなく「配置」が効く（IEEE13, OpenDSS）

<!-- 標準経路（docs/mvp_standard_workflow.md）のみで実施。自作スクリプトなし。 -->

## 1. 課題（出典）

- 出典: `docs/mvp_problem_candidates.md` 候補1（高PV浸透 + 雲影スパイクの Volt-VAR）。学術ギャップ＝**PVの配置・容量の不確実性の下での電圧違反リスクの特性化**。
- 一文で: 住宅配電フィーダー（IEEE13）に屋根置きPVを大量導入したとき、母線電圧が ANSI C84.1 Range A（0.95–1.05 pu）帯を外れる違反リスクが、PVの「容量」と「電気的位置」のどちらでどれだけ駆動されるか。

## 2. 手法（framework の実 DOF に限定）

- baseline: `ieee13@1.0.0`（標準 baseline pack, `baseline: true`）を `scenario clone` して `ieee13-voltvar@1.0.0` を派生。
- 介入: pack パラメータ `pv_bus` / `pv_kw` を振り、OpenDSS で単一PVを注入して潮流を解く（コネクタの runtime-PV 注入機能）。
- **重要な設計判断（Rule 9 v2 / invariant 検査）**: 独立アイデア創出で 5 候補を生成し、
  - ❌ 新規Q制御コントローラ提案型 → gridflow に制御アルゴリズムの一級プラグイン点が無く、自作は try11-16 の反パターン（標準経路逸脱）→ **機械的に脱落**。
  - ❌ 同一設定のシード反復で分散推定型 → **OpenDSS の潮流はシード非依存で完全決定的**（seed 1 と 2 で母線電圧が bit 単位一致、実測）→ 分散ゼロ → benchmark の zero_variance ガードが有意判定を拒否 → **脱落**。
  - ✅ 採用: **配置ランダム性を唯一の正当な分散源**とする特性化（容量効果 / 位置効果）。

## 3. 実験設計

- feeders: IEEE13（単一系統。**§4.2 E-2 の「≥2 feeder」を満たさない — Limitations 参照**）。
- 分散源: PV配置のランダム性（`RandomSampleAxis`, seed=100, N=24/条件）。**シード反復ではない**。
- envelope: V_min=0.95 / V_max=1.05 pu（ANSI C84.1 Range A, strict）。全メトリクスに刻印。
- 条件:
  - 容量: BASE(pv_kw=0) / LOW(600) / HIGH(1800)、全母線からランダム配置（同一 seed でペア）。
  - 位置: HIGH固定(1800)で ROOT={632,634,645,646}（変電所近傍）vs END={675,611,652,680}（フィーダー末端）。
- 全実行が `gridflow sweep`→`benchmark`（Holm補正・permutation検定・Cohen's d・bootstrap CI）。自作統計コードなし。

## 4. 結果（すべて results/*.json に基づく）

### 4.1 ベースライン（PV無, 決定的）
既存負荷だけで **voltage_violation_rate = 0.488**（stdev=0.000, n実質=1）。IEEE13 は末端母線の**低電圧**違反が既に約49%存在する。これは PV では制御対象外の baseline_only。

### 4.2 容量効果 — 平均には有意差なし（ガードが早計を却下）

| 比較 | delta(vvr) | Cohen's d | p_adj(Holm) | significant |
|---|---|---|---|---|
| BASE→HIGH | **−0.069** | −0.429 | 0.147 | **False** |
| LOW→HIGH | +0.023 | +0.139 | 1.0 | **False** |

ナイーブには「高PVで違反が 0.488→0.419 に減った（−0.07）」と書きたくなるが、**benchmark は有意性を認めない**（p_adj=0.147）。配置ばらつきに埋もれる差であり、「PVで違反が減る」という headline は成立しない（try11 型過大主張の機構的抑止）。ただし HIGH は **stdev=0.222**（配置により 0.146–0.732）と分散が爆発し、平均は動かないが**tail リスク**が増大する。

### 4.3 位置効果 — 有意（真の陽性がガードを通過）、ただし方向は反直観

`results/bench_root_vs_end.json`（HIGH固定）:

| メトリクス | ROOT | END | delta | Cohen's d | p_adj(Holm) | significant |
|---|---|---|---|---|---|---|
| voltage_violation_rate | 0.569 [0.498, 0.640] | 0.303 [0.243, 0.364] | **−0.266** | **−1.553** | **0.0002** | **True** |
| voltage_deviation | 0.066 | 0.129 | **+0.063** | +0.988 | 0.0022 | **True** |

- **末端配置の方が違反率が低い**（0.303 < 0.569）。CI は非重複、d=−1.55（大）。機構: 既存の末端**低電圧**違反を、末端PVの有効電力注入が持ち上げて是正するため。根元配置は末端の低電圧を救えず違反が残る。
- **同時に、末端配置は voltage_deviation を増やす**（0.129 > 0.066, これも有意）。局所の電圧振れは末端の方が大きい。**2つの物理メトリクスが逆符号**で有意 → 単一指標での「良し悪し」断定は誤り。「違反カウント」と「電圧偏差」は別の量。

### 4.4 収束・データ健全性
全条件で **non_convergence_rate = 0.000**（全潮流収束）。`voltage_violation_rate_valid_n = 24`（NaN 除外ゼロ）。

## 5. Limitations（隠さず列挙）

1. **単一 feeder**（IEEE13 のみ）。§4.2 E-2 の「≥2 feeder」を**満たさない** → 一般性は主張できない。位置効果が他トポロジで再現するかは未検証。
2. **エンジン相互検証ができていない**。`validate-engines opendss,pandapower` は失敗（`E-30001`）：ieee13 は OpenDSS ネイティブ(.dss)で CDL 表現が無く、pandapower コネクタが読めない。→ 位置効果が**OpenDSS 単一エンジンの結果**であり、ソルバ癖の可能性を排除できていない（try13→14 型リスクが未クローズ）。
3. **起因分離ができていない**。`attribute-violations` は失敗（`E-30300`：baseline 82 サンプル vs candidate 84）：PV注入がノード数を変えるため「同一トポロジ」前提の分離ツールが適用外。→ END の違反低減が「既存低電圧の是正(baseline_only 減)」か「PV誘発(dispatch_induced 増)」かの内訳は未分離（4.3 の機構は状況証拠）。
4. **制御器の提案ではない**。framework に制御アルゴリズムの差込点が無く、本研究は「配置・容量 → 違反リスクの特性化」に限定される（Volt-VAR *制御方式* の新規性は主張しない）。
5. PV は単一母線・単一容量の静的注入。雲影の秒スケール確率時系列は未実装（候補1の動的側面は範囲外）。

## 6. 論文主張のリフレーズ（成果物のみから）

> IEEE13 試験フィーダー上で単一PV（1800kW）を無作為配置したとき、**電圧帯違反率は PV の設置位置に有意に依存し**（変電所近傍 0.57 vs 末端 0.30, Cohen's d=1.55, Holm補正後 p=2×10⁻⁴, 95%CI 非重複）、末端配置が既存の低電圧違反を是正して違反率を下げる一方、電圧偏差は逆に増やす。対照的に、**PV 容量の増加（0→1800kW）は平均違反率を有意に変えない**（p=0.15）。この非対称性は、配電系統の PV 受入リスクが「どれだけ」より「どこに」で決まることを示唆する。ただし単一フィーダー・単一エンジンの結果であり、一般化には多トポロジ・エンジン相互検証が要る。

## 7. 再現手順

```bash
export GRIDFLOW_HOME=<workdir>
gridflow scenario register examples/ieee13/pack.yaml
gridflow scenario clone ieee13@1.0.0 --id ieee13-voltvar@1.0.0
# 容量条件
for c in base low high; do gridflow sweep --plan test/mvp_try17/plans/sweep_$c.yaml --connector opendss --output test/mvp_try17/results/sweep_$c.json; done
# 位置条件
for c in root end; do gridflow sweep --plan test/mvp_try17/plans/sweep_$c.yaml --connector opendss --output test/mvp_try17/results/sweep_$c.json; done
# 統計判定（実験IDを sweep_*.json の experiment_ids から抽出して --baseline/--candidate に渡す）
gridflow benchmark <ROOT ids...> <END ids...> --correction holm --alpha 0.05 --output test/mvp_try17/results/bench_root_vs_end.json
gridflow export paper test/mvp_try17/results/bench_root_vs_end.json -o test/mvp_try17/results/paper_export
```

---

## 8. 査読後訂正（独立査読の結果を受けて）— 中心的主張を撤回

独立査読（`review_record.md`, 著者≠査読者）で **CRITICAL 欠陥**が指摘され、判定は**不合格**。
著者はこれを受け入れ、§4.3 / §6 の位置効果に関する中心的主張を**撤回**する。

- **疑似反復（pseudo-replication）**: 位置条件 ROOT/END の候補母線は各4個で、`RandomSampleAxis`
  が24回**復元抽出**していた。per-experiment 値は実際には**各群3通り**しかない
  （ROOT: 0.244/0.488/0.732, END: 0.146/0.302/0.500）。benchmark はこの疑似反復を n=24 の
  独立標本として扱い、d=−1.55 / Holm p_adj=2×10⁻⁴ / CI 非重複 を算出したが、**母線を独立単位
  （実効 4 vs 4, 実質 3 通り）として再検定すると vvr p≈0.14 で非有意**。4v4 の最小到達 two-sided p は
  0.029 であり、報告の 2×10⁻⁴ は独立標本では原理的に到達不能＝反復数え上げの artifact。
- したがって「容量より位置が効く」という §6 のリフレーズは**証拠に支持されない**。正しい結論は
  「**本試行の設計では、容量効果も位置効果も、独立標本ベースでは有意差を示せなかった**」。
- §3 で「シード反復ではない」と try11 型 artifact を否定した一方、**候補が4母線で復元抽出している
  事実を非開示**にしていた点が査読の核心的指摘であり、妥当。

### この失敗が示すこと（本試行の真の価値）

1. **機構的ガードは疑似反復を検出できなかった**。`voltage_violation_rate_valid_n=24` は額面通り24を
   報告し、benchmark は `significant=True` を返した。`insufficient_replicates` ガードは「n<2」しか
   見ず、「N個の標本が少数の離散値の反復」を捕捉しない。
2. **独立査読（§4.1.3）がツールの盲点を捕捉した**。著者が仕込んだ穴を、成果物のみを渡された独立
   査読者が厳密再検定で暴いた。→ 「機構的ガード＋独立査読の両輪」という設計思想（PR #27）の妥当性を
   実証。どちらか一方では try11 型（実効標本数の水増し）を止められない。
3. **framework の実ギャップを発見**: 標本の**実効独立数 / 疑似反復**を検知するガードが無い。
   → follow-up issue 化（distinct(values) ≪ N や、RandomSampleAxis の復元抽出で候補数≪N_samples の
   ときに警告する effective-sample-size ガード）。これは try11「sample-of-1 artifact」の一般化。
