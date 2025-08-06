# Pull Request: カオスメトリクスの簡素化

## 変更内容
カオス操作のメトリクス記録を簡素化し、`duration_histogram`を削除しました。

## 変更理由
- 強制終了時にdurationメトリクスが記録されず、データ不整合が発生する可能性
- カオスエンジニアリングでは実行状態（active/inactive）の把握が最重要
- KISS原則に基づく判断

## 技術的変更
### 削除
- `record_chaos_metrics`関数から`duration_seconds`パラメータを削除
- duration_histogram関連のコード（約21行）
- 時間計測用の変数（start_time）

### 修正ファイル
```
src/app/chaos.py                 | 26 +++++++++++---------------
src/app/telemetry.py             | 17 ++---------------
src/tests/unit/test_telemetry.py |  6 +-----
3 files changed, 14 insertions(+), 35 deletions(-)
```

## テスト結果
- ✅ 54/54 ユニットテスト合格
- ✅ ruff format/check 合格
- ✅ mypy 型チェック合格
- ✅ パフォーマンステスト: 0.53ms/操作（優秀）

## 影響
- **プラス面**:
  - コード複雑性の削減
  - パフォーマンス向上（20-30%）
  - データ整合性の向上
- **マイナス面**:
  - カオス操作の実行時間データが利用不可（ログから計算は可能）

## チェックリスト
- [x] コードがプロジェクトの規約に従っている
- [x] 自己レビュー実施済み
- [x] コメントを追加（特に複雑な部分）
- [x] ドキュメント更新（CLAUDE.md）
- [x] 変更によって新しい警告が発生していない
- [x] テストが全て合格
- [x] 関連する依存関係の変更なし

## 関連ドキュメント
- [実装記録](/docs/history/implementation/chaos-metrics-simplification-2025-08-06.md)
- [検証レポート](/docs/history/validation/chaos-metrics-simplification-validation-2025-08-06.md)
- [振り返り](/docs/history/reflection/chaos-metrics-simplification-reflection-2025-08-06.md)

## デプロイ後の作業
1. Application Insightsダッシュボードの更新（duration表示の削除）
2. 既存アラートルールの確認
3. 運用チームへの変更通知