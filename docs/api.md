# APIドキュメント

## ベースURL

```
https://<your-app>.azurecontainerapps.io
```

## 認証

カオステスト用エンドポイントに認証は必要ありません。

## エンドポイント

### ヘルスチェック

アプリケーションの健全性とRedis接続性をチェックします。

```http
GET /health
```

#### レスポンス

```json
{
  "status": "healthy",
  "redis": {
    "connected": true,
    "latency_ms": 5
  },
  "timestamp": "2024-01-20T10:30:00Z"
}
```

| フィールド | 型 | 説明 |
|------------|-----|------|
| status | string | "healthy" または "unhealthy" |
| redis.connected | boolean | Redis接続状態 |
| redis.latency_ms | integer | Redis pingレイテンシ（ミリ秒） |
| timestamp | string | ISO 8601タイムスタンプ |

### メインエンドポイント

Redisと相互作用し、アプリケーションステータスを返します。

```http
GET /
```

#### レスポンス

```json
{
  "message": "Hello from Container Apps Chaos Lab",
  "redis_data": "Data created at 2024-01-20T10:30:00Z",
  "timestamp": "2024-01-20T10:30:00Z"
}
```

| フィールド | 型 | 説明 |
|------------|-----|------|
| message | string | アプリケーションのグリーティング |
| redis_data | string/null | Redisからのデータまたは "Redis unavailable" |
| timestamp | string | ISO 8601タイムスタンプ |

### カオスステータス

現在のカオス注入状態を取得します。

```http
GET /chaos/status
```

#### レスポンス

```json
{
  "load": {
    "active": true,
    "level": "medium",
    "remaining_seconds": 45
  },
  "hang": {
    "active": false,
    "remaining_seconds": 0
  }
}
```

| フィールド | 型 | 説明 |
|------------|-----|------|
| load.active | boolean | 負荷シミュレーションがアクティブかどうか |
| load.level | string | 現在の負荷レベル（"low"/"medium"/"high"） |
| load.remaining_seconds | integer | 負荷が停止するまでの秒数 |
| hang.active | boolean | ハングシミュレーションがアクティブかどうか |
| hang.remaining_seconds | integer | ハングが停止するまでの秒数（永続的な場合は0） |

### 負荷シミュレーションの開始

CPUとメモリの負荷を注入します。

```http
POST /chaos/load
Content-Type: application/json

{
  "level": "medium",
  "duration_seconds": 60
}
```

#### リクエストボディ

| フィールド | 型 | 必須 | 説明 |
|------------|-----|------|------|
| level | string | はい | 負荷レベル: "low"、"medium"、または "high" |
| duration_seconds | integer | はい | 継続時間（秒）（1-3600） |

#### レスポンス

```json
{
  "status": "load_started",
  "level": "medium",
  "duration_seconds": 60
}
```

#### エラーレスポンス

- `400 Bad Request` - 無効なパラメータ
- `409 Conflict` - 負荷シミュレーションが既にアクティブ

### アプリケーションハングのトリガー

アプリケーションを無応答状態にします。

```http
POST /chaos/hang
Content-Type: application/json

{
  "duration_seconds": 30
}
```

#### リクエストボディ

| フィールド | 型 | 必須 | 説明 |
|------------|-----|------|------|
| duration_seconds | integer | はい | 継続時間（秒）（永続的な場合は0） |

#### レスポンス

時限ハングの場合、継続時間後に返されます：
```json
{
  "status": "hang_completed"
}
```

永続的なハングの場合、リクエストはタイムアウトします。

#### エラーレスポンス

- `409 Conflict` - ハングが既にアクティブ

## 負荷レベル

### 低負荷（30% CPU）
- 軽いCPU使用
- 100MBメモリ割り当て
- 通常操作への影響は最小限

### 中負荷（60% CPU）
- 中程度のCPU使用
- 500MBメモリ割り当て
- 顕著なパフォーマンスへの影響

### 高負荷（90% CPU）
- 重いCPU使用
- 1GBメモリ割り当て
- 著しいパフォーマンス低下

## エラーハンドリング

すべてのエンドポイントは標準的なHTTPステータスコードを返します：

- `200 OK` - 成功
- `400 Bad Request` - 無効なリクエストパラメータ
- `409 Conflict` - 操作が現在の状態と競合
- `500 Internal Server Error` - 予期しないサーバーエラー

エラーレスポンスには詳細メッセージが含まれます：

```json
{
  "detail": "Load simulation already active"
}
```

## パフォーマンス特性

2025年7月28日の本番環境検証結果：

- **平均レスポンス時間**: 23ms（ヘルスチェック、メイン、ステータスエンドポイント）
- **最大レスポンス時間**: 249ms（負荷テスト中）
- **スループット**: 5.6 req/s（10ユーザー定常負荷）
- **エラー率**: 0%（すべてのテストシナリオ）
- **Redis接続レイテンシ**: 1-2ms（Azure Managed Redis）

## レート制限

レート制限は実装されていません - テスト環境で責任を持って使用してください。

## Webhook

Webhookサポートはありません - 状態変更を監視するには `/chaos/status` をポーリングしてください。