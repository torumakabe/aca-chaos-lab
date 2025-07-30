### [実装] - [エラーメッセージ標準化] - [2025-07-29T00:00:00Z]
**目的**: API全体で一貫したエラーレスポンス形式を実装
**コンテキスト**: エラーハンドリングの改善とデバッグ容易性の向上
**決定**: ErrorResponseモデルを作成し、HTTPExceptionを標準化されたJSONResponseに置き換え
**実行**: 
1. models.pyにErrorResponseモデルを追加
   - error: エラーの種類（例: "Bad Request", "Conflict"）
   - detail: 詳細なエラーメッセージ
   - timestamp: エラー発生時刻（ISO形式）
   - request_id: リクエストIDヘッダー（トレーシング用）
2. main.pyに汎用例外ハンドラーを追加
   - すべての未処理例外をキャッチ
   - DEBUGモードの場合のみ詳細を表示
3. chaos.pyのすべてのHTTPExceptionを置き換え
   - JSONResponseとErrorResponseモデルを使用
   - Request オブジェクトからX-Request-IDヘッダーを取得

**出力**: 
## 変更内容

### 標準化されたエラーレスポンス形式
```json
{
  "error": "Bad Request",
  "detail": "Invalid load level. Must be 'low', 'medium', or 'high'",
  "timestamp": "2025-07-29T00:00:00Z",
  "request_id": "abc123"
}
```

### 変更されたファイル
- `/src/app/models.py`: ErrorResponseモデルを追加
- `/src/app/main.py`: 汎用例外ハンドラーを追加
- `/src/app/chaos.py`: HTTPExceptionをJSONResponse + ErrorResponseに置き換え

### 利点
1. **一貫性**: すべてのエラーが同じ形式で返される
2. **トレーサビリティ**: request_idによるリクエストの追跡が可能
3. **デバッグ**: タイムスタンプとDEBUGモードでの詳細情報
4. **型安全性**: Pydanticモデルによる型チェック

**検証**: すべてのユニットテストが成功し、型チェックも通過
**次**: Phase 4（検証フェーズ）への移行準備完了