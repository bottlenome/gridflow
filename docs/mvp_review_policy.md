# MVP 検証方針 (MVP Review Policy)

本ドキュメントは gridflow の MVP 検証プロセス全体の方針を定義する。
個々の MVP シナリオ定義 (`mvp_scenario*.md`) や実験レポート (`test/mvp_try*/report.md`)
よりも上位のルールであり、全フェーズに適用される。

---

## 0. 検証の目的

gridflow の MVP 検証は、以下の問いに答えることを目的とする:

> **gridflow を使った研究者が、ドメイン研究の査読論文を書けるか？**

「gridflow が動くか」ではなく、「gridflow を使って得られた研究成果が
論文として成立するか」を検証する。

---

## 1. 検証フローの全体像

```
Phase 0: 課題収集
    ↓
Phase 1: 仮想研究者による MVP 実験
    ↓
Phase 2: 仮想査読者によるレビュー
    ↓
Phase 3: プロダクトオーナーによる最終レビュー
```

---

## 2. Phase 0 — 課題収集

### 2.1 課題の出典要件

- 課題は **査読つき論文の「将来課題 (Future Work)」セクション** から収集すること
- ブログ記事、ホワイトペーパー、自己定義の課題は不可
- 収集した課題は `docs/research_landscape.md` に論文引用つきで記録する

### 2.2 課題の記録形式

各課題は以下を含む:

| 項目 | 内容 |
|---|---|
| 課題 ID | C-{連番} |
| 出典論文 | 著者, タイトル, ジャーナル/会議, 年, DOI |
| 原文引用 | Future Work セクションからの引用 |
| gridflow との関係 | direct / indirect / out-of-scope |

---

## 3. Phase 1 — 仮想研究者による MVP 実験

### 3.1 最重要ルール: gridflow 自体を論文の主張に含めない

**MVP 実験で作成するレポート・論文ドラフトにおいて、gridflow 自体を
提案手法 (contribution) として主張することを禁止する。**

gridflow は「研究を行うためのツール」であり、「研究の成果物」ではない。
論文の contribution は、gridflow を使って得られたドメイン知見
（例: HCA の cross-solver 比較結果、指標の統計的性質）でなければならない。

#### 許可される言及

- Methodology / Experimental Setup セクションでツールとして言及:
  - "Simulations were orchestrated using an open-source workflow tool."
  - "Parameter sweeps were automated with deterministic seed control."
- 再現性の担保として付記:
  - "All experiment configurations and results are version-controlled and reproducible."

#### 禁止される言及

- Abstract や Contribution で gridflow を提案:
  - ❌ "We propose gridflow, a framework for..."
  - ❌ "The main contribution is the gridflow framework..."
- gridflow のアーキテクチャや設計を論文の本体で議論:
  - ❌ "gridflow separates concerns via Connector Protocol..."

### 3.2 ディレクトリ規則

```
test/
└── mvp_try{N}/
    ├── README.md               # シナリオ概要・実行手順
    ├── report.md               # 実験レポート（論文ドラフト材料含む）
    ├── packs/                  # ScenarioPack 定義 (YAML + ネットワークファイル)
    ├── sweep_plans/            # SweepPlan 定義 (YAML)
    ├── tools/                  # 補助スクリプト (run_*.sh, metric plugin, plot, compare)
    ├── results/                # 生成成果物 (JSON, PNG)
    │   └── .gitkeep
    └── review_record.md        # Phase 2 レビュー結果（レビュー後に追加）
```

### 3.3 レポート (report.md) の要件

- シナリオ概要と実験条件
- ステップ別の実行結果（コマンド・出力・計測値）
- DoD (Definition of Done) チェックリストと判定
- 論文ドラフト材料（Title, Abstract, 図キャプション, Limitations）
- **数値は全て成果物 JSON から転記し、計算過程を明示する**
- **gridflow 自体を contribution として主張しないこと (§3.1)**

---

## 4. Phase 2 — 仮想査読者によるレビュー

### 4.1 レビューの原則

