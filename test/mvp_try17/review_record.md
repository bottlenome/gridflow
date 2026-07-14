# try17 独立査読記録（Phase 2）

- 査読者: 独立査読エージェント（著者と分離、§4.1.1 準拠）
- 入力: `report.md` と `results/*.json` のみ（中間生成物・src・思考ログは不参照）
- 準拠: `docs/mvp_review_policy.md` §4.1〜§4.5
- 日付: 2026-07-14

---

## 0. 論文主張のリフレーズ（成果物 JSON のみから、report §6 を見る前に再構成）

- **課題**: IEEE13 配電フィーダーに大量の屋根置き PV を入れたとき、母線電圧が ANSI C84.1
  Range A（0.95–1.05 pu）を外れる違反リスクが、PV の「容量」と「電気的位置」の
  どちらでどれだけ駆動されるか。
- **先行研究**: （成果物からは特定不可。候補プール 候補1 の「高PV浸透 Volt-VAR」課題を
  出典と称するが、research_landscape.md を参照できないため引用の妥当性は本査読では未検証。）
- **方法（提案手法の価値）**: OpenDSS 潮流を決定的に解き、分散源を「PV 配置のランダム性」
  （`RandomSampleAxis`, N=24/条件）に限定。容量条件（0/600/1800 kW を全母線ランダム配置）
  と位置条件（1800 kW を変電所近傍4母線 vs 末端4母線）を `sweep`→`benchmark`
  （Holm 補正・permutation 検定・Cohen's d・bootstrap CI）で判定。gridflow 自体は
  contribution にしない。
- **実験結果（JSON の数値）**:
  - BASE(0kW): vvr=0.488, stdev=0（決定的・単一値）。
  - 容量: BASE→HIGH は vvr −0.069 (p_adj=0.147, 非有意)、LOW→HIGH は +0.023 (p_adj=1.0, 非有意)。
  - 位置: ROOT vvr=0.569 vs END vvr=0.303, delta=−0.266, d=−1.55, **p_adj=0.0002「有意」**;
    voltage_deviation は ROOT 0.066 vs END 0.129, delta=+0.063, d=0.99, **p_adj=0.0022「有意」**。
  - 全条件 non_convergence_rate=0, valid_n=24。
- **考察（JSON から言えること）**: benchmark の verdict をそのまま読めば「容量は平均違反率を
  変えないが、位置は有意に変える（末端が低い）」となる。**しかし** 位置条件の
  per-experiment 値は候補4母線を復元抽出した4種の反復に過ぎず（後述 CRITICAL-1）、
  独立標本は各群4個。4母線を独立単位として厳密検定すると vvr p=0.143 / dev p=1.0 で
  **いずれも非有意**。すなわち成果物のみからは「位置効果が有意」という結論は導けない。

→ 私のリフレーズと report §6 の骨格は「容量 non-significant・位置 significant」で一致するが、
**「位置 significant」の部分で決定的に食い違う**。私は成果物から位置効果を有意と再構成できない。
このギャップが本査読の核心（CRITICAL-1）。

---

## 1. 数値照合結果（report 本文 vs results/*.json）

**転記は全て一致。転記ミス（B 観点）はゼロ。** 問題は数値そのものではなく、その数値の
生成条件（実効標本数）にある。

| report 箇所 | report 記載 | JSON 実値 | 判定 |
|---|---|---|---|
| §4.1 BASE vvr | 0.488, stdev=0 | 0.4878048780487805, stdev=0.0 | ✅一致 |
| §4.2 BASE→HIGH delta | −0.069 | −0.068810266591038 | ✅一致 |
| §4.2 BASE→HIGH d | −0.429 | −0.42899892836840875 | ✅一致 |
| §4.2 BASE→HIGH p_adj | 0.147 | 0.1471852814718528 (significant=false) | ✅一致 |
| §4.2 LOW→HIGH delta/d/p_adj | +0.023 / +0.139 / 1.0 | 0.02298.. / 0.13868.. / 1.0 (false) | ✅一致 |
| §4.2 HIGH stdev/範囲 | 0.222 / 0.146–0.732 | 0.22205999.. / 0.14634..–0.73170.. | ✅一致 |
| §4.3 vvr ROOT/END | 0.569[.498,.640]/0.303[.243,.364] | 0.56910..[0.49796..,0.64024..]/0.30322..[0.24254..,0.36390..] | ✅一致 |
| §4.3 vvr delta/d/p_adj | −0.266 / −1.553 / 0.0002 (True) | −0.26588.. / −1.55256.. / 0.00019998.. (true) | ✅一致 |
| §4.3 dev ROOT/END/delta/d/p_adj | 0.066/0.129/+0.063/+0.988/0.0022 (True) | 0.06623../0.12918../0.06295../0.98781../0.0021997.. (true) | ✅一致 |
| §4.4 non_convergence / valid_n | 0.000 / 24 | 0.0 / 24.0 | ✅一致 |

