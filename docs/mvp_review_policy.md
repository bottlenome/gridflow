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
Phase 0.5: アイデア創出（AI 平均化回避プロセス）
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

## 2.5 Phase 0.5 — アイデア創出（AI 平均化回避プロセス）

### 2.5.1 背景: なぜこのフェーズが必要か

MVP try2-try7 の実践で、**AI (LLM) が出すアイデアは分布の平均に収束する**
という構造的問題が判明した。具体的には:

- try5: 「HC を閾値で平均する」(HCA-R) — 教科書的操作
- try7: 「HC 曲線の 50% 点を見る」(HC₅₀) — 普遍的手法の適用
- 全 try を通じて「HC(θ) curve 上の統計量の変奏」に fixate し、
  根本的に異なるアプローチが出なかった

この問題は LLM の構造的特性に起因する (arXiv:2602.20408):

| メカニズム | 内容 |
|---|---|
| **Fixation (固着)** | 最初に出した案に後続の案が引きずられる |
| **Knowledge Partitioning の欠如** | 人間は各人が異なる知識領域を持つが、LLM は全知識を平均化した単一分布から生成する |

### 2.5.2 アイデア創出ルール (全 6 条)

Phase 1 の実験に入る **前に** 以下のプロセスを実行する。
アイデアの質はこのフェーズで決まり、後段の実験・レビューでは回復できない。

#### Rule 1: AI に解を出させるな、候補を出させろ (HAI-CDP)

AI は **10 個以上のアイデア候補** を生成するだけにし、
**ranking も推薦もさせない**。人間が候補を読み、
**最も non-obvious なもの** を選択する。

根拠: AI が ranking すると「もっともらしい中央値」が選ばれる。
人間の選択眼が外れ値を拾う唯一のメカニズム (HAI-CDP, Cambridge Core 2025)。

```
❌ 悪い例: 「最適な HCA metric を提案して」
✅ 良い例: 「HCA の閾値依存を解決するアプローチを 10 個列挙して。
            ranking しないで。分野横断のものを含めて」
```

#### Rule 2: Ordinary Persona を使え

「電力系の専門家として考えて」ではなく、**無関係な職業の人格**
で考えさせる。有名イノベーター (Steve Jobs 等) も避ける。

根拠: ordinary persona は semantic space の distinct region に
anchor し、LLM の knowledge partitioning を人為的に再現する
(arXiv:2602.20408, fixation を 36% 削減)。

```
✅ 例: 「保険のアクチュアリーとして」「農業の品種改良者として」
        「交通渋滞を研究する都市工学者として」考えさせる
```

#### Rule 3: 段階を踏め — 解の前に問題構造を分析 (CoT)

「解を出す」前に以下の 4 ステップを強制する:

1. **問題構造の分析**: 何と何の間にどんな矛盾があるか
2. **隣接分野の列挙**: この問題構造が出現する他の分野を 5 つ以上挙げる
3. **アナロジー生成**: 各分野でこの問題がどう解かれているか
4. **最遠アナロジーの選択**: 最も「ありえない」分野からの転用を優先

根拠: CoT prompting は fixation を削減し (arXiv:2602.20408)、
段階的発散は convergent な回答を抑制する。

#### Rule 4: Extreme User から逆算しろ (IDEO)

「平均的な研究者」の需要ではなく、**極端なユーザー** の
ニーズから発想する。極端なユーザーの amplified needs は
平均的ユーザーには見えない制約やチャンスを顕在化させる。

```
✅ 例:
  - 「1000 フィーダーを毎日分析する utility のオペレーター」
  - 「10 年間 1 フィーダーだけを追跡する PhD 学生」
  - 「ANSI 規格改訂委員会の委員長」
  - 「DER を一切信用しない保守的な配電計画者」
```

#### Rule 5: 妥協を禁止しろ (TRIZ 矛盾解決)

