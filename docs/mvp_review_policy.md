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

### 2.5.2 アイデア創出ルール (全 9 条)

実行順:
- **Rule 7 (乱数アンカリング)** — Rule 1 の前段
- **Rule 1〜6** — 候補生成と発散
- **Rule 8 (課題深掘り連鎖)** — 候補ごとに depth 確認
- **Rule 9 (TRIZ 遠隔ドメイン移植)** — Rule 5 を遠隔ドメイン縛りで強化

Rule 1-6 (生成系) のあとに Rule 7-9 (絞込・強制系) を回す並びでなく、
**Rule 7 が最先端**で、Rule 8/9 は Novelty Gate と並走する評価系。

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

#### Rule 7: 乱数アンカリング (Random Anchoring) — Rule 1 の前段

**Rule 1 (HAI-CDP) を実行する前に**、AI に **乱数列 + 強制連想ワード + 強制ドメイン** を
commit させ、その anchor から発想を開始させる。anchor は「もっともらしさ」で選ばない。

根拠: AI 単独 ideation は「中央値的に妥当な答え」へ収束する。乱数 anchor は
出発点を **意図的に非妥当** にすることで自己選択バイアスを破る。
人間の連想システムは制約された出発点から非自明な経路を辿る (de Bono の
ランダム入力法 [Lateral Thinking, 1970])。anchoring 効果 (Tversky &
Kahneman 1974) は「最初に置いた数値に判断が引かれる」現象だが、これを
**意図的に逆用**して「平均から離れた起点」を強制する。

```
❌ 悪い例:
  "EV 充電の novel 手法を 10 個出して"
  → AI は smart charging / V2G / dynamic pricing 等の中央値候補に収束

✅ 良い例:
  "乱数列 73, 11, 4 を思い浮かべ、強制連想ワード 'honeycomb',
   'ferment', 'mirror' を commit して、それぞれを EV 充電に
   むりやり射影してから 10 個出す"
  → "ferment" → 抗生物質耐性 → 選択圧 → endogenous demand HC、
    "honeycomb" → 結晶学 → 相転移 → percolation HC、等の
    中央値から外れた候補が出る
```

**適用法**:

1. ideation 開始前に乱数列 (8 個程度の数字)、連想ワード (5-8 個、領域
   横断的)、強制ドメイン (3-5 個、本問題から最も遠い分野) を **書き下す**
2. ranking や pre-screening をしない (= 一見不毛な anchor も commit)
3. 各 anchor を本問題に「むりやり」射影させ、出てきた連想を Rule 1 の
   候補集合に投入

**失敗パターン**:
- "ランダム" と称して実は系統的に選んでいる (= bias 残存)
- anchor を後から正当化するために事実誇張 (= post-hoc rationalisation)

#### Rule 8: 課題深掘り連鎖 (Problem Depth Chain S0→S8)

候補ごとに「**前段の課題 → 詳細化方向 → 出てきた新課題**」の連鎖を
S0 から S8 まで書き下し、S7 で手法が **強制** されるかを確認する。

| Step | 答えるべき問い | 失敗パターン |
|---|---|---|
| S0 | 何が観測される? どんな事象が起きている? | 抽象スローガン止まり |
| S1 | データ・観察値は? | 「揺れる」だけで数値なし |
| S2 | なぜ起きる? 物理 / 数式は? | "そういうもの" |
| S3 | 誰が困る? 困らない人は誰? | 仮想ユーザのみ |
| S4 | その人がいつ何を決める? | 「知見が得られる」止まり |
| S5 | 間違えたコストは? FN と FP の比は? | 単純精度競争 |
| S6 | 使える資源 / 使えない資源は? | 制約なし、何でもいい |
| S7 | 制約を満たす method は何通り? 1 通りなら強い | "ML を使います" 止まり |
| S8 | どんな evidence で当事者が行動を変える? 数値閾値は? | "性能を評価する" のみ |

**通過判定**:
- L7-L8 まで埋まり、かつ L7 で残った method が L1〜L6 のどれか **1 つ
  でも緩めると別 method に collapse する** こと
- 単に L8 まで埋めた "形" ではなく、**S6 制約が後付けでない** ことを
  自己テストで確認 (= "この制約は **なぜ** 必要か?" を 2 段以上
  さかのぼれること)

**根拠**: Rule 3 (4-step CoT) を発展させ、各 step に検証可能な basis を
持たせる。CoT prompting の fixation 削減効果 (arXiv:2602.20408) は
step が浅いと効かない。S0-S8 は最低保証の depth。

```
❌ 悪い例:
  S0 "HCA は不確実"
  S6 "制約: ML を使う" (← 制約でなく method 仮置き)
  S7 "ML には GNN を使う" (← S6 から自明に出る、強制力なし)

✅ 良い例:
  S0 "stochastic HCA が同一 feeder で variance=0 になる regime を観測"
  S6 "PF を 1 回も走らせてはならない (= 走らせたら判定の意味消失)"
  S7 "GNN-with-PF / surrogate / BNN は全部 S6 で消去、線形 + analytic
      ΔV の logistic regression のみ生存"
```