転記精度は完璧。**しかし数値一致は妥当性を意味しない**——後述の通り、一致している p 値
そのものが artifact である。

---

## 2. 機構的ガード確認（§4.1.2 チェックリスト）

| ガード | JSON での有無 | 評価 |
|---|---|---|
| `significant` 判定 | 全 benchmark に有り | ✅存在。ただし後述の通り位置効果の True は artifact |
| `zero_variance` 警告 | non_convergence_rate のみ発火 | ⚠️ **BASE の voltage 系（stdev=0, CI=[0.4878,0.4878]）には未発火**。ガードは両群ゼロ分散でのみ発火し、片側 degenerate baseline を見逃す |
| `insufficient_replicates` 警告 | どの metric にも無し（warnings=[]） | ❌ **復元抽出による疑似反復を検出できず**。n=24 という「見かけの標本数」を独立標本と誤認 |
| `non_convergence_rate` | 全条件 0.0, valid_n=24 | ✅存在 |
| `{metric}_valid_n` | vvr/dev とも 24 | ✅存在（ただし24は疑似反復込みの数） |
| envelope 刻印 | report §3 に V_min=0.95/V_max=1.05 と記載 | JSON 内に envelope フィールドは非確認（sweep JSON に格納なし）。report 記載のみ |
| 決定的 experiment_id / plan_hash | 各 sweep に plan_hash 有り | ✅存在 |
| `attribute-violations`（起因分離） | **`attribution_end.json` 不在** | ❌未実施（report Lim.3 で E-30300 失敗を開示） |
| `validate-engines`（エンジン相互検証） | 相当成果物なし | ❌未実施（report Lim.2 で E-30001 失敗を開示） |
| cross-validation | **`xval.json` 不在** | ❌成果物なし・report にも言及なし |

**結論**: gridflow の機構的ガードは本 try の2つの致命的 artifact（BASE degenerate / 復元抽出
水増し）を**どちらも自動検出できなかった**。`significant=True` を額面通り信頼すると誤判定に至る。

---

## 3. §4.5 主張と証拠のギャップ検証（最重要）

### 3.1 位置条件の per-experiment 構造（成果物から復元）

`sweep_root.json` / `sweep_end.json` の `assignments` と `per_experiment_metrics` を突合すると、
**位置条件の候補母線は各群 4 個のみ**で、N=24 はそれを復元抽出した反復である：

ROOT（4母線, 復元抽出で 24 draws）:

| 母線 | vvr | deviation | draw 回数 |
|---|---|---|---|
| 632 | 0.244 | 0.039 | 4 |
| 634 | 0.488 | 0.054 | 8 |
| 645 | 0.732 | 0.081 | 6 |
| 646 | 0.732 | 0.086 | 6 |

END（4母線, 復元抽出で 24 draws）:

| 母線 | vvr | deviation | draw 回数 |
|---|---|---|---|
| 675 | 0.146 | 0.028 | 4 |
| 680 | 0.146 | 0.028 | 6 |
| 652 | 0.302 | 0.220 | 6 |
| 611 | 0.500 | 0.187 | 8 |

per-experiment 値は 4 通りしか取らず、benchmark はこの 4 値の反復コピー 24 個を
**独立標本 24 個として** CI と permutation 検定に投入している（`n_baseline=24, n_candidate=24`,
p_value=9.999e-05 は 10000 permutation の下限に張り付き）。

### 3.2 独立単位（4母線）で厳密再検定した結果

母線を独立単位（各群 n=4）とみなし、4 vs 4 の厳密 Mann-Whitney（成果物値から計算）:

- **voltage_violation_rate**: two-sided exact p = **0.143** → 非有意
  （群が重複: ROOT の 632=0.244 は END の 611=0.500 より低い。分布が入り交じる）
