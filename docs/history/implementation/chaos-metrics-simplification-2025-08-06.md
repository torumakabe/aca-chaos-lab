# カオスメトリクス簡素化実装計画 - 2025-08-06

## 実装タスク

### タスク1: telemetry.pyの修正
**説明**: record_chaos_metrics関数からduration_histogram関連を削除
**期待される結果**: duration_secondsパラメータなし、histogramメトリクスなし
**依存関係**: なし

### タスク2: chaos.pyの修正
**説明**: record_chaos_metricsの呼び出しを更新（5箇所）
**期待される結果**: duration引数を削除した呼び出し
**依存関係**: タスク1

### タスク3: test_telemetry.pyの修正
**説明**: record_chaos_metricsのテストを更新
**期待される結果**: durationパラメータなしのテスト
**依存関係**: タスク1

### タスク4: 品質チェック
**説明**: format, lint, type checkの実行
**期待される結果**: すべてのチェックが合格
**依存関係**: タスク1-3

### タスク5: 統合テスト
**説明**: 統合テストを実行して動作確認
**期待される結果**: すべてのテストが合格
**依存関係**: タスク1-4

## 実装順序
1. telemetry.py修正（関数シグネチャとロジック）
2. chaos.py修正（呼び出し箇所）
3. test_telemetry.py修正（テストケース）
4. 品質チェック実行
5. 統合テスト実行