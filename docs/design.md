# Azure Container Apps Chaos Lab - 技術設計書

## 更新履歴
- 2025-07-25: 初版作成
- 2025-07-28: 実装に合わせて更新（サブネット構成、Redisポート、マネージドID）
- 2025-07-30: Redis接続リセット機能の設計追加
- 2025-07-30: Container Apps応答監視アラート設計追加

## アーキテクチャ概要

### システムコンポーネント

```
┌─────────────────────────────────────────────────────────────────┐
│                         Internet                                │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Container Apps Ingress                       │
│                        (HTTPS)                                  │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Azure VNet                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Container Apps Subnet                        │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │            Container App (Python)                   │  │  │
│  │  │  ┌──────────────────┐  ┌─────────────────────┐    │  │  │
│  │  │  │   FastAPI App     │  │  Application       │    │  │  │
│  │  │  │  - Health Check   │  │  Insights SDK      │    │  │  │
│  │  │  │  - Redis Client   │  └─────────────────────┘    │  │  │
│  │  │  │  - Chaos APIs     │                             │  │  │
│  │  │  │  - Managed ID     │                             │  │  │
│  │  │  └──────────────────┘                             │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  │                            │                              │  │
│  │                     NSG (動的制御)                        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                               │                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │           Private Endpoint Subnet                         │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │        Redis Private Endpoint                      │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│          Azure Managed Redis (Entra ID認証)                     │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│     Monitoring Services (Public Access)                         │
│  ┌─────────────────────┐  ┌─────────────────────────────────┐  │
│  │  Log Analytics      │  │  Application Insights           │  │
│  └─────────────────────┘  └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│              External Load Testing (Locust)                     │
│                   ┌─────────────────┐                          │
│                   │  Local Machine  │                          │
│                   └─────────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
```

### ネットワーク設計

#### VNet構成
- **アドレス空間**: 10.0.0.0/16
- **Container Apps サブネット**: 10.0.1.0/24 (256 IPs)
- **Private Endpoint サブネット**: 10.0.2.0/24 (256 IPs)

#### NSG設計
- **適用対象**: Private Endpoint サブネットのみ（Container Appsサブネットには適用しない）
- **通常時ルール**:
  - デフォルトルールのみ（送信は許可）
- **障害注入時ルール**:
  - Redis向けの通信を動的にDENY（優先度100）
  - ルール名: "DenyRedisTraffic"

### 認証設計

#### Managed Identity
- Container AppにUser Assigned Managed Identityを使用
- Container Registry Pullロールを付与（AcrPull）
- Redisアクセスポリシーを付与

#### Redis Entra ID認証
- Azure Managed Redis（Redis Enterprise）を使用
- Entra ID認証を有効化（アクセスポリシー経由）
- パスワード認証は使用しない
- Container AppのManaged Identityにdefaultアクセスポリシーを付与

### データフロー

#### 正常時のフロー
```
1. クライアント → Container Apps Ingress (HTTPS)
2. Ingress → Container App
3. Container App → Entra ID (トークン取得)
4. Container App → Redis Private Endpoint (Entra IDトークンで認証)
5. Redis → Container App
6. Container App → Application Insights (テレメトリ)
7. Container App → クライアント (HTTP 200)
```

#### Redis障害時のフロー
```
1. クライアント → Container Apps Ingress (HTTPS)
2. Ingress → Container App
3. Container App → Entra ID (トークン取得)
4. Container App → Redis Private Endpoint (NSGでブロック)
5. Container App → Application Insights (エラーログ)
6. Container App → クライアント (HTTP 503)
```

#### 外部負荷テスト時のフロー
```
1. Locust → Container Apps Ingress (大量のHTTPSリクエスト)
2. Ingress → Container App (複数のレプリカに分散)
3. Container App → Redis (高頻度アクセス、Entra ID認証)
4. Container App → Application Insights (高負荷メトリクス)
5. Container App → Locust (レスポンス時間劣化)
```

#### Redis接続リセット時のフロー
```
1. クライアント → Container Apps Ingress (HTTPS)
2. Ingress → Container App
3. Container App → Redis接続プール (既存接続をクローズ)
4. Container App → Application Insights (リセットイベント記録)
5. Container App → クライアント (リセット完了応答)
6. 次回Redis操作時 → 新規接続確立
```

## インターフェース定義

### REST API仕様