- **voltage_deviation**: two-sided exact p = **1.0** → 完全非有意
  （ROOT{0.039,0.054,0.081,0.086} と END{0.028,0.028,0.187,0.220} が入れ子）

→ **report §4.3・§6 の中心的主張「位置効果は有意」は、復元抽出で n を 4→24 に 6 倍
水増ししたことによる artifact**。独立標本で正しく数えれば、位置効果は容量効果と同じく
非有意であり、「容量より位置が効く」という論文の非対称メッセージ全体が崩れる。

---

## 4. 発見した欠陥

### CRITICAL-1 — 復元抽出による実効標本数の水増し（中心的主張を無効化）

- **内容**: 位置条件 ROOT/END は候補母線が各 4 個のみ。`RandomSampleAxis` で 24 回
  復元抽出し、per-experiment 値は 4 通りの反復に過ぎない。benchmark はこの疑似反復を
  n=24 の独立標本として扱い、p_adj=0.0002(vvr)/0.0022(dev)・CI 非重複・d=1.55/0.99 を算出。
- **実値対比**: 独立単位（4母線）で厳密検定すると vvr p=0.143 / dev p=1.0（いずれも非有意）。
  4 vs 4 で到達しうる最小 two-sided p は 2/70=0.029 であり、報告の 0.0002 は
  独立標本では**原理的に到達不能**——反復数え上げによる捏造。
- **開示状況**: report §3 は「シード反復ではない」と try11 型 artifact を否定する一方、
  **位置軸の候補が4母線しかなく復元抽出している事実は非開示**。分散源が「配置ランダム性」
  で legitimate である点（§4.2 C）は正しいが、その配置候補が 4 個しかないため実効標本数は
  4 であり、24 ではない。分散源の正当性と標本数の妥当性は別問題。
- **影響**: report §4.3（位置効果有意）と §6（リフレーズの核）が成立しない。
  容量効果（null）は水増し下でも null のままなので結論は保存されるが、
  **論文の唯一の陽性結果が消滅**。§4.2 C（実験設計）違反。

### MAJOR-1 — 単一フィーダー（§4.2 E-2 違反）

- IEEE13 のみ。方法論/特性化の主張には ≥2 フィーダー必須（policy §4.2 E-2）。
- report §3・Lim.1 で明示開示。隠蔽なし。開示済みだが E-2 上は MAJOR。

### MAJOR-2 — 実験規模と実効 n（§4.2 E-2 / E-3）

- Monte Carlo n=24（policy 最低ライン n≥1000 に対し 2 桁不足）。かつ CRITICAL-1 により
  位置条件の実効独立標本は 4、容量条件でも母線候補 9・実効 ≤9。収束分析（n を増やした
  CI 収束図）なし。開示は部分的（n=24 は明記、実効 4 は非開示）。

### MODERATE-1 — 機構説明の post-hoc 性とデータ不整合

- §4.3 の「末端 PV が末端低電圧を是正して違反を下げる」機構は attribute-violations 未実施
  （E-30300）で未検証。report は「状況証拠」と開示（Lim.3）——ここは誠実。
- **ただしデータは単調な位置→違反関係を支持しない**: ROOT の 632=0.244 は END の
  611=0.500 より低く、END 内でも 611 が突出。「根元＝高違反 / 末端＝低違反」という
  clean な物理ストーリーは 4 母線の内部ばらつきと矛盾。逆符号（vvr↓ but deviation↑）の
  解釈自体は「別々の量」という注意喚起として妥当だが、deviation の群差は独立検定で p=1.0
  であり、そもそも「末端が deviation を有意に増やす」も成立しない。

### MINOR-1 — BASE degenerate baseline に zero_variance 警告が未発火

- bench_base_vs_high の baseline は voltage 系で stdev=0・CI=[0.4878,0.4878] の点質量だが
  warnings=[]（non_convergence のみ発火）。ツールのガードが片側 degenerate を見逃す。
  report §4.1 が「n 実質=1」と手動開示している点は評価できるが、機構的ガードとしては穴。

### MINOR-2 — paper_export が論文品質でない

- `table.tex`/`caption.txt` の method 名が sweep ハッシュ ID
  （`sweep-76727f40175cae52-...`）のまま。caption は END を "proposed method" と自動記載。
  データ CSV の n 列が 1（誤解を招く）。§4.2 D（図表完成度）の観点で公表不可レベル。
  gridflow を contribution 化する表現ではないため §3.1 違反ではない。