Trade-off を受け入れず、**矛盾を同時解決する** 方法を探す。
「AかBか」ではなく「AもBも」を要求する。

```
❌ 「精度と速度のバランスを取る」
✅ 「精度を犠牲にせず速度を上げる方法は何か。
    両方を同時に達成する原理的な方法があるはず」
```

#### Rule 6: Fixation 打破 — 3 回連続で同方向なら強制転換

AI が提案したアイデアの系列を監視し、
**同じ方向の改善案が 3 回以上連続** した場合、
そのアイデア系列を**強制的に打ち切り**、
Rule 2 (別 persona) または Rule 3 step 2 (別分野) からやり直す。

```
例: try5 (HC curve の平均) → try6 (同 curve の 2-feeder 比較)
    → try7 (同 curve の 50% 点)
    = 3 回連続で「HC(θ) curve 上の統計量」 → 強制転換すべきだった
```

### 2.5.3 Novelty Gate (実験前の新規性審査)

アイデアが決まったら、**実験に入る前に** 以下の 6 項目で
新規性を審査する。1 つでも ❌ なら Rule 1 に戻る。

| # | チェック | 基準 |
|---|---|---|
| 1 | 既存 metric / 手法から自明に導けるか | 「パラメータの変更」「統計量の変更」だけなら ❌ |
| 2 | 先行文献に同等概念があるか | 同じ分野での先行があれば ❌ |
| 3 | 物理的に解釈可能か | 「平均を取った」等の数学的操作のみでは ❌ |
| 4 | "So what?" テストに耐えるか | 結果を 1 文で述べたとき、専門家が行動を変えるか |
| 5 | Cross-disciplinary insight があるか | 単一分野内の改善は novelty として弱い |
| 6 | 計算手法自体に innovation があるか | 命名 / 形式化 / 標準化提案のみは弱い。新しいアルゴリズム・モデル・理論があるか |

### 2.5.4 エビデンス (本ルールの根拠論文)

| 論文 | 知見 | 適用先 Rule |
|---|---|---|
| arXiv:2602.20408 (2025) "Examining and Addressing Barriers to Diversity in LLM-Generated Ideas" | LLM の fixation + knowledge partitioning 欠如を特定。CoT + ordinary persona で改善 | Rule 2, 3, 6 |
| arXiv:2409.04109 (2024) "Can LLMs Generate Novel Research Ideas?" (100+ NLP 研究者) | LLM ideas は novelty 高いが diversity 低い + feasibility 弱い。top decile には届かない | Rule 1 |
| CHI 2025 "Human Creativity in the Age of LLMs" | AI 支援で個人の creativity は上がるが collective diversity は下がる | Rule 1, 6 |
| Nature Sci. Rep. 2025 "Divergent creativity in humans and LLMs" | LLM は 0.28% しか top-tier creativity に到達しない。人間は 35 倍多い | Rule 1 |
| IDEO "Extremes and Mainstreams Design Toolkit" | Extreme user の amplified needs が non-obvious 解を導く | Rule 4 |
| TRIZ (Altshuller, 1946-) | 矛盾の妥協なき解決が breakthrough invention の核 | Rule 5 |
| Cambridge Core 2025 "Enhancing designer creativity through human-AI co-ideation" | HAI-CDP: AI は生成、人間は選択の役割分担が最も効果的 | Rule 1 |

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

#### E. 投稿先水準の査読基準（トップ学会 / ジャーナルへの適合性）

MVP 検証の目的は「gridflow を使った研究者が**査読論文を書けるか**」であり、
論文材料が想定投稿先の査読基準を満たすかを評価する。
本セクションは IEEE PES General Meeting を基準として策定した。
MDPI Energies / IEEE Access 等のよりアクセスしやすい venue では E の一部は
緩和されうるが、MVP としてはトップ学会水準で評価する。

##### E-1. 手法的新規性 (Novelty)