#### ヘルスチェックエンドポイント
```http
GET /health
```
**レスポンス**:
```json
{
  "status": "healthy|unhealthy",
  "redis": {
    "connected": true|false,
    "latency_ms": 0
  },
  "timestamp": "2025-07-25T00:00:00Z"
}
```

#### メインエンドポイント
```http
GET /
```
**レスポンス**:
```json
{
  "message": "Hello from Container Apps Chaos Lab",
  "redis_data": "...",
  "timestamp": "2025-07-25T00:00:00Z"
}
```

#### 負荷制御エンドポイント
```http
POST /chaos/load
Content-Type: application/json

{
  "level": "low|medium|high",
  "duration_seconds": 60
}
```
**レスポンス**:
```json
{
  "status": "load_started",
  "level": "medium",
  "duration_seconds": 60
}
```

#### ハングアップエンドポイント
```http
POST /chaos/hang
Content-Type: application/json

{
  "duration_seconds": 0  // 0 = 永続的
}
```
**レスポンス**: なし（ハングアップするため）

#### Redis接続リセットエンドポイント
```http
POST /chaos/redis-reset
Content-Type: application/json

{
  "force": true|false  // オプション: 強制切断フラグ（デフォルト: true）
}
```
**レスポンス**:
```json
{
  "status": "redis_connections_reset",
  "connections_closed": 3,
  "timestamp": "2025-07-30T12:00:00Z"
}
```

#### ステータス確認エンドポイント
```http
GET /chaos/status
```
**レスポンス**:
```json
{
  "load": {
    "active": true|false,
    "level": "low|medium|high",
    "remaining_seconds": 30
  },
  "hang": {
    "active": true|false,
    "remaining_seconds": 0
  },
  "redis": {
    "connected": true|false,
    "connection_count": 3,
    "last_reset": "2025-07-30T12:00:00Z"
  }
}
```

## データモデル

### Redis データ構造
```python
# キー構造
key = "chaos_lab:{entity_type}:{entity_id}"

# 例
"chaos_lab:counter:requests" → int (リクエストカウンター)
"chaos_lab:data:sample" → JSON string (サンプルデータ)
"chaos_lab:health:last_check" → timestamp (最終ヘルスチェック時刻)
```

### アプリケーション内部状態
```python
class ChaosState:
    load_active: bool = False
    load_level: str = "low"  # low, medium, high
    load_end_time: Optional[datetime] = None
    hang_active: bool = False
    hang_end_time: Optional[datetime] = None
    redis_last_reset: Optional[datetime] = None
```

## エラー処理

### エラーマトリックス

| エラーシナリオ | HTTPステータス | エラーメッセージ | 対応 |
|--------------|--------------|----------------|-----|
| Redis接続失敗 | 503 | "Redis connection failed" | リトライ後、デグレード動作 |
| Redis認証失敗 | 503 | "Redis authentication failed" | トークン再取得、エラーログ |
| Redis タイムアウト | 504 | "Redis operation timeout" | タイムアウト値調整、エラーログ |
| 不正な負荷レベル | 400 | "Invalid load level" | 有効な値を返す |
| 内部エラー | 500 | "Internal server error" | スタックトレース記録 |
| ハングアップ中 | - | - | レスポンスなし |

### エラー処理フロー
```python
try:
    # Redis操作
    result = await redis_client.get(key)
except ConnectionError:
    # 接続エラー
    logger.error("Redis connection failed")
    return JSONResponse(
        status_code=503,
        content={"error": "Redis connection failed"}
    )
except AuthenticationError:
    # 認証エラー
    logger.error("Redis authentication failed")
    return JSONResponse(
        status_code=503,
        content={"error": "Redis authentication failed"}
    )
except TimeoutError:
    # タイムアウト
    logger.error("Redis operation timeout")
    return JSONResponse(
        status_code=504,
        content={"error": "Redis operation timeout"}
    )
except Exception as e:
    # その他のエラー
    logger.exception("Unexpected error")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )
```

## 単体テスト戦略

### テストカバレッジ目標
- コードカバレッジ: 80%以上
- 主要パスのカバレッジ: 100%

### テスト対象
1. **API エンドポイント**
   - 正常系レスポンス
   - エラーレスポンス
   - バリデーション

2. **Redis 操作**
   - Entra ID認証
   - 接続/切断
   - データ読み書き
   - エラーハンドリング

