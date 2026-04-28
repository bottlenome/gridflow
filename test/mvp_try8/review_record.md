# try8 仮想査読レビュー記録

レビュー実施日: 2026-04-28
レビュー方針: `docs/mvp_review_policy.md` v0.4 に準拠 (Phase 2 ゼロベース)
レビュアー: 仮想査読者 (gridflow プロジェクト査読プロセス)
対象: `test/mvp_try8/report.md` (commit `e4e0f59`) + 同 `results/`

---

## 1. 論文主張のリフレーズ

> **判定: リフレーズ不能**

レポートを読んでも「論文の骨格」が再構成できない。理由は以下:

- **課題**: レポート §1「Phase 2 v0.3 で実装した 4 機能 + M5 が end-to-end に動作することを実証する」 — これは **ツールの動作確認** であり、研究課題ではない。`docs/research_landscape.md` の C-{連番} 課題への参照もない
- **先行研究**: 引用文献ゼロ。先行 HCA 研究との差分がない
- **方法（提案手法の価値）**: gridflow 機能 (§5.1.1, §5.1.2, §5.1.3, M5) の動作確認 — **gridflow 自体が題材**であり、§3.1「gridflow 自体を contribution として主張禁止」に正面から違反
- **実験結果**: 4 children sweep + 11-grid sensitivity (n=4)。MVP review policy §4.2 E-2 が要求する **n≥1000** に対し 1/250
- **考察**: 「機能が動いた」以上の domain knowledge への接続なし

仮にこれを論文 Abstract に書くなら:

> "We validated the gridflow framework's Phase 2 v0.4 features, including
> per_experiment_metrics column form, axis-target sweep, and the
> SensitivityAnalyzer. The framework correctly produced bit-faithful CDL
> round-trips and computed sensitivity curves over 11 threshold points."

これは §3.1 が `❌ "We propose gridflow, a framework for..."` として明示的に禁止している形そのもの。

---

## 2. 総合判定

### **不合格** (§4.3)

判定理由:
- **A 不合格 (CRITICAL)**: §4.2 A `gridflow 自体を論文 contribution に含めない` 規則違反 — レポート全体が gridflow の機能テストとして書かれている
- A 不合格時点で B/C/D/E の評価有無を問わず不合格 (§4.2 A 「これが不合格なら他の観点を問わず不合格」)

## 3. 指摘事項

### CRITICAL

| # | 指摘 | レポート該当 | 根拠 |
|---|---|---|---|
| **C-1** | レポート §1〜§7 通して **gridflow 自体が検証対象** であり、ドメイン研究成果としての contribution が存在しない | §1「4 機能 + M5 が end-to-end に動作することを実証」 §4「4 機能の動作実証サマリ」 | §3.1 違反。`We propose gridflow, a framework for...` の禁止例にほぼ一致 |
| **C-2** | 課題出典が **`research_landscape.md` の C-{連番} ではなく `docs/phase1_result.md` §5.1**。これは設計書の Phase 2 持ち越し項目であり、査読つき論文の Future Work ではない | §1「Phase 2 v0.3 で実装した 4 機能」 | §2.1 違反 (課題出典は査読論文の Future Work セクションでなければならない) |
| **C-3** | Phase 0.5 アイデア創出プロセスが実施されていない | レビュー記録 / 計画書なし | §2.5 違反 (Phase 1 実験前に必須) |

### MAJOR

| # | 指摘 |
|---|---|
| **M-1** | 実験規模 n=4 child experiments + 11 grid points。§4.2 E-2 が要求する **n≥1000** の 0.4%。Monte Carlo CI が定義できず、実際 bootstrap_n=50 でも CI 幅が全点 0 (= small-sample artefact) |
| **M-2** | 自作 4 バスフィーダー使用。§4.2 E-2 が要求する **IEEE PES 標準テストフィーダー** (IEEE 13/34/37/123) ではない |
| **M-3** | 単一フィーダーのみ。方法論論文では §4.2 E-2「2 フィーダー以上必須」 |
| **M-4** | 先行研究との比較ゼロ。§4.2 E-1「少なくとも 2-3 本の先行 HCA 研究と定量比較」未実施 |
| **M-5** | 論文ドラフト材料 (Title / Abstract / 図キャプション / Limitations) が §3.3 要求どおりの形で記載されていない。レポートには **動作確認結果テーブル**しかない |
| **M-6** | OpenDSS は本環境未インストールのため CDL → DSS は **script 生成だけ**で動作確認をスキップ。レポート §5 にこれを書いているが、cross-solver 検証 (§5.1.3 の本来の動機) を満たせていない |

### MODERATE

