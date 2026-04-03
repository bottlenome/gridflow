# WI-04: 第5章 状態遷移設計

**対象ファイル**: `/home/user/gridflow/docs/detailed_design/05_state_transition.md` を新規作成
**共通ルール**: `WI-00_common.md` 参照

冒頭:
```markdown
# 第5章 状態遷移設計
## 更新履歴
| 版数 | 日付 | 変更内容 |
|---|---|---|
| 0.1 | 2026-04-03 | 初版作成 |
```

各コンポーネントに **Mermaid stateDiagram-v2** と **状態遷移表（状態×イベント マトリクス）** をセットで記述する。

---

## 5.1 Orchestrator 状態遷移（REQ-F-002）

### 状態
| 状態 | 説明 |
|---|---|
| Idle | 初期状態。コマンド待ち |
| Initializing | ExecutionPlan生成・コンテナ起動中 |
| Ready | 全Connectorがhealthy。実行準備完了 |
| Running | ステップ実行中 |
| Collecting | 結果収集・メトリクス計算中 |
| Completed | 正常完了 |
| Failed | 異常終了 |

### イベント
run_requested, containers_ready, step_completed, all_steps_done, error_occurred, reset, cancel

### 遷移ルール
Idle→Initializing(run_requested), Initializing→Ready(containers_ready), Initializing→Failed(error_occurred), Ready→Running(step_started), Running→Running(step_completed, 次ステップあり), Running→Collecting(all_steps_done), Running→Failed(error_occurred), Collecting→Completed(collection_done), Failed→Idle(reset), Completed→Idle(reset)

---

## 5.2 Connector 状態遷移（REQ-F-007）

### 状態
Disconnected, Connecting, Connected, Executing, Idle(実行待ち), Disconnecting, Error

### イベント
initialize_called, connection_established, execute_called, step_done, teardown_called, error_occurred, recovered

### 遷移ルール
Disconnected→Connecting(initialize_called), Connecting→Connected(connection_established), Connecting→Error(error_occurred), Connected→Idle(ready), Idle→Executing(execute_called), Executing→Idle(step_done), Executing→Error(error_occurred), Idle→Disconnecting(teardown_called), Error→Disconnecting(teardown_called), Disconnecting→Disconnected(disconnected)

---

## 5.3 Scenario Pack ライフサイクル（REQ-F-001）

### 状態
Draft, Validated, Registered, Running, Completed, Archived

### イベント
validate_success, validate_fail, register, run_start, run_complete, run_fail, archive, unarchive

### 遷移ルール
Draft→Validated(validate_success), Draft→Draft(validate_fail, エラー修正後再検証), Validated→Registered(register), Registered→Running(run_start), Running→Completed(run_complete), Running→Registered(run_fail, 再実行可能), Completed→Archived(archive), Archived→Registered(unarchive)

---

## 5.4 バッチジョブ状態遷移（REQ-F-002）

### 状態
Queued, Running, Succeeded, Failed, Cancelled, Retrying

### イベント
dequeue, complete, fail, cancel, retry, max_retries_exceeded

### 遷移ルール
Queued→Running(dequeue), Running→Succeeded(complete), Running→Failed(fail), Running→Cancelled(cancel), Failed→Retrying(retry), Retrying→Running(dequeue), Failed→Failed(max_retries_exceeded)