3. **負荷シミュレーション**
   - CPU負荷生成
   - メモリ負荷生成
   - タイマー動作

4. **ハングアップ機能**
   - 永続的ハング
   - 時限的ハング
   - 状態管理

5. **Redis接続リセット機能**
   - 接続プールの切断
   - 接続状態の確認
   - 自動再接続

### モックストラテジー
- Redis接続: AsyncMockを使用したカスタムモック
- Entra ID認証: azure-identityのDefaultAzureCredentialをモック
- 時刻: asyncio.sleepのモック
- HTTPクライアント: httpxのAsyncClientモック

## セキュリティ考慮事項

### ネットワークセキュリティ
- Container AppsはVNet統合で外部直接アクセスを防止
- RedisはPrivate Endpointのみでアクセス可能
- NSGで最小権限の原則を適用

### アプリケーションセキュリティ
- Managed Identityで認証（パスワード不要）
- 環境変数に機密情報を保存しない
- エラーメッセージに機密情報を含めない
- 入力値の適切なバリデーション

### 監視セキュリティ
- Application InsightsとLog Analyticsはパブリックアクセス（設計制約）
- 監視データに機密情報を含めない
- 適切なRBACの設定

## パフォーマンス考慮事項

### スケーリング設計
- Container Apps自動スケーリング設定
  - 最小レプリカ: 1
  - 最大レプリカ: 10
  - スケールルール: CPU使用率70%

### Redis接続プール
- 接続プール管理: redis-pyの自動管理
- 接続ポート: 10000（Azure Managed Redisのデフォルト）
- SSL/TLS: 有効（必須）
- トークンキャッシュ: DefaultAzureCredentialによる自動管理

### 負荷特性
- **アプリケーション内部負荷**:
  - 低負荷: CPU 20-30%、メモリ 100MB
  - 中負荷: CPU 50-60%、メモリ 500MB
  - 高負荷: CPU 80-90%、メモリ 1GB
- **外部負荷（Locust）**:
  - 段階的増加: 10→100→1000 users/秒
  - スパイク: 0→5000 users（瞬時）
  - 持続負荷: 500 users×10分間

## 技術スタック

### インフラストラクチャー
- **IaC**: Bicep
- **環境管理**: Azure Developer CLI (azd)
- **CI/CD**: GitHub Actions (将来的な拡張用)

### アプリケーション
- **言語**: Python 3.13
- **Webフレームワーク**: FastAPI
- **非同期処理**: asyncio
- **Redisクライアント**: redis (v6.2.0) + azure-identity
- **監視**: Azure Monitor OpenTelemetry (v1.6.12)
- **パッケージ管理**: uv (開発環境のみ)

### 開発ツール
- **テストフレームワーク**: pytest, pytest-asyncio
- **負荷テスト**: Locust
- **コード品質**: ruff (linting & formatting)
- **型チェック**: mypy
- **依存管理**: uv, pyproject.toml

## デプロイメントアーキテクチャ

### Azure Developer CLI構成
```
aca-chaos-lab/
├── azure.yaml          # azd設定
├── infra/             # Bicepテンプレート
│   ├── main.bicep     # メインテンプレート
│   ├── main.parameters.json
│   └── modules/       # Bicepモジュール
├── src/               # アプリケーションコード
│   ├── app/           # FastAPIアプリ
│   ├── Dockerfile     # 本番用Dockerfile
│   ├── pyproject.toml # uv設定（開発用）
│   └── requirements.txt # pip用（本番用）
├── tests/             # テストコード
│   └── locust/        # Locustシナリオ
└── scripts/           # 運用スクリプト
    ├── inject-network-failure.sh
    ├── clear-network-failures.sh
    ├── list-network-failures.sh
    ├── inject-deployment-failure.sh
    ├── list-revisions.sh
    └── azd-env-helper.sh
```

### 環境変数設計
```bash
# Redis接続
REDIS_HOST=<redis-name>.redis.azure.net
REDIS_PORT=10000
REDIS_SSL=true
# パスワードは不要（Entra ID認証）

# Application Insights
APPLICATIONINSIGHTS_CONNECTION_STRING=<connection-string>

# アプリケーション設定
APP_PORT=8000
LOG_LEVEL=INFO

# Azure環境
AZURE_CLIENT_ID=<managed-identity-client-id>
# AZURE_TENANT_IDは不要（DefaultAzureCredentialが自動検出）
```