### 開示されている限界（隠蔽なしと確認）

- 単一フィーダー（Lim.1）、エンジン相互検証未実施 E-30001（Lim.2）、起因分離未実施
  E-30300（Lim.3）、制御器提案でない（Lim.4）、静的注入・雲影未実装（Lim.5）——
  いずれも明記。開示姿勢は良好。**唯一 CRITICAL-1（復元抽出の実効 n=4）だけが未開示**であり、
  これが致命的。
- `attribution_end.json`・`xval.json` は results/ に不在。attribution は失敗を開示済み。
  xval は成果物も report 言及も無し。

---

## 5. 観点別サマリ

- **A 方針適合性**: 合格。gridflow を contribution 化していない（Lim.4 で明示限定）。
  標準経路のみ・自作統計コードなしと明記、§7 も gridflow コマンドのみ。→ A は通過。
- **B 数値信頼性**: 転記は完全一致（CRITICAL/MAJOR なし）。ただし artifact 識別に失敗
  （復元抽出による水増しが未識別＝§4.2 B「アーティファクト未識別は CRITICAL」に該当）。
- **C 科学的妥当性**: **CRITICAL-1**。実験設計が中心主張を支持しない。DoD 上「位置効果有意」に
  相当する主張は未検証項目への ✅ 付与に等しい。
- **D 完成度**: paper_export が非公表品質（MINOR）。
- **E 投稿先水準**: E-2（単一フィーダー・n 不足）MAJOR、E-3（交絡・実効 n）問題あり。投稿不可。

---

## 6. judgment（総合判定）

## **不合格（Fail）**

**理由**:

1. **CRITICAL-1（復元抽出による実効標本数の水増し）が論文の唯一の陽性結果を無効化する。**
   位置条件は候補 4 母線を 24 回復元抽出した疑似反復であり、benchmark の
   `significant=True`（p_adj=0.0002 / 0.0022）は n を 4→24 に水増ししたことによる artifact。
   独立単位（4母線）で厳密再検定すると vvr p=0.143・dev p=1.0 で**いずれも非有意**。
   「容量より位置が効く」という論文の中心メッセージ（§4.3, §6）は成立しない。
   これは policy §4.2 B「アーティファクト未識別は CRITICAL」および §4.2 C（実験設計が
   主張を支持しない）に該当。
2. これに加え MAJOR が 2 件（単一フィーダー E-2、規模/実効 n）。
3. policy §4.3 判定基準「CRITICAL 1 件以上 → 不合格」「MAJOR 2 件以上 → 不合格」の
   両方に該当。

**指示されたクリティカル 2 点の評価（必達項目）**:

- **復元抽出による実効標本数の水増し**: ✅評価済み＝**CRITICAL-1**。位置条件 4母線→24 draws。
  独立再検定で位置効果は非有意（vvr 0.143 / dev 1.0）。中心主張を無効化する最重要欠陥。
- **BASE の stdev=0**: ✅評価済み＝**MINOR-1**＋B観点。著者は §4.1 で「n 実質=1」と手動開示し、
  base_vs_high から有意性を主張していない（non-significant）ため誤判定には至っていないが、
  機構的 zero_variance ガードが voltage 系で未発火した穴を残す。BASE を benchmark baseline に
  使う設計自体（点質量 vs 分布の permutation）も統計的にクリーンではない。

**再実験への必須修正（優先度順）**:

1. (CRITICAL) 位置効果の検定単位を「母線」にする。候補母線を大幅に増やす（≥30 母線）か、
   4母線しかないなら n=4 の independent test として報告し、p=0.14 の非有意を正しく記す。
   復元抽出で n を水増ししない。→ これが直らない限り論文の主張は撤回が必要。
2. (MAJOR) 第2フィーダー（IEEE34/37/123 いずれか）で位置効果の再現を確認。
3. (MAJOR) Monte Carlo n を実効ベースで拡大し、CI 収束図を添付。
4. (MODERATE) attribute-violations の E-30300（ノード数不一致）を解消し、END の違反低減を
   baseline_only / dispatch_induced に分離して機構主張を検証。
5. (MINOR) paper_export の method 名を可読ラベルに置換。
