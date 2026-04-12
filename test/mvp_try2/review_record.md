# MVP try2 report.md — 査読レビュー記録

## 論文主張のリフレーズ

- **課題**: DER の Hosting Capacity Analysis (HCA) は研究者ごとにソルバー・指標定義・掃引手法がバラバラで、再現・比較ができない
- **先行研究**: 既存 HCA 研究はソルバー固有スクリプトで完結。FAIR データ原則はあるが計算ワークフロー層の再現性は未保証。OpenDSS と pandapower を横断した系統的 HCA 比較フレームワークは存在しない
- **方法（提案手法の価値）**: OSS フレームワーク gridflow を提案。SweepPlan + Connector Protocol でソルバーと実験を分離し、カスタム指標 Plugin・plan_hash プロビナンス・deterministic seed による再現性を実現 → **gridflow 自体が contribution になっており §3.1 違反**
- **実験結果**: 200 random PV 配置 x 2 solver (IEEE 13 / OpenDSS + 7-bus MV ring / pandapower) で 400 実験を 54 秒で完走。hosting_capacity_mw_mean 差 ~6%
- **考察**: workflow-level 再現性が HCA 研究の missing ingredient だと主張。ただし異トポロジ比較であり physics-level の cross-validation ではないと自認

---

## 総合判定: 不合格

**理由: MVP 検証方針への根本的違反**

本レポートの論文ドラフト (§4.2 Abstract) は gridflow 自体を提案手法として主張している:

> "We propose a workflow-level cross-solver approach ... via the open-source **gridflow** framework."

MVP 検証の目的は「gridflow を使った研究者が、gridflow に言及せずとも成立する
ドメイン論文を書けるか」を確認することである（`docs/mvp_review_policy.md` 参照）。
ツール自体を論文の contribution に含めることは検証方針に違反しており、
**レポートの内容品質に関わらず不合格**とする。

仮にこの方針違反がなかったとしても、以下の個別指摘（CRITICAL x2, MAJOR x2,
MODERATE x3, MINOR x2）により現状では論文材料として使用不可。

---

| 項目 | 値 |
|---|---|
| レビュー実施日 | 2026-04-12 |
| 対象ファイル | `test/mvp_try2/report.md` |
| レビュー方式 | 全成果物（JSON, PNG, スクリプト, sweep plan YAML, ソースコード）との照合 |
| 総合判定 | **不合格** — MVP 検証方針違反 + 複数の CRITICAL/MAJOR 指摘 |
| レビュー方針 | `docs/mvp_review_policy.md` |

---

## 1. CRITICAL 指摘

### 1.1 レポート §2.4 の runtime 数値が JSON と一致しない

| 指標 | レポート記載値 | JSON 実値 (`results/sweep_pandapower.json`) |
|---|---|---|
| pandapower runtime_mean | 0.6213 | **0.2368** |
| delta | +0.6094 | +0.2245 |
| relative | +98.07% | +94.8% |

`results/sweep_pandapower.json` の `runtime_mean` は `0.23681581626998877`。
レポートの `0.6213` の出典が不明。論文材料として使う前提であるため致命的。

### 1.2 hosting_capacity_mw_max の「0.00% 一致」はアーティファクト

両 solver で `hosting_capacity_mw_max = 1.9900994293629632` が完全同一だが、
これはクロスソルバー合意の証拠ではない。

- 両 sweep plan の `pv_kw` 軸が **同一 seed=200, n_samples=200, uniform(100, 2000)**
  → 生成される 200 個の pv_kw 値が全く同じ
- `HostingCapacityMetric.calculate()` は「電圧違反なし → pv_kw/1000」を返す
- max は「200 個中の最大 pv_kw 値のうち電圧違反しなかったもの」
- 両ネットワークとも最大 pv_kw (~1990 kW) を受容しただけ

共有 seed の trivial な帰結であり、物理的にも方法論的にも意味のない一致。
論文に引用すると cross-solver agreement と誤読される。

---

## 2. MAJOR 指摘

### 2.1 DoD #2「bit-identical rerun」は自己申告で未検証

レポート記載:
> ✅ (deterministic seeds, runtime PV insertion は固定 cmd)

括弧内は「なぜ bit-identical であるべきか」の設計意図であり、検証結果ではない。
2 回目の実行・JSON diff の痕跡なし、検証スクリプトも存在しない。

try1 では `numpy.array_equal` で明示的に検証していたのに、try2 では退行。
単体テスト (`test_reproducibility`) は存在するが、sweep 全体の E2E 再現テストは未実装。

### 2.2 異トポロジ比較で DoD #4「≤10% 差」を主張する妥当性

| | OpenDSS (IEEE 13) | pandapower (MV ring) |
|---|---|---|
| ノード数 | 13 | 7 |
| 電圧レベル | 4.16 kV | 20 kV |
| voltage_deviation_mean | 0.0500 pu | 0.0056 pu |
| hosting_capacity_mw_min | 0.0 (reject あり) | 0.1037 (reject なし) |