### 開発環境でのuv使用

#### pyproject.toml
```toml
[project]
name = "aca-chaos-lab"
version = "0.1.0"
description = "Azure Container Apps Chaos Lab"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn>=0.27.0",
    "redis>=5.0.0",
    "azure-identity>=1.15.0",
    "azure-monitor-opentelemetry>=1.2.0",
    "pydantic>=2.5.0",
    "httpx>=0.26.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.1.0",
    "mypy>=1.8.0",
    "locust>=2.20.0",
]

[tool.ruff]
line-length = 88
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "ASYNC", "S", "B", "A", "C4", "T20", "SIM"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.13"
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true
```

#### 開発ワークフロー
```bash
# 開発環境のセットアップ
uv venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows

# 依存関係のインストール
uv pip install -e ".[dev]"

# requirements.txtの生成（本番用）
uv pip compile pyproject.toml -o requirements.txt
```

#### Dockerfile（本番用）
```dockerfile
FROM python:3.13-slim

WORKDIR /app

# 依存関係のインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションのコピー
COPY ./app ./app

# ポート設定
EXPOSE 8000

# 実行
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Redis Entra ID認証の実装

#### 概要

本アプリケーションでは、redis-pyライブラリの標準的な機能を活用し、Azure Managed Redis（Redis Enterprise）への接続を実装しています。主な特徴：

- **Entra ID認証**: DefaultAzureCredentialを使用したパスワードレス認証
- **接続プール管理**: redis-pyの内部接続プールによる効率的な接続管理
- **標準的なリトライ機構**: redis-pyのRetry/ExponentialBackoffを使用
- **自動再接続**: 接続エラー時の自動的な再接続処理

#### 接続管理の詳細

##### 1. 起動時の接続処理

```python
# アプリケーション起動時（lifespan内）
if settings.redis_enabled:
    redis_client = RedisClient(settings.redis_host, settings.redis_port, settings)
    try:
        await redis_client.connect()
        logger.info("Successfully connected to Redis at startup")
    except Exception as e:
        logger.warning(f"Failed to connect to Redis at startup: {e}")
        logger.info("Redis connection will be retried on first use")
        # 起動は継続 - 最初の操作時に再接続を試行
```

**設計方針**:
- 起動時の接続エラーでアプリケーションを停止させない
- 設定ミスなど恒久的な問題は運用時に検知・修正
- 一時的なネットワーク問題には自動的に対応

##### 2. リトライメカニズム

```python
# redis-pyの標準的なリトライ設定
retry_strategy = Retry(
    backoff=ExponentialBackoff(base=backoff_base, cap=backoff_cap),
    retries=max_retries
)

self.client = await redis.from_url(
    f"rediss://{self.host}:{self.port}",
    username=client_id,
    password=token,
    retry=retry_strategy,
    retry_on_error=[redis.ConnectionError, redis.TimeoutError],
    health_check_interval=30,
)
```

**デフォルト設定**:
- 最大リトライ回数: 1回
- 指数バックオフ: 1秒ベース、3秒上限
- ヘルスチェック間隔: 30秒
- 対象エラー: ConnectionError, TimeoutError

##### 3. 接続プール管理

```python
# 接続プール設定
max_connections=50  # 最大接続数
socket_timeout=3    # ソケットタイムアウト（秒）
socket_connect_timeout=3  # 接続タイムアウト（秒）
```

**接続プールの動作**:
- redis-pyが内部的に接続プールを管理
- 接続の再利用により効率的なリソース使用
- 自動的な接続の作成・破棄
- ヘルスチェックによる不正な接続の検出・削除

##### 4. 接続リセット機能

```python
async def reset_connections(self) -> int:
    """Reset all Redis connections."""
    async with self._connection_lock:
        if self.client and hasattr(self.client, "connection_pool"):
            # 接続プールのdisconnect()メソッドを使用
            # これは標準的な接続リセット方法
            closed_count = await pool.disconnect()
            self._connection_count = 0
            return closed_count
```

**リセット機能の特徴**:
- 接続プールの`disconnect()`メソッドを使用（標準的な方法）
- すべての既存接続を切断
- 次回操作時に自動的に新規接続を確立
- カオステスト用APIから呼び出し可能

#### エラーハンドリング

##### 1. 起動時のエラー

```python
# 起動時: エラーでも継続
try:
    await redis_client.connect()
