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

#### レスポンス（正常時）

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

#### レスポンス（異常時）

HTTPステータスコード: 503 Service Unavailable

```json
{
  "status": "unhealthy",
  "redis": {
    "connected": false,
    "latency_ms": 0
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

**注**: 
- Redisが無効化されている場合（`REDIS_ENABLED=false`）、常に200 OKと"healthy"を返します
- Redisが有効でも接続できない場合、503 Service Unavailableと"unhealthy"を返します

### メインエンドポイント

Redisと相互作用し、アプリケーションステータスを返します。

```http
GET /
```

#### レスポンス（成功時）

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
| redis_data | string | Redisからのデータ |
| timestamp | string | ISO 8601タイムスタンプ |

#### エラーレスポンス

- `503 Service Unavailable` - Redisが有効だが接続できない場合

**Redis接続エラー時の動作**:
1. redis-pyが自動的にリトライを実行（デフォルト: 1回、指数バックオフ1-3秒）
2. リトライが失敗した場合、503エラーを返す
3. Redisが復旧した場合、次回リクエストから自動的に接続が回復

```json
{
  "error": "Service Unavailable",
  "detail": "Redis operation failed: Redis connection failed",
  "timestamp": "2024-01-20T10:30:00Z",
  "request_id": "req-12345"
}
```

**注**: Redisが無効化されている場合（`REDIS_ENABLED=false`）、エンドポイントは常に200を返し、`redis_data`フィールドは"Redis unavailable"になります。

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
  },
  "redis": {
    "connected": true,
    "connection_count": 2,
    "last_reset": "2025-07-30T10:00:00Z"
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
| redis.connected | boolean | Redis接続状態 |
| redis.connection_count | integer | 現在のRedis接続数 |
| redis.last_reset | string/null | 最後のRedis接続リセット時刻（ISO 8601） |

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

呼び出したリクエストを無応答状態にします。

**重要な動作仕様**:
- ハングAPIを呼び出したリクエストのみがハングします
- 他のAPIエンドポイント（`/health`、`/chaos/status`など）は引き続き正常に応答します
- アプリケーション全体は動作を継続し、新しいリクエストも処理されます
- FastAPIの非同期処理により、他のリクエストは影響を受けません

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
| duration_seconds | integer | はい | 継続時間（秒）<br>- 1以上: 指定秒数後にレスポンスを返す<br>- 0: 永続的ハング（レスポンスを返さない） |

#### レスポンス

**時限ハングの場合**（duration_seconds > 0）:
指定された秒数後に以下のレスポンスが返されます：
```json
{
  "status": "hang_completed"
}
```

**永続的ハングの場合**（duration_seconds = 0）:
- レスポンスは返されません
- クライアント側でタイムアウトが発生します
- `/chaos/status`で状態を確認可能

#### エラーレスポンス

- `409 Conflict` - ハングが既にアクティブ（グローバル状態の競合）

#### 使用例

```bash
# 30秒間のハング（レスポンスあり）
curl -X POST "${APP_URL}/chaos/hang" \
  -H "Content-Type: application/json" \
  -d '{"duration_seconds": 30}'

# 別のターミナルで他のエンドポイントは正常に応答
curl "${APP_URL}/health"  # 正常に応答
curl "${APP_URL}/chaos/status"  # ハング状態を確認可能
```

### Redis接続リセット

Redis接続を強制的にリセットして、接続障害をシミュレートします。

**動作詳細**:
- 接続プール内のすべての接続を切断
- クライアントインスタンスは保持（設定情報を維持）
- 次回のRedis操作時に自動的に新しい接続を確立
- リセット直後は一時的に接続エラーが発生する可能性あり

```http
POST /chaos/redis-reset
Content-Type: application/json