| チェック項目 | 判定基準 |
|---|---|
| 提案手法に先行研究との明確な差分があるか | 「再現可能にした」だけでは不十分。計算手法・指標定義・実験設計のいずれかに新規な工夫が必要 |
| 差分が自明でないか | パラメータの変更のみ (e.g. "we used Range B instead of Range A") は不十分。差分の影響を定量的に示す必要がある |
| 先行研究との比較が含まれるか | 少なくとも 2-3 本の先行 HCA 研究の手法・結果と定量比較すべき |

##### E-2. 実験規模 (Scale)

| チェック項目 | 判定基準 |
|---|---|
| Monte Carlo サンプル数は十分か | **n >= 1000** が最低ライン。信頼区間の収束を示すこと |
| テストフィーダーは標準的か | **IEEE PES 標準テストフィーダー** (IEEE 13/34/37/123) を使用。仮想・自作フィーダーのみは不可 |
| **フィーダー数は十分か** | **方法論 (metric) 提案論文では 2 フィーダー以上が必須**。提案指標の識別力を異なる特性のフィーダーで実証すること。1 フィーダーのみ (特に degenerate case のみ) は MAJOR |
| 時間粒度は適切か | ピーク 1 時刻のみは MODERATE 指摘対象。代表日 (24h) 以上が望ましい |
| 制約の網羅性 | 電圧制約のみは最低限。熱制約 (line loading) の追加が望ましい |

##### E-3. 科学的健全性 (Scientific Rigor)

| チェック項目 | 判定基準 |
|---|---|
| 交絡要因が分離されているか | 同一ソルバーでフィーダーを比較する、同一フィーダーで閾値を比較する等。複数変数の同時変更は MAJOR |
| 信頼区間・統計検定が示されているか | mean / stdev だけでは不足。95% CI、bootstrap CI、または Mann-Whitney 検定等を含むべき |
| 収束分析があるか | n=100, 200, 500, 1000 と増やしたときに metric がどう収束するかを示す図 |
| 感度分析があるか | 少なくとも 1 つのパラメータ (閾値、サンプル数、PV 容量範囲等) への感度 |

##### E-4. 実用的メッセージ (Practical Relevance)

| チェック項目 | 判定基準 |
|---|---|
| 配電事業者・研究者への actionable な知見があるか | 「HCA は topology に依存する」だけでは不十分。「何をどう変えると HCA がどれだけ変わるか」を定量的に示す |
| Policy implication が述べられているか | 例: 「Range A と Range B の選択が HCA 評価を N% 変える」等 |

##### E 判定

| 判定 | 条件 |
|---|---|
| **投稿可 (Top venue)** | E-1〜E-4 全項目に CRITICAL/MAJOR なし |
| **投稿可 (Tier 2 venue)** | E-1 の MAJOR 1 件以下 + E-2〜E-4 に CRITICAL なし |
| **投稿不可** | E-1 に CRITICAL、または E-2〜E-4 に CRITICAL 2 件以上 |

### 4.3 判定基準

| 判定 | 条件 |
|---|---|
| **合格** | A 合格 + B/C/D に CRITICAL/MAJOR なし |
| **合格 (Top venue)** | 上記 + E に CRITICAL/MAJOR なし |
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
| 2026-04-22 | §4.2 E (投稿先水準の査読基準) を追加。IEEE PES GM 水準での評価を try3 レビューで実施し、基準の不在が判明したため。§4.3 に「合格 (Top venue)」判定を追加 |
| 2026-04-22 | §4.2 E-2 に「フィーダー数」チェック項目を追加。try5 で単一 degenerate case のみの実証が MAJOR 指摘となった教訓を反映 |
| 2026-04-22 | §2.5 Phase 0.5 (アイデア創出) を新設。try2-try7 で AI のアイデアが分布の平均に収束した問題を受け、6 ルール + Novelty Gate を策定。根拠論文 7 本を引用 |