except Exception as e:
    logger.warning(f"Failed to connect to Redis at startup: {e}")
    # アプリケーションは起動を継続
```

##### 2. 実行時のエラー

```python
# 実行時: redis-pyがリトライを実行
try:
    redis_data = await redis_client.get(key)
except Exception as e:
    # リトライ後も失敗した場合
    logger.error(f"Redis operation failed: {e}")
    # HTTPステータス503を返す
    return JSONResponse(status_code=503, ...)
```

##### 3. 接続リセット後の動作

```python
# リセット後: 自動再接続
1. /chaos/redis-reset APIを呼び出し
2. 既存の接続をすべて切断
3. 次のRedis操作で自動的に新規接続を確立
4. 一時的にエラーが発生する可能性があるが自動回復
```

#### 環境変数による設定

| 変数名 | 説明 | デフォルト値 |
|--------|------|------------|
| `REDIS_MAX_CONNECTIONS` | 接続プール最大接続数 | 50 |
| `REDIS_SOCKET_TIMEOUT` | ソケットタイムアウト（秒） | 3 |
| `REDIS_SOCKET_CONNECT_TIMEOUT` | 接続タイムアウト（秒） | 3 |
| `REDIS_MAX_RETRIES` | 最大リトライ回数 | 1 |
| `REDIS_BACKOFF_BASE` | 指数バックオフベース時間（秒） | 1 |
| `REDIS_BACKOFF_CAP` | 指数バックオフ最大時間（秒） | 3 |

## Locust負荷テスト設計

### テストシナリオ
1. **段階的負荷増加シナリオ**
   ```python
   # 10分かけて0→1000ユーザーまで増加
   stages = [
       {"duration": 120, "users": 100, "spawn_rate": 10},
       {"duration": 180, "users": 500, "spawn_rate": 50},
       {"duration": 300, "users": 1000, "spawn_rate": 100}
   ]
   ```

2. **スパイク負荷シナリオ**
   ```python
   # 瞬時に5000ユーザーを投入
   stages = [
       {"duration": 10, "users": 5000, "spawn_rate": 500},
       {"duration": 60, "users": 5000, "spawn_rate": 0},
       {"duration": 10, "users": 0, "spawn_rate": 500}
   ]
   ```

3. **持続負荷シナリオ**
   ```python
   # 500ユーザーで10分間継続
   stages = [
       {"duration": 30, "users": 500, "spawn_rate": 50},
       {"duration": 600, "users": 500, "spawn_rate": 0}
   ]
   ```

### テストエンドポイント
- メインページ（GET /）
- ヘルスチェック（GET /health）
- Redis読み書き操作を含むAPI


## 実装状況（2025-07-28）

すべての機能が実装済みで、本番環境で稼働中：

1. **基本インフラ** ✅
   - VNet、サブネット、NSG
   - Container Apps Environment（VNet統合）
   - Azure Managed Redis（Redis Enterprise）with Private Endpoint
   - User Assigned Managed Identity

2. **基本アプリケーション** ✅
   - FastAPIベースのWebアプリ
   - Redis接続とヘルスチェック（Entra ID認証）
   - Azure Monitor OpenTelemetry統合

3. **障害注入機能** ✅
   - NSGルール操作スクリプト（azd環境変数対応）
   - 負荷シミュレーションAPI（/chaos/load）
   - ハングアップAPI（/chaos/hang）
   - ステータス確認API（/chaos/status）

4. **負荷テストツール** ✅
   - Locustテストシナリオ（baseline、stress、spike、chaos）
   - 負荷テスト実行スクリプト
   - 結果分析とレポート生成

5. **運用ツール** ✅
   - Application Insightsダッシュボード
   - 包括的なドキュメント
   - Azure Developer CLI統合

6. **Redis接続リセット機能** ✅ (2025-07-30追加)
   - Redis接続リセットAPI（/chaos/redis-reset）
   - 接続プールの標準的なdisconnect()メソッドを使用
   - 自動再接続機能
   - ネットワーク障害スクリプトとの統合

## Container Apps応答監視アラート設計

### アラートアーキテクチャ

```mermaid
graph TD
    CA[Container App] -->|Generates Metrics| M[Azure Monitor Metrics]
    M --> AR1[5xx Error Alert Rule]
    M --> AR2[Response Time Alert Rule]
    AR1 -->|Evaluates| T1{Threshold Exceeded?}
    AR2 -->|Evaluates| T2{Threshold Exceeded?}
    T1 -->|Yes| A1[Alert Fired]
    T2 -->|Yes| A2[Alert Fired]
    A1 --> P[Azure Portal Notifications]
    A2 --> P
    
    style CA fill:#f9f,stroke:#333,stroke-width:2px
    style AR1 fill:#bbf,stroke:#333,stroke-width:2px
    style AR2 fill:#bbf,stroke:#333,stroke-width:2px