**失敗パターン**:
- S6 制約を method 一意化のために後付けで作る (= try10 v2 の私の失敗)
- S5 の cost 比を単位なしで書く ("FN は重い" のみ)
- S8 の数値閾値を stakeholder elicitation なしに勝手に設定する

#### Rule 9: TRIZ 遠隔ドメイン移植 (TRIZ Distant Transposition)

Rule 5 (妥協なし) を実行する際、解の参照を **本問題から domain distance
が大きい分野** に強制する。同分野 / 隣接分野からの組み合わせは
"既存技術の組合せ" として novelty が弱い。

**重要 (try10 の失敗教訓)**: 単一の遠隔ドメインを 1 つ持ってくるだけでは
不十分。**(a) 複数候補の比較** と **(b) invariant 保存の確認** を要する。

**適用法**:

1. 問題の抽象矛盾を 1 文に圧縮 (例: "個体性能向上 vs 集団同期共鳴回避")
2. TRIZ 矛盾マトリクスから推奨 inventive principle を抽出
3. その principle が観察される **遠隔ドメイン** (= 本問題と語彙
   共有が少ない分野) を 10 個以上列挙
4. 各遠隔ドメインの **機構そのもの** (= 名前ではなく動作原理) を
   本問題に射影
5. **複数候補 (≥ 3 個) を並列で抽象化**:
   各候補について以下を 2 sentence で書く
   - (a) 元ドメインで **保存される invariant** (mathematical /
     structural property)
   - (b) 移植先で **invariant が保存される条件** (target の
     constraint 構造下で本当に成立するか)
6. **Invariant 検査**: (a) と (b) の vocabulary を入れ替えて、
   **元ドメインの暗黙前提** (例: 個体同種性、目的関数の形) が
   移植先で **満たされるか** を確認
7. **元の暗黙前提が target で成立しないものは脱落**
8. 残った候補で **Rule 8 の S6-S7 で再強制テスト**
9. それでも複数残れば、stakeholder cost (Rule 8 S5) で 1 つに絞る

**try10 phyllotactic charging の失敗例 (本ルールの教訓元)**:

step 5 (複数並列) を skip し phyllotaxis 1 個だけ採用。
step 6 (invariant 検査) で確認すべきだった暗黙前提:

| 元ドメイン (botany) | 移植先 (EV charging) | 一致? |
|---|---|---|
| 葉は同種 | EV は heterogeneous (E_i, τ_i 異なる) | **❌** |
| 目的 = 被覆均一性 | 目的 = peak load 最小化 | **❌** (積分均一 ≠ max 最小) |
| 角度配置の continuity | 時間配置の discreteness | ⚠️ |

→ step 6 を踏んでいれば、heterogeneous case で **6% peak gap が
predicate** できた。Rule 9 v1 (= step 5-6 欠落) が原因で、実験で
事後発見する羽目になった。

**失敗パターン**:
- 単一遠隔ドメインを採用 (= step 5 skip) → "1 個試して当たるかどうか"
  ギャンブルになる。`try10/review_record.md` 参照
- Invariant の表層しか見ない (= step 6 skip)。例: "irrational
  rotation で resonance 防止" まで書いて止めると、その下の
  "同種前提" / "目的一致" を見逃す
- 候補を出した後 ranking で絞る → Rule 1 (HAI-CDP) と矛盾。
  Invariant 検査で **mechanical に脱落させる**こと

```
❌ 悪い例 (try10 phyllo):
  step 5 で phyllotaxis 1 個だけ採用
  step 6 を skip (= 表層 invariant "non-resonance" のみ確認)
  → 実験で initial 仮説 falsify (phyllo は MILP より 6% 悪い)

✅ 良い例 (Rule 9 v2 後):
  step 5 で 7 候補 (phyllotaxis / polyrhythm / cicada cycles /
    quantum revival / cellular automaton / antibody maturation /
    Penrose tiling) を並列抽象化
  step 6 で各 invariant を検査:
    - phyllotaxis: 同種前提 ❌ → 脱落
    - polyrhythm: 同種前提 ❌ → 脱落
    - antibody maturation: heterogeneity 内蔵 ✅ → 残る
    - cellular automaton: 局所規則 ✅ → 残る
  step 7-8 で残候補 (#4, #5) を S6-S7 で絞る
  → 実験前に invariant 不一致を予測、無駄な実装を回避
```



**Domain distance の判定**:

| 距離 | 例 (vs power systems / EV) |
|---|---|
| 近 | 制御工学、最適化、queueing theory |
| 中 | 機械学習、ゲーム理論、交通工学 |
| 遠 | 植物形態学、結晶学、抗生物質耐性、動物行動学、言語学 |