{
  "force": true
}
```

#### リクエストボディ

| フィールド | 型 | 必須 | 説明 |
|------------|-----|------|------|
| force | boolean | いいえ | 強制的にリセット（デフォルト: true） |

#### レスポンス

```json
{
  "status": "redis_connections_reset",
  "connections_closed": 3,
  "timestamp": "2025-07-30T10:30:00Z"
}
```

| フィールド | 型 | 説明 |
|------------|-----|------|
| status | string | 操作ステータス |
| connections_closed | integer | 閉じた接続数 |
| timestamp | string | リセット時刻（ISO 8601） |

#### エラーレスポンス

- `503 Service Unavailable` - Redisクライアントが初期化されていない
- `500 Internal Server Error` - リセット中のエラー

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

## Redis接続管理

### 接続ライフサイクル

1. **アプリケーション起動時**
   - Redisへの接続を試行
   - 失敗してもアプリケーションは起動を継続
   - 最初のAPIコール時に再接続を試行

2. **通常操作時**
   - redis-pyが内部的に接続プールを管理
   - 接続エラー時は自動リトライ（指数バックオフ）
   - ヘルスチェックによる不正な接続の自動検出・削除

3. **接続リセット後**
   - `/chaos/redis-reset`呼び出し後、既存接続はすべて切断
   - 次のRedis操作で新しい接続を自動確立
   - リセット直後のリクエストは一時的に失敗する可能性あり

### 接続設定

| 設定項目 | 環境変数 | デフォルト値 | 説明 |
|----------|----------|------------|------|
| 最大接続数 | REDIS_MAX_CONNECTIONS | 50 | 接続プールの最大接続数 |
| ソケットタイムアウト | REDIS_SOCKET_TIMEOUT | 3秒 | 操作のタイムアウト |
| 接続タイムアウト | REDIS_SOCKET_CONNECT_TIMEOUT | 3秒 | 接続確立のタイムアウト |
| リトライ回数 | REDIS_MAX_RETRIES | 1 | 最大リトライ回数 |
| バックオフベース | REDIS_BACKOFF_BASE | 1秒 | 指数バックオフのベース時間 |
| バックオフ上限 | REDIS_BACKOFF_CAP | 3秒 | 指数バックオフの上限時間 |

## エラーハンドリング

すべてのエンドポイントは標準的なHTTPステータスコードを返します：

- `200 OK` - 成功
- `400 Bad Request` - 無効なリクエストパラメータ
- `409 Conflict` - 操作が現在の状態と競合
- `503 Service Unavailable` - Redis接続エラーまたはサービス利用不可
- `500 Internal Server Error` - 予期しないサーバーエラー

### 標準エラーレスポンス形式

すべてのエラーは以下の標準化された形式で返されます：

```json
{
  "error": "Bad Request",
  "detail": "Invalid load level. Must be 'low', 'medium', or 'high'",
  "timestamp": "2025-07-29T10:30:00Z",
  "request_id": "abc123-def456-ghi789"
}
```

| フィールド | 型 | 必須 | 説明 |
|------------|-----|------|------|
| error | string | はい | エラーの種類（HTTPステータスに対応） |
| detail | string | いいえ | 詳細なエラーメッセージ |
| timestamp | string | はい | エラー発生時刻（ISO 8601形式） |
| request_id | string | いいえ | リクエストID（X-Request-IDヘッダーから取得） |

### エラーレスポンスの例

#### 400 Bad Request
```json
{
  "error": "Bad Request",
  "detail": "Duration must be between 1 and 3600 seconds",
  "timestamp": "2025-07-29T10:30:00Z",
  "request_id": "req-12345"
}
```

#### 409 Conflict
```json
{
  "error": "Conflict",
  "detail": "Load simulation already active",
  "timestamp": "2025-07-29T10:30:00Z",
  "request_id": "req-67890"
}
```

#### 503 Service Unavailable
```json
{
  "error": "Service Unavailable",
  "detail": "Redis connection failed",
  "timestamp": "2025-07-29T10:30:00Z",
  "request_id": "req-54321"
}
```

#### 500 Internal Server Error
```json
{
  "error": "Internal Server Error",
  "detail": null,
  "timestamp": "2025-07-29T10:30:00Z",
  "request_id": "req-abcde"
}
```

**注**: デバッグモード（環境変数 `LOG_LEVEL=DEBUG`）の場合、500エラーの`detail`フィールドに詳細なエラー情報が含まれます。

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