レビューは **ゼロベース** で行う。実験の実施経緯や開発の苦労は考慮しない。
成果物（JSON, PNG, スクリプト, ソースコード）と report.md の突き合わせのみで判定する。

### 4.2 レビュー観点

#### A. 方針適合性（前提条件、これが不合格なら他の観点を問わず不合格）

| チェック項目 | 判定基準 |
|---|---|
| gridflow 自体を論文 contribution に含めていないか | Abstract / Contribution に gridflow の提案・設計の議論があれば不合格 |
| 課題の出典が査読論文の Future Work か | research_landscape.md の引用を確認 |

#### B. 数値の信頼性

| チェック項目 | 判定基準 |
|---|---|
| レポートの数値が成果物 JSON と一致するか | 全数値を JSON と照合。転記ミスは CRITICAL |
| 統計指標の計算方法が明示されているか | relative delta の分母、信頼区間の定義等 |
| アーティファクト（共有 seed 等による見かけの一致）が識別されているか | 未識別なら CRITICAL |

#### C. 科学的妥当性

| チェック項目 | 判定基準 |
|---|---|
| 実験設計が主張を支持するか | 異トポロジ比較で cross-solver 一致を主張する等は不可 |
| DoD の判定が適切か | 未検証項目に ✅ をつけていないか |
| Limitations が十分か | 既知の制約を隠していないか |

#### D. 論文材料としての完成度

| チェック項目 | 判定基準 |
|---|---|
| 図のラベル・キャプションが正確か | ネットワーク名、単位、凡例の誤りがないか |
| 用語が正確か | 規格名と統計用語の混同等 |
| 再現手順が他者に追跡可能か | スクリプト 1 本で結果が再現できるか |

### 4.3 判定基準

| 判定 | 条件 |
|---|---|
| **合格** | A 合格 + B/C/D に CRITICAL/MAJOR なし |
| **条件付き合格** | A 合格 + MAJOR 1 件以下（修正計画つき） |
| **不合格** | A 不合格、または CRITICAL 1 件以上、または MAJOR 2 件以上 |

### 4.4 レビュー記録 (review_record.md) の形式

- **先頭に論文主張のリフレーズ** (後述 §4.5)
- 総合判定と理由
- 指摘は CRITICAL / MAJOR / MODERATE / MINOR の 4 段階
- 各指摘に「レポート記載値 vs 実値」の対比を含める
- 修正提案を優先度つきで列挙

### 4.5 論文主張のリフレーズ（レビュー記録の冒頭に必須）

レビュー記録の先頭で、レポートが主張する論文の骨格を以下の 5 項目で
**査読者自身の言葉で端的にリフレーズ**する。レポートの文面をコピーするのではなく、
成果物を読んだ上で「この論文は何を言おうとしているのか」を再構成する。

```
## 論文主張のリフレーズ

- **課題**: （この論文が解こうとしている問題は何か）
- **先行研究**: （既存研究の何が不十分で、どこにギャップがあるか）
- **方法（提案手法の価値）**: （課題に対してどういうアプローチを取り、何が新しいか）
- **実験結果**: （実験で何が示されたか — 数値で）
- **考察**: （結果から何が言え、何が言えないか）
```

このリフレーズにより以下を達成する:

1. **主張の明確化** — レポートが曖昧に書いている部分を査読者が言語化することで、
   主張と証拠のギャップが可視化される
2. **方針違反の早期検出** — 「方法」欄にツール自体が contribution として
   現れれば §3.1 違反が即座に判明する
3. **Phase 3 レビューの効率化** — PO はリフレーズだけ読めば論文の骨格を把握できる

---

## 5. Phase 3 — プロダクトオーナー最終レビュー

- Phase 2 のレビュー記録を確認
- MVP としての合否を最終判定
- 次の MVP try の方針を決定（修正再実行 / シナリオ変更 / Phase 2 実験計画等）

---

## 6. 更新履歴

| 日付 | 内容 |
|---|---|
| 2026-04-12 | 初版作成。MVP try2 レビューで判明した方針不在を受けて策定 |