```

### アラートルール仕様

#### 1. 5xx系エラーアラート

```bicep
resource alert5xxStatusCodes 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${containerAppName}-5xx-alerts'
  location: 'global'
  properties: {
    severity: 2
    enabled: true
    scopes: [containerAppResourceId]
    evaluationFrequency: 'PT1M'
    windowSize: 'PT5M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [{
        name: 'HTTP5xxErrors'
        metricName: 'Requests'
        metricNamespace: 'Microsoft.App/containerApps'
        dimensions: [{
          name: 'StatusCodeCategory'
          operator: 'Include'
          values: ['5xx']
        }]
        operator: 'GreaterThan'
        threshold: 5
        timeAggregation: 'Count'
        criterionType: 'StaticThresholdCriterion'
      }]
    }
    autoMitigate: true
  }
}
```

**設計ポイント**:
- メトリクス: Container Appsの標準メトリクス「Requests」
- フィルタ: StatusCodeCategoryディメンションで5xxをフィルタリング
- 閾値: 5分間で5回以上の5xxエラー
- 評価頻度: 1分ごと
- 重要度: 2（警告レベル）

#### 2. 応答時間アラート

```bicep
resource alertResponseTime 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${containerAppName}-response-time-alerts'
  location: 'global'
  properties: {
    severity: 2
    enabled: true
    scopes: [containerAppResourceId]
    evaluationFrequency: 'PT1M'
    windowSize: 'PT5M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [{
        name: 'HighResponseTime'
        metricName: 'ResponseTime'
        metricNamespace: 'Microsoft.App/containerApps'
        operator: 'GreaterThan'
        threshold: 5000
        timeAggregation: 'Average'
        criterionType: 'StaticThresholdCriterion'
      }]
    }
    autoMitigate: true
  }
}
```

**設計ポイント**:
- メトリクス: Container Appsの標準メトリクス「ResponseTime」
- 閾値: 平均応答時間5000ミリ秒（5秒）
- 集計方法: 5分間の平均値
- 評価頻度: 1分ごと
- 重要度: 2（警告レベル）

### Bicepモジュール統合

#### alert-rules.bicep

```bicep
param location string
param tags object
param containerAppName string

// Container Appリソースの参照
resource containerApp 'Microsoft.App/containerApps@2025-01-01' existing = {
  name: containerAppName
}

// 5xxエラーアラートルール
resource alert5xxStatusCodes 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  // ... 上記の定義
}

// 応答時間アラートルール
resource alertResponseTime 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  // ... 上記の定義
}

output alert5xxId string = alert5xxStatusCodes.id
output alertResponseTimeId string = alertResponseTime.id
```

#### main.bicepへの統合

```bicep
// 既存のモジュール定義...

module alertRules './modules/alert-rules.bicep' = {
  name: 'alert-rules'
  scope: resourceGroup
  params: {
    location: location
    tags: tags
    containerAppName: containerApp.outputs.containerAppName
  }
  dependsOn: [
    containerApp
  ]
}

// 新しい出力の追加
output AZURE_ALERT_5XX_ID string = alertRules.outputs.alert5xxId
output AZURE_ALERT_RESPONSE_TIME_ID string = alertRules.outputs.alertResponseTimeId
```

### 実装考慮事項

1. **アクショングループ**:
   - 現時点では定義しない（ユーザー要件）
   - 将来的にメール、SMS、Webhook通知を追加可能

2. **アラートの調整**:
   - 閾値は環境に応じて調整可能
   - 評価頻度とウィンドウサイズの最適化

3. **監視の拡張性**:
   - 追加のメトリクスアラート（CPU、メモリ使用率など）
   - カスタムメトリクスの追加

4. **コスト考慮**:
   - メトリクスアラートは低コスト
   - 評価頻度の調整でコスト最適化可能
