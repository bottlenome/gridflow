# MVP 標準ワークフロー — gridflow CLI だけで 1 試行を回す

## 0. なぜこの文書があるか

try11〜16 の全試行は、sweep・bootstrap CI・baseline・合成属性生成を各試行の
`tools/` に**自作**し、`gridflow sweep` / `benchmark` / `evaluate` をほぼ使わなかった。
その結果、framework が持つ決定的 seed・再現性検証・統計判定が経路上バイパスされ、
実際の誤判定（try16 salted-hash 再現性事故、try11 CI ゼロ幅見逃し、try13→14 の
infeasibility 誤検出）を招いた。

本文書は「自作スクリプトを書く前に必ず通す標準経路」を定義する。**この経路上の
機能で足りない場合は、自作する前に issue を立てる**（framework の欠落は framework
側で埋める。§0.5.1 割り切り禁止）。

## 1. パイプライン全体像

```
仮説
 └─ scenario clone      標準 baseline から比較対象を派生（数値可比性を担保）
     └─ sweep           レプリケート付きで多数セルを実行（決定的 seed・resume 可）
         └─ evaluate    保存済み結果に CI 付きでメトリクスを再適用
             └─ benchmark   レプリケート群を統計判定（検定・効果量・多重比較補正）
                 └─ attribute-violations   controller の成果を起因分離
                 └─ validate-engines       単一エンジンのバグを排除
                     └─ export paper        JSON→LaTeX 表（転記ミス排除）
```

各ステップは自作せず CLI を使う。以下、`examples/ieee13` を例に具体化する。

## 2. ステップ詳細

### 2.1 baseline を clone して比較対象を作る

```bash
gridflow scenario register examples/ieee13/pack.yaml
gridflow scenario clone ieee13@1.0.0 --id ieee13-mymethod@1.0.0
# clone 先のパラメータ/手法を編集して自分の手法を入れる
```

標準 baseline を起点にすることで、try15 の「simulator 自作で try11-14 と数値
非可比」を避ける。

### 2.2 レプリケート付き sweep

`sweep_plan.yaml`（テンプレート: `test/_template/sweep_plan.yaml`）で
`n_replicates` を 2 以上にする。これで run-to-run 分散が推定でき、後段の統計検定に
必要な標本が供給される。

```bash
gridflow sweep --plan sweep_plan.yaml --connector opendss --output sweep.json
# 途中で失敗しても再実行時は --resume で未済セルだけ走る（決定的 experiment_id）
gridflow sweep --plan sweep_plan.yaml --connector opendss --resume --output sweep.json
```

**禁止**: builtin `hash()` で合成属性を作らない。決定性が必要なら
`gridflow.domain.util.stable_hash`（プロセス間安定）を使う。

### 2.3 CI 付き evaluate（後処理再評価）

シミュレーションを再実行せずに、閾値違いのメトリクス等を掛け直す。

```bash
gridflow evaluate --results <results_dir> \
  --metric "hc:mypkg.metrics:HostingCapacity" \
  --parameter-sweep "voltage_low:0.90:0.95:11" \
  --bootstrap-n 1000 --output sensitivity.json
```

`--bootstrap-n` で CI が付く。**CI がゼロ幅なら警告が出る**（try11 の罠）。
`_bootstrap_ci` を自作しない。

### 2.4 統計判定付き benchmark

同一手法を複数回実行した結果（レプリケート群）を渡すと、平均差ではなく検定で判定する。

```bash
gridflow benchmark \
  --baseline b1 --baseline b2 --baseline b3 \
  --candidate c1 --candidate c2 --candidate c3 \
  --correction holm --alpha 0.05 --output cmp.json
```

`significant` が True になるのは「補正後 p < alpha **かつ** 両群 ≥2 レプリケート
**かつ** 非ゼロ分散 **かつ** informational でない」時のみ。有意でなければ改善と書けない。

### 2.5 誤判定ガードを通す

```bash
# controller の成果を起因分離（envelope 必須）
gridflow attribute-violations --baseline no_control --candidate with_control \
  --v-min 0.95 --v-max 1.05 --output attribution.json

# 単一エンジンのバグを排除
gridflow validate-engines ieee13-mymethod@1.0.0 --engines opendss,pandapower --tol 1e-6
```

`attribute-violations` は `dispatch_induced_rate` だけが controller の責任。
`validate-engines` が exit≠0 なら、その結果は単一エンジンの癖の可能性がある。

### 2.6 論文成果物の生成

```bash
gridflow export paper cmp.json -o paper_export/
```

JSON→LaTeX 表を自動生成することで「数値の JSON→本文転記ミス」（§4.2 B CRITICAL）を
機構的に排除する。手で表を書かない。

## 3. self-review 前チェックリスト（機構的ガードの証拠を添付）

report.md を凍結する前に、以下の CLI 出力を results/ に残す。査読者はこれを証拠とする
（`docs/mvp_review_policy.md` §4.1.2）。

- [ ] `benchmark` の JSON に `significant` と p 値・効果量・CI がある
- [ ] `benchmark` に `zero_variance` / `insufficient_replicates` 警告が出ていない
- [ ] `validate-engines` が agree（exit 0）
- [ ] 電圧違反の主張は `attribute-violations` の `dispatch_induced_rate` に基づく
- [ ] 合成属性は `stable_hash` 由来（builtin `hash` 不使用）
- [ ] sweep 結果に `non_convergence_rate` があり 0 に近い

## 4. 逸脱の記録

やむを得ず標準経路を外れて自作した場合、review_record に**理由と、なぜ framework
機能で代替できなかったか**を明記する（テンプレート: `test/_template/review_record.md`
の「標準経路の使用状況」欄）。理由が「framework に機能が無い」なら、issue を立てて
framework 側に還元する。
```

## 5. パイロット

本経路を 1 試行で完走させる実証（研究成果物）は、次の実試行で行う。framework 側で
不足が見つかれば個別 issue 化して埋める。テンプレート一式は `test/_template/` にある。