→ Rule 9 は **「中」以下を経由しない** ことを推奨。

**根拠**: TRIZ の核は「異分野の解を機構レベルで移植する」こと
[Altshuller 1946-]。組合せ的拡張は incremental work、機構移植が
breakthrough。

```
❌ 悪い例 (隣接組合せ):
  EV 充電 + queueing + power flow + bandit
  → 全部 OR / 機械学習 / power systems の隣接、TRIZ 移植ゼロ

✅ 良い例 (遠隔移植):
  EV 充電の同期共鳴問題 ← 植物形態学の黄金角配置機構
  → 葉序の low-discrepancy 性質を charging schedule に移植、
    closed-form `t_n = T_0 + φ·n mod W` で deconfliction
```

**失敗パターン**:
- 遠隔ドメインの **名前だけ** 借りて中身は隣接組合せ (= "biological-
  inspired" だが実質は genetic algorithm)
- 機構を移植したが S7 で他 method を排除できない (= 移植が必要不可欠
  でない、装飾的)

### 2.5.3 Novelty Gate (実験前の新規性審査)

アイデアが決まったら、**実験に入る前に** 以下の **9 項目** で
新規性を審査する。1 つでも ❌ なら Rule 1 (= Rule 7 の乱数 anchoring)
に戻る。

| # | チェック | 基準 | 関連 Rule |
|---|---|---|---|
| 1 | 既存 metric / 手法から自明に導けるか | 「パラメータ / 統計量の変更」だけなら ❌ | - |
| 2 | 先行文献に同等概念があるか | 同分野での直接先行があれば ❌。**未検索のままの "ない" 主張は ❌** | - |
| 3 | 物理的に解釈可能か | 「平均を取った」等の数学的操作のみでは ❌ | - |
| 4 | "So what?" テストに耐えるか | 結果 1 文で述べたとき専門家が行動を変えるか | Rule 8 S5 |
| 5 | Cross-disciplinary insight があるか | 単一分野内改善は novelty として弱い | Rule 9 |
| 6 | 計算手法自体に innovation があるか | 命名 / 形式化のみは弱い。アルゴリズム / モデル / 理論があるか | - |
| **7** | **乱数 anchor を経由したか** | 自己選択の plausible 候補のみで構成されていれば ❌ | **Rule 7** |
| **8** | **課題深掘り S0-S8 が S7 で method 一意化を達成したか** | S6 制約の必然性が 2 段以上たどれない場合 ❌ | **Rule 8** |
| **9** | **method 構成要素のうち遠隔ドメインから移植されたものがあるか** | 隣接組合せのみなら ❌ | **Rule 9** |

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
| Tversky & Kahneman (1974) "Judgment under Uncertainty" | anchoring 効果。出発点の数値 / 概念に判断が引かれる現象を **逆用** | Rule 7 |
| de Bono (1970) "Lateral Thinking: Creativity Step by Step" | random word stimulus method。意図的に非関連 anchor から発想を起動 | Rule 7 |
| Niederreiter (1992) "Random Number Generation and Quasi-Monte Carlo Methods" | 低 discrepancy 数列の理論。Rule 9 で phyllotactic charging 例の理論裏付け | Rule 9 (例) |
| Mitchison (1977) "Phyllotaxis and the Fibonacci series" *Science* | 黄金角 137.5° の non-resonance 性質。Rule 9 の遠隔移植元の数学的基礎 | Rule 9 (例) |

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
| 2026-04-28 | §2.5.2 に Rule 7 (乱数アンカリング) / Rule 8 (課題深掘り連鎖 S0-S8) / Rule 9 (TRIZ 遠隔ドメイン移植) を追加。try10 で v1 (Novelty Gate を文献検索なしに通過させた) → v2 (課題深掘り後付け) → v3 (乱数 anchor で phyllotactic charging に到達) の試行錯誤を経て、3 ルールが揃って初めて非妥当 anchor から手法強制が成立することが判明したため。Novelty Gate を 6 → 9 項目に拡張、根拠論文 4 本 (Tversky & Kahneman / de Bono / Niederreiter / Mitchison) を追加引用 |
| 2026-04-28 | Rule 9 を v2 に拡張。try10 phyllotactic charging が単一遠隔ドメインのワンショット移植のため experiment 後に MILP に対して 6% 劣る (= invariant 不整合) ことを後付け発見した教訓から、step 5-9 を追加: **(a) ≥3 候補の並列抽象化**, **(b) invariant 保存検査** (元ドメイン暗黙前提が target で成立するか), **(c) 機械的脱落** (preservation 不成立で除外), **(d) Rule 8 S6-S7 で残候補から強制絞込**。try10 phyllo の失敗を worked anti-pattern として本文に埋込 (botany の「葉同種」「目的=被覆均一」前提が EV charging で成立しないことを mechanical に確認すべきだった)。AI ideation の "another domain method を 1 個持ってくれば novel になる" バイアス対策 |
