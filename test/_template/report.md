# try NN — <one-line title>

<!-- Report skeleton. See docs/mvp_standard_workflow.md and mvp_review_policy.md §4. -->

## 1. 課題（出典）

- 出典: <査読論文の Future Work 引用 / mvp_problem_candidates.md の候補ID>
- 一文で: <解こうとしている問題>

## 2. 手法

- baseline: <standard baseline pack_id（scenario clone 元）>
- candidate: <自分の手法 / 変更点>
- 新規性の根拠: <Rule 9 v2 の invariant 保存検査結果への参照>

## 3. 実験設計

- feeders: <≥2 必須（§4.2 E-2）>
- sweep: `sweep_plan.yaml`（n_replicates=<N>）
- envelope: V_min=<0.95> / V_max=<1.05>（strict/relaxed を明示）

## 4. 結果（すべて CLI 出力の JSON に基づく）

| 主張 | 根拠ファイル | 数値 |
|---|---|---|
| <改善の主張> | `results/cmp.json` | significant=<t/f>, p_adj=<>, d=<>, CI=[<>,<>] |
| <違反低減> | `results/attribution.json` | dispatch_induced_rate=<> |
| <エンジン一致> | `results/xval.json` | agree=<t/f> |

<!-- 本文の数値は必ず results/*.json と一致させること（転記ミスは CRITICAL）。
     表は `gridflow export paper` の出力を使い、手書きしない。 -->

## 5. Limitations

- <既知の制約を隠さず列挙>

## 6. 再現手順

```bash
# scenario clone -> sweep -> evaluate -> benchmark -> attribute/validate -> export
# （docs/mvp_standard_workflow.md のコマンドをそのまま貼る）
```