voltage_deviation が **10 倍** 異なる 2 ネットワークでの hosting_capacity_mean 差
5.95% に、cross-solver 合意としての意味はほぼない。
pv_kw 入力分布が同一（同 seed）であるため、出力 mean がある程度近いのは統計的に当然。

§4.5 Limitations で「methodology-level であり physics-level ではない」と注記しているが、
DoD #4 の ✅ と矛盾。DoD が要求するのは「ソルバー間の数値一致」であり、
「異なるネットワークでワークフローが動く」ではない。

---

## 3. MODERATE 指摘

### 3.1 図とスクリプトの「IEEE 30」ラベルが誤り

| ファイル | 箇所 | 記載 | 実態 |
|---|---|---|---|
| `plot_stochastic_hca.py` | L41 | `"pandapower\n(IEEE 30)"` | simple_mv_open_ring_net (7-bus) |
| `run_cross_solver.sh` | L53 コメント | `IEEE 30` | 同上 |
| `stochastic_hca.png` | 軸ラベル | `pandapower (IEEE 30)` | 同上 |
| `ieee30_pp_sweep_base.yaml` | ファイル名 | `ieee30` | 中身は MV ring |

pack YAML のコメントに「case_ieee30 はベースラインが 1.08 pu 超で使えないため MV ring
を選択」と明記されており、ファイル名がリネーム漏れした名残り。
論文図に転用すると factual error。

### 3.2 比較スクリプトの relative_delta 計算が非標準

`compare_solvers.py:35`:
```python
denom = max(abs(av), abs(bv))
```

分母に `max(|a|, |b|)` を使用。通常の学術論文では baseline 基準 (`|a|`) が一般的。

- 本スクリプト: 0.0604 / 1.0159 = **5.95%**
- baseline 基準: 0.0604 / 0.9555 = **6.32%**

どちらも DoD の 10% 閾値は満たすが、計算方法を論文で明示する必要あり。

### 3.3 OpenDSS の hosting_capacity_mw_min = 0.0 の非対称性が未議論

OpenDSS 側では一部の PV 配置が完全 reject（min = 0.0）、
pandapower 側は全配置 accept（min = 0.1037）。
2 ネットワークの voltage headroom が根本的に異なることを示すデータだが、
レポートで議論されていない。

---

## 4. MINOR 指摘

### 4.1 Abstract の "95% Range B confidence" は用語混同

Range B は ANSI C84.1 の電圧規格（0.90-1.06 pu）であり、統計的 confidence level ではない。
"95%" がどこに掛かるか不明確。

### 4.2 child experiment JSON の永続化

レポートは「`~/.gridflow/results/<exp_id>.json` に永続化済み」と主張。
`SweepOrchestrator._persist_child_result()` の実装は確認済みだが、
テスト環境上に実ファイルが存在するかは未確認（一時ディレクトリの可能性）。

---

## 5. 合格項目

| 項目 | 判定 | 根拠 |
|---|---|---|
| 成果物の存在 | **合格** | JSON x3, PNG x1, スクリプト x4 全て存在 |
| SweepOrchestrator 実装品質 | **良好** | frozen dataclass, Protocol, plan_hash, child persistence |
| SweepPlan 展開ロジック | **良好** | cartesian x zipped-random, seed 決定性 |
| StatisticsAggregator | **良好** | mean/median/min/max/stdev の標準集計 |
| HostingCapacityMetric Plugin | **良好** | Protocol 準拠、Range B デフォルト、kwargs でカスタマイズ可能 |
| E2E ワークフロー | **合格** | register → sweep → compare → plot が sh 1 本で完走 |
| experiment_ids 件数 | **合格** | OpenDSS 200 + pandapower 200 = 400 件 |

---

## 6. 修正提案の優先度

| 優先度 | 内容 | 影響範囲 |
|---|---|---|
| P0 | §2.4 runtime 数値を JSON 実値に修正 | report.md |
| P0 | hosting_capacity_mw_max の 0.00% を「共有 seed artifact」と注記 | report.md |
| P1 | DoD #2 を「未検証」に変更するか、rerun + diff を実施 | report.md / 新スクリプト |
| P1 | DoD #4 の ✅ 判定を再検討（cross-topology disclaimer を明確化） | report.md |
| P1 | 「IEEE 30」ラベルを全箇所で「MV ring (7-bus)」に修正 | plot, sh, yaml, png |
| P2 | relative_delta の計算方法を明示 | compare_solvers.py / report.md |
| P2 | hosting_capacity_mw_min = 0 の非対称性を §4.5 で議論 | report.md |
| P3 | Abstract の "95% Range B confidence" 文言を修正 | report.md |

---

## 7. 結論

gridflow のエンジニアリング（sweep → aggregate → persist → plot パイプライン）は
well-built であり、MVP としてのインフラ品質は十分。

しかし report.md が claim している科学的意味は、成果物の実態に対して over-stated。
数値の転記ミスが複数あり、論文ドラフト材料としてそのまま使うのは危険。

**推奨アクション**:
1. 上記 P0/P1 修正を report.md に適用
2. 同一トポロジ（IEEE 13 を両 solver で解く）での cross-solver 実行を Phase 2 で計画
3. DoD #2 の検証スクリプトを追加
