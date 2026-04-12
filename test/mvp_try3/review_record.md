# MVP try3 report.md — 査読レビュー記録

## 論文主張のリフレーズ

- **課題**: DER の Hosting Capacity Analysis (HCA) は個別のフィーダー上で研究されるが、異なるネットワークトポロジ間での HCA 結果の系統的比較は限られている。metric 定義の不統一がその一因
- **先行研究**: 既存 HCA 研究は特定フィーダー + 特定ソルバーに閉じた解析が主流。ANSI C84.1 Range B に基づく再現可能な HCA metric 定義をコードレベルで共有した比較研究は見当たらない
- **方法（提案手法の価値）**: hosting_capacity_mw を「全バス電圧が Range B 内に収まる PV 容量 (MW)」として形式定義し、2 つのフィーダー (IEEE 13 / MV ring 7-bus) に同一定義で適用。トポロジが HCA 分布を支配する要因であることを定量的に示した
- **実験結果**: mean hosting capacity は 0.96 MW (IEEE 13) vs 1.02 MW (MV ring) で差 +6.3%。ただし voltage deviation は 0.050 vs 0.006 pu で 10 倍の差
- **考察**: aggregate な hosting capacity 差 (6.3%) は小さく見えるが、背後の電圧余裕は桁違いに異なり、min=0 (IEEE 13) vs min=0.10 (MV ring) という非対称が潜む。aggregate 統計量だけでは topology の影響を過小評価する

---

| 項目 | 値 |
|---|---|
| レビュー実施日 | 2026-04-12 |
| 対象ファイル | `test/mvp_try3/report.md` |
| レビュー方式 | 全成果物 (JSON x4, PNG x1, スクリプト x5, sweep plan YAML x2) との照合 |
| レビュー方針 | `docs/mvp_review_policy.md` |

---

## 1. 方針適合性 (A)

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| gridflow 自体を論文 contribution に含めていないか | ✅ 合格 | Abstract (§4.2) は metric 定義とトポロジ比較を contribution として記述。gridflow への言及なし。§4.4 Contribution も同様。§4.4 末尾の Note で「ツール自体は contribution ではない」と明示 |
| 課題の出典が査読論文の Future Work か | ✅ 合格 | research_landscape.md の C-1/C-2/C-3/C-4/C-10 を参照。全て査読論文からの引用 |

**A 判定: 合格**

---

## 2. 数値の信頼性 (B)

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| レポートの数値が成果物 JSON と一致するか | ✅ 合格 | §2.4 の全数値を comparison.json と照合。hosting_capacity_mw_mean: report=0.9555 vs JSON=0.9554591625533196 (四捨五入一致)。pandapower runtime_mean: report=0.2471 vs JSON=0.24707719600500297 (一致)。try2 で CRITICAL だった runtime_mean の転記ミスは解消 |
| 統計指標の計算方法が明示されているか | ✅ 合格 | relative_delta の分母を "baseline (OpenDSS)" と明記 (§2.4)。comparison.json にも `relative_delta_method` フィールドあり |
| アーティファクトが識別されているか | ✅ 合格 | hosting_capacity_mw_max の 0.00% 一致を "shared-seed artifact" と明示的に注記 (§2.4)。plot の summary panel にも artifact 注記あり |

**B 判定: 合格**

---

## 3. 科学的妥当性 (C)

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| 実験設計が主張を支持するか | ✅ 合格 | 論文の主張は「トポロジが HCA 分布を支配する」であり、異トポロジ比較はその主張に整合する。try2 では異トポロジ比較で cross-solver 合意を主張していたが、try3 ではフレーミングが修正されている |
| DoD の判定が適切か | ✅ 合格 | DoD #2 は rerun + diff で実検証済み。DoD #4 は ⚠️ (条件付き) とし、cross-solver 合意とは主張しない。未検証項目に ✅ は付いていない |
| Limitations が十分か | ✅ 合格 | 5 項目の Limitations を列挙。cross-topology vs cross-solver の区別、shared-seed artifact、PV モデル簡略化、サンプルサイズ、min=0 非対称性を全て議論 |

**C 判定: 合格**

---

## 4. 論文材料としての完成度 (D)

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| 図のラベル・キャプションが正確か | ✅ 合格 | plot で "MV ring 7-bus, 20 kV" と正しく表記。try2 の "IEEE 30" ラベル誤りは解消。キャプション (§4.3) で shared-seed artifact に言及 |
| 用語が正確か | ✅ 合格 | Range B を "ANSI C84.1 Range B (0.90-1.06 pu)" と正しく定義。try2 の "95% Range B confidence" 用語混同は解消 |
| 再現手順が他者に追跡可能か | ✅ 合格 | `run_cross_solver.sh` 1 本で全工程 (sweep + rerun + compare + plot) が実行可能 |

**D 判定: 合格** (MINOR 1 件あり)

### MINOR 指摘

#### D-1: comparison.json の hosting_capacity_mw_min の relative_delta が 1.0 (100%)

comparison.json で min の relative_delta が 1.0 と記録されている。これは
OpenDSS 側が 0.0 のため分母が pandapower (0.1037) にフォールバックした結果。
計算は正しいが、"baseline = OpenDSS" と表記しつつ実際には分母が切り替わっている
ケースが 1 件存在する。レポート §2.4 では min の relative を "-" と表記しており
問題を回避しているが、comparison.json 側の挙動は明記すべき。

---

## 5. 総合判定

| 判定 | 条件充足 |
|---|---|
| A 方針適合性 | ✅ 合格 |
| B 数値信頼性 | ✅ 合格 (CRITICAL/MAJOR なし) |
| C 科学的妥当性 | ✅ 合格 (CRITICAL/MAJOR なし) |
| D 完成度 | ✅ 合格 (MINOR 1 件) |

### 総合判定: 合格

try2 で指摘した全 9 件の問題 (FATAL x1, CRITICAL x2, MAJOR x2, MODERATE x3, MINOR x2)
が try3 で適切に対応されている。§3.1 違反は解消され、数値の信頼性が確保され、
科学的主張が実験設計と整合している。

---

## 6. 残存リスク (Phase 2 で対処推奨)

| 優先度 | 内容 |
|---|---|
| P2 | 同一ネットワークの cross-solver 検証 (CDL canonical input) |
| P2 | サンプルサイズ 500-1000 への拡大と Monte-Carlo 誤差の定量評価 |
| P3 | comparison.json の relative_delta 分母フォールバック挙動のドキュメント化 |
