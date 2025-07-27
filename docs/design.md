# Azure Container Apps Chaos Lab - 技術設計書

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
- **Container Apps サブネット**: 10.0.0.0/23 (512 IPs)
- **Private Endpoint サブネット**: 10.0.2.0/24 (256 IPs)

#### NSG設計
- **通常時ルール**:
  - Inbound: Container Apps管理トラフィックを許可
  - Outbound: インターネット、Redis、監視サービスへの通信を許可
- **障害注入時ルール**:
  - Redis向けの通信を動的にDENY（優先度100）
  - ルール名: "DenyRedisTraffic"

### 認証設計

#### Managed Identity
- Container AppにSystem Assigned Managed Identityを有効化
- Redis Data Ownerロールを付与
- Application InsightsへのメトリクスPublisherロールを付与

#### Redis Entra ID認証
- Entra ID認証を有効化
- パスワード認証を無効化
- Container AppのManaged IdentityにRedis Data Ownerロールを付与

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

### モックストラテジー
- Redis接続: redis-py-mockを使用
- Entra ID認証: azure-identityのモック
- 時刻: freezegunを使用
- HTTPクライアント: httpxのモック機能を使用

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
- 接続プール最大サイズ: 50
- 接続タイムアウト: 5秒
- コマンドタイムアウト: 2秒
- トークンキャッシュ: 30分

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
- **Redisクライアント**: redis-py (async) + azure-identity
- **監視**: Azure Application Insights SDK
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
    ├── inject-failure.sh
    ├── restore-normal.sh
    └── run-load-test.sh
```

### 環境変数設計
```bash
# Redis接続
REDIS_HOST=<redis-name>.redis.cache.windows.net
REDIS_SSL=true
# パスワードは不要（Entra ID認証）

# Application Insights
APPLICATIONINSIGHTS_CONNECTION_STRING=<connection-string>

# アプリケーション設定
APP_PORT=8000
LOG_LEVEL=INFO

# Azure環境
AZURE_TENANT_ID=<tenant-id>
AZURE_CLIENT_ID=<managed-identity-client-id>
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
target-version = "py311"

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

```python
from azure.identity import DefaultAzureCredential
import redis.asyncio as redis

class RedisClient:
    def __init__(self, host: str):
        self.host = host
        self.credential = DefaultAzureCredential()
        self.client = None
    
    async def connect(self):
        # Entra IDトークンを取得
        token = self.credential.get_token(
            "https://redis.azure.com/.default"
        )
        
        # Redisクライアントを初期化
        self.client = redis.Redis(
            host=self.host,
            port=6380,
            ssl=True,
            username=token.token,  # Entra IDトークンをユーザー名として使用
            decode_responses=True
        )
    
    async def get(self, key: str):
        return await self.client.get(key)
    
    async def set(self, key: str, value: str):
        return await self.client.set(key, value)
```

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

## 実装の優先順位

1. **基本インフラ** (優先度: 高)
   - VNet、サブネット、NSG
   - Container Apps Environment
   - Redis with Private Endpoint (Entra ID認証有効)

2. **基本アプリケーション** (優先度: 高)
   - FastAPIベースのWebアプリ
   - Redis接続とヘルスチェック（Entra ID認証）
   - Application Insights統合

3. **障害注入機能** (優先度: 中)
   - NSGルール操作スクリプト
   - 負荷シミュレーションAPI
   - ハングアップAPI

4. **負荷テストツール** (優先度: 中)
   - Locustテストシナリオ
   - 負荷テスト実行スクリプト
   - 結果分析ツール

5. **運用ツール** (優先度: 低)
   - 監視ダッシュボード
   - ドキュメント整備
   - CI/CDパイプライン
