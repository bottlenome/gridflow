# MVP try3 report.md — Phase 2 査読レビュー記録（第三者レビュー）

## 論文主張のリフレーズ

- **課題**: Stochastic HCA は個別フィーダー上では十分に研究されているが、トポロジの異なるフィーダー間で「同一 metric 定義」を適用した系統的比較は不足しており、metric 定義自体が論文ごとにバラバラなことがその一因
- **先行研究**: 既存 HCA 研究は単一ソルバー・単一フィーダーに閉じる。metric 計算式がコードとして公開・再利用可能な形で共有されたケースは稀。異トポロジ間での定量比較は報告が限られている
- **方法（提案手法の価値）**: hosting_capacity_mw を「全バス電圧が ANSI C84.1 Range B 内に収まる場合の PV 容量 (MW)、違反時は 0」として Python コードで形式定義し、2 フィーダー (IEEE 13 / MV ring 7-bus) にそれぞれ 200 ランダム配置で適用。metric 定義の再利用性と seed 制御による再現性を備えた比較基盤を提供
- **実験結果**: mean hosting capacity は 0.96 MW (IEEE 13) vs 1.02 MW (MV ring) で差 6.3%。一方で voltage deviation は 0.050 vs 0.006 pu で約 9 倍の差。min は 0.0 (IEEE 13, reject あり) vs 0.10 (MV ring, 全 accept)
- **考察**: aggregate な HC mean の 6.3% 差は小さく見えるが、背後の電圧余裕が桁違いに異なることが min / voltage deviation から判明する。aggregate 統計量だけではトポロジの影響を過小評価する可能性がある。ただしソルバーとトポロジの効果は交絡しており分離できない

---

| 項目 | 値 |
|---|---|
| レビュー実施日 | 2026-04-12 |
| 対象ファイル | `test/mvp_try3/report.md` |
| レビュー方式 | 全成果物 (JSON x4, PNG x1, スクリプト x5, sweep plan YAML x2, pack YAML x2) との照合 |
| レビュー方針 | `docs/mvp_review_policy.md` |
| レビュアー | Phase 2 仮想査読者（セルフレビューとは独立に実施） |

---

## 1. 方針適合性 (A)

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| gridflow 自体を論文 contribution に含めていないか | ✅ 合格 | Abstract (§4.2) に "gridflow" の語は出現しない。Contribution (§4.4) は metric 定義・トポロジ比較・再現性の 3 点で構成され、全てドメイン知見。§4.4 末尾の Note で「ツール自体は contribution ではない」と明示 |
| 課題の出典が査読論文の Future Work か | ✅ 合格 | C-1 (ScienceDirect, PMC 2024), C-2 (ScienceDirect 2025, MDPI 2020), C-3 (ScienceDirect 2025), C-4 (ScienceDirect 2025), C-10 (MDPI Energies 2023) — research_landscape.md で確認 |

**A 判定: 合格**

---

## 2. 数値の信頼性 (B)

### 2.1 レポート §2.4 の全数値と comparison.json の照合

| metric | report OpenDSS | JSON 実値 | 一致 |
|---|---|---|---|
| hosting_capacity_mw_max | 1.9901 | 1.99009942... | ✅ 4dp 四捨五入 |
| hosting_capacity_mw_mean | 0.9555 | 0.95545916... | ✅ |
| hosting_capacity_mw_median | 0.9445 | 0.94450103... | ✅ |
| hosting_capacity_mw_min | 0.0000 | 0.0 | ✅ |
| hosting_capacity_mw_stdev | 0.5836 | 0.58362862... | ✅ |
| voltage_deviation_max | 0.0558 | 0.05576345... | ✅ |
| voltage_deviation_mean | 0.0500 | 0.04997893... | ✅ |
| runtime_mean | 0.0128 | 0.01284591... | ✅ |

| metric | report pandapower | JSON 実値 | 一致 |
|---|---|---|---|
| hosting_capacity_mw_max | 1.9901 | 1.99009942... | ✅ |
| hosting_capacity_mw_mean | 1.0159 | 1.01587848... | ✅ |
| hosting_capacity_mw_median | 0.9797 | 0.97973993... | ✅ |
| hosting_capacity_mw_min | 0.1037 | 0.10367087... | ✅ |
| hosting_capacity_mw_stdev | 0.5725 | 0.57254971... | ✅ |
| voltage_deviation_max | 0.0060 | 0.00599417... | ✅ |
| voltage_deviation_mean | 0.0056 | 0.00557509... | ✅ |
| runtime_mean | 0.2471 | 0.24707719... | ✅ |

| metric | report relative | JSON relative_delta | 一致 |
|---|---|---|---|
| hc_mw_mean | +6.32% | 0.06323589... (=6.32%) | ✅ |
| hc_mw_median | +3.73% | 0.03730954... (=3.73%) | ✅ |
| hc_mw_stdev | -1.90% | -0.01898281... (=-1.90%) | ✅ |
| vd_max | -89.25% | -0.89250704... (=-89.25%) | ✅ |
| vd_mean | -88.85% | -0.88845105... (=-88.85%) | ✅ |

**全数値が成果物 JSON と一致。try2 で CRITICAL だった runtime_mean 転記ミスは解消。**