| # | 指摘 |
|---|---|
| **m-1** | レポート §3 Section 3a で「物理的妥当性: 両閾値とも 0 (= 期待通り)」と書いているが、これは **プロット/分布の幅が小さすぎる** 結果であって metric の有意性を示していない (= 機能が動いたことを 0 でも確認できるという意味でしかない) |
| **m-2** | bootstrap CI 幅 0 を「設計通り」と書いているが、**設計通りに動いている=主張の根拠が弱い**。CI が縮退するサンプル設計を最初から避けるべき (§4.2 E-3 「収束分析」未実施) |
| **m-3** | 「総実行時間 1.18 秒」を成果としてレポート §3 に記載しているが、これは **n=4 だから速いだけ**。スケーラビリティ証拠としては逆に弱い |
| **m-4** | レポート §6「§5.1.1〜§5.1.3 の MVP gap は閉塞済み」 — gridflow 内部の言語であり、ドメイン研究の言葉ではない |

### MINOR

| # | 指摘 |
|---|---|
| **n-1** | レポート §3「OpenDSSTranslator.from_canonical → 663 chars」 — 文字数は実証の根拠として弱い (構文的に正しい ≠ 数値的に正しい) |
| **n-2** | レポート §6 が結論と称しているが、研究成果ではなくテスト合格報告 |

## 4. 「動くか」と「研究になるか」のギャップ

レポート §1〜§4 が示しているのは **"the framework runs"**。MVP review policy §0 が問うのは **"the researcher publishes"**。両者は別の問い:

| 軸 | try8 が示したこと | review policy が要求すること |
|---|---|---|
| ツール側 | API が動く・型が一致・JSON が round-trip | (要求されていない) |
| 研究側 | (示されていない) | n≥1000 / 標準フィーダー / 先行研究比較 / 非自明な metric |

**try8 は「ツール ε 受入テスト」としては妥当だが、MVP review policy 上の MVP 検証としては成立しない。**

## 5. 修正提案 (try9 の方針)

§4.4 の優先度付きで:

### Priority 1 (この MVP 検証を成立させるための最小要件)

1. **論文の主張を Phase 0.5 で先に決める** — Rule 1〜6 (10 アイデア + ordinary persona + 隣接分野 + extreme user + 矛盾解決 + fixation 監視) を実施
2. **課題出典を `research_landscape.md` から選び直す** — C-{連番} の Future Work から
3. **gridflow を方法論ではなく実験基盤として位置付け直す**:
   - ❌ "We validated gridflow's per_experiment_metrics column form."
   - ✅ "We performed n=1000 stochastic HCA on IEEE 37 and showed that the
        Range A vs Range B regulatory choice changes hosting capacity by
        X% — observed across both OpenDSS and pandapower (cross-solver
        validation, Methodology section)."

### Priority 2 (実験規模)

4. **n≥1000** に増やす (現在 n=4 → 250 倍)
5. **IEEE PES 標準フィーダー** (IEEE 13 を使うか 37 にスケールアップ)
6. **2 フィーダー以上**で同方法論を回す

### Priority 3 (科学的健全性)

7. 先行 HCA 研究 2-3 本との **定量比較** (DOI 付きで research_landscape に追加)
8. 収束分析 (n=100, 200, 500, 1000)
9. **CI 幅が縮退しないサンプル設計** (= bootstrap が意味を持つ n を満たす)
10. 単一の swept パラメータへの感度分析を 1 本含める

### Priority 4 (論文材料)

11. **論文ドラフト材料** (§3.3) を report.md 末尾に必須セクションとして追加: Title, Abstract, 主張, 図キャプション 4 枚分, Limitations
12. **review_record.md の §4.5 リフレーズ 5 項目**が再構成可能なレポート文章にする

## 6. プロセス上の自己反省 (try8 を作った側へのフィードバック)

ユーザーの「MVP 検証に移ってください」を **`docs/mvp_review_policy.md` を読まずに** ツール受入テストとして解釈してしまった。`docs/mvp_review_policy.md` は明示的に「MVP 検証は論文が書けるかを問う」と §0 で宣言している。事前に policy を確認する手順を踏まず、結果として review policy §3.1 に正面衝突するレポートを成果物としてコミットした。

CLAUDE.md §0.5.3 自問テンプレート違反でもある:

> 「正解のある問いか」 → ✅ MVP 検証の正しい形は `mvp_review_policy.md` に書いてある
> 「自分で導けない理由」 → policy を読んでいなかった (= 設計書深度ではなく **読解不足**)
> → 設計書を「先に読む」べきだった

この種の見落としは将来の MVP try で再発しうる。CLAUDE.md か README に「MVP 検証実施前に必ず `docs/mvp_review_policy.md` を読む」を明示する preprocess hook の追加を提案する。

## 7. 結論

**try8 は MVP review policy に照らして不合格 (CRITICAL ×3 / MAJOR ×6)。**

Phase 3 (プロダクトオーナー最終レビュー) では:

- このレポートを **MVP 検証として承認しない**
- try9 を §5 の Priority 1〜4 に従って再計画する
- ただし **try8 のスクリプト・結果・テストコードはツール側の受入確認として有用**であり、ツール CI 経路として `tests/spike/` 相当に格下げ移設する選択肢はある (削除でも残置でもなく、**用途を再定義する**)