### 2.2 統計指標の計算方法

- relative_delta の分母: "baseline (OpenDSS denominator)" と §2.4 で明示 ✅
- comparison.json に `"relative_delta_method": "baseline (OpenDSS denominator)"` あり ✅
- compare_solvers.py L36-38: `denom = abs(av) if abs(av) > 0 else abs(bv)` — ゼロ時フォールバックを実装 ✅

### 2.3 アーティファクト識別

- hosting_capacity_mw_max 0.00% を "shared-seed artifact" と §2.4 で明示的に注記 ✅
- メカニズム説明あり（同一 seed=200 → 同一 pv_kw 列 → 最大 pv_kw が両ネットワークで accept）✅
- plot の summary panel にも artifact 注記あり ✅

### 2.4 再現性検証の実データ確認

sweep_opendss.json vs sweep_opendss_rerun.json を直接照合:

| physics metric | run1 | rerun | 一致 |
|---|---|---|---|
| hosting_capacity_mw_max | 1.9900994293629632 | 1.9900994293629632 | ✅ bit-identical |
| hosting_capacity_mw_mean | 0.9554591625533196 | 0.9554591625533196 | ✅ bit-identical |
| voltage_deviation_mean | 0.04997893233006222 | 0.04997893233006222 | ✅ bit-identical |

runtime_mean: 0.01284... vs 0.01334... → wall-clock 変動 ✅ 想定通り

**B 判定: 合格** (CRITICAL/MAJOR なし)

---

## 3. 科学的妥当性 (C)

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| 実験設計が主張を支持するか | ✅ 合格 | 論文の主張は「トポロジが HCA 分布を支配する」。異トポロジ比較はこの主張の直接的な検証。try2 の「異トポロジで cross-solver 合意を主張」という問題は解消されている |
| DoD の判定が適切か | ✅ 合格 | DoD #2 は rerun + diff で実検証済み。DoD #4 は ⚠️ とし cross-solver 合意と主張しない。未検証項目に ✅ なし |
| Limitations が十分か | ✅ 合格 | 5 項目: (1) solver/topology 交絡, (2) shared-seed artifact, (3) PV モデル簡略化, (4) サンプルサイズ, (5) min=0 非対称性 |

**C 判定: 合格** (CRITICAL/MAJOR なし)

---

## 4. 論文材料としての完成度 (D)

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| 図のラベル・キャプションが正確か | ✅ 合格 | plot_stochastic_hca.py L44: "MV ring 7-bus, 20 kV" ✅。try2 の "IEEE 30" 誤りは解消。キャプション (§4.3) に shared-seed artifact 注記あり |
| 用語が正確か | ✅ 合格 | Range B = "ANSI C84.1 Range B (0.90-1.06 pu)" ✅。try2 の "95% Range B confidence" 混同は解消 |
| 再現手順が他者に追跡可能か | ✅ 合格 | `run_cross_solver.sh` 1 本で 6 ステップ (register → sweep x2 → rerun → compare → plot) が実行可能 |

**D 判定: 合格** (MINOR 2 件あり)

### MINOR 指摘

#### D-1: ヘッダーの "600 experiments" は検証 rerun を含む

レポートヘッダーに "600 experiments" と記載あるが、内訳は OpenDSS 200 + pandapower 200 + rerun 200。比較に寄与する実験は 400 件であり、rerun は再現性検証目的。"400 experiments + 200 rerun for verification" のほうが正確。

#### D-2: comparison.json の min relative_delta 分母フォールバック

comparison.json で hosting_capacity_mw_min の relative_delta = 1.0 (100%)。
OpenDSS baseline が 0.0 のため、分母が pandapower (0.1037) にフォールバックしている。
レポート §2.4 では relative を "-" と表記しており問題を回避しているが、
comparison.json と report の不一致が 1 箇所存在する。
compare_solvers.py のフォールバック挙動をコメントで注記すべき。

---

## 5. 総合判定

| 観点 | 判定 |
|---|---|
| A 方針適合性 | ✅ 合格 |
| B 数値信頼性 | ✅ 合格 (CRITICAL/MAJOR なし) |
| C 科学的妥当性 | ✅ 合格 (CRITICAL/MAJOR なし) |
| D 完成度 | ✅ 合格 (MINOR 2 件) |

### 総合判定: 合格

判定基準 (`mvp_review_policy.md` §4.3): A 合格 + B/C/D に CRITICAL/MAJOR なし → **合格**

try2 で指摘した全 9 件 (FATAL x1, CRITICAL x2, MAJOR x2, MODERATE x3, MINOR x2) が
適切に対応されている。科学的主張は実験設計と整合し、数値は全て成果物 JSON と
一致している。

---

## 6. 残存リスク (Phase 2 以降で対処推奨)

| 優先度 | 内容 |
|---|---|
| P2 | 同一ネットワーク cross-solver 検証 (CDL canonical input) で solver/topology 交絡を解消 |
| P2 | サンプルサイズ 500-1000 への拡大 + Monte-Carlo 誤差の信頼区間表示 |
| P3 | comparison.json の relative_delta ゼロ分母フォールバックのドキュメント化 |
| P3 | ヘッダーの experiment 数表記の明確化 (400 + 200 rerun) |
