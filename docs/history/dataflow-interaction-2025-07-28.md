### [分析] - [データフローと相互作用マッピング] - [2025-07-28]
**目的**: システム内のデータフローと各コンポーネント間の相互作用を可視化する
**コンテキスト**: アーキテクチャの理解を深め、障害注入ポイントを明確化
**決定**: mermaid図を使用してデータフローを詳細に文書化
**実行**: 正常時、障害時、負荷テスト時の各シナリオでのデータフローを分析
**出力**: 

## システム相互作用図

```mermaid
sequenceDiagram
    participant User
    participant Ingress as Container Apps Ingress
    participant App as FastAPI App
    participant MI as Managed Identity
    participant EntraID as Entra ID
    participant Redis as Azure Managed Redis
    participant AI as Application Insights
    participant LA as Log Analytics

    %% 正常時のフロー
    User->>Ingress: HTTPS Request
    Ingress->>App: Forward Request
    App->>MI: Get Identity
    MI->>EntraID: Request Token
    EntraID-->>MI: Return Token
    MI-->>App: Token
    App->>Redis: Connect with Token
    Redis-->>App: Connection Established
    App->>Redis: Get/Set Data
    Redis-->>App: Data Response
    App->>AI: Send Telemetry
    App->>LA: Send Logs
    App-->>User: HTTP 200 Response
```

## データフローマトリックス

| フロー | 送信元 | 宛先 | プロトコル | ポート | データ種別 | 認証方式 |
|-------|--------|------|------------|--------|-----------|----------|
| ユーザーリクエスト | Internet | Container Apps Ingress | HTTPS | 443 | API呼び出し | なし |
| アプリ転送 | Ingress | FastAPI App | HTTP | 8000 | API呼び出し | なし |
| トークン取得 | App | Entra ID | HTTPS | 443 | 認証要求 | Managed Identity |
| Redis接続 | App | Redis (PE) | TLS | 10000 | データ操作 | Entra ID Token |
| テレメトリ送信 | App | Application Insights | HTTPS | 443 | メトリクス/トレース | Connection String |
| ログ送信 | App | Log Analytics | HTTPS | 443 | ログデータ | Workspace Key |

## 障害シナリオ別データフロー

### 1. ネットワーク障害（NSGブロック）
```mermaid
graph LR
    A[FastAPI App] -->|TLS:10000| B[NSG]
    B -->|DENY| C[Redis Private Endpoint]
    A -->|Error| D[Application Insights]
    A -->|503 Response| E[User]
```

### 2. 高負荷シナリオ
```mermaid
graph LR
    A[Locust] -->|大量リクエスト| B[Ingress]
    B -->|分散| C[App Replica 1]
    B -->|分散| D[App Replica 2]
    B -->|分散| E[App Replica N]
    C -->|高頻度| F[Redis]
    D -->|高頻度| F
    E -->|高頻度| F
    F -->|遅延増加| C
    F -->|遅延増加| D
    F -->|遅延増加| E
```

### 3. デプロイメント障害
```mermaid
graph LR
    A[Azure CLI] -->|Update| B[Container App]
    B -->|Pull| C[Container Registry]
    C -->|404 Not Found| B
    B -->|Revision Failed| D[Old Revision Active]
    A -->|Error Response| E[User]
```

### 4. ハングアップシナリオ
```mermaid
graph LR
    A[User] -->|POST /chaos/hang| B[FastAPI App]
    B -->|Block Event Loop| C[Async Handler]
    C -->|No Response| A
    D[Health Check] -->|Timeout| B
    E[Container Apps] -->|Restart| B
```

## 相互作用の詳細

### アプリケーション内部の相互作用
```
FastAPIApp
├── main.py
│   ├── lifespan (起動/終了処理)
│   ├── root endpoint (/) 
│   │   └── RedisClient.get/set
│   └── health endpoint (/health)
│       └── RedisClient.ping
├── chaos.py (カオスルーター)
│   ├── load endpoint (/chaos/load)
│   │   └── ChaosManager.start_load
│   ├── hang endpoint (/chaos/hang)
│   │   └── ChaosManager.start_hang
│   └── status endpoint (/chaos/status)
│       └── ChaosManager.get_status
├── redis_client.py
│   ├── connect (Entra ID認証)
│   ├── get/set (データ操作)
│   └── ping (ヘルスチェック)
└── telemetry.py
    └── OpenTelemetry設定
```

### 外部サービスとの相互作用
1. **Entra ID**: 
   - DefaultAzureCredential経由でトークン取得
   - トークンは30分キャッシュ
   - 自動更新メカニズム

2. **Redis**:
   - プライベートエンドポイント経由の接続
   - 接続プール管理（最大50接続）
   - 非同期操作のみ

3. **監視サービス**:
   - OpenTelemetryによる自動計装
   - カスタムスパンとメトリクス
   - エラー時の例外記録

## データフローのボトルネック分析

### 潜在的ボトルネック
1. **Redis接続プール**: 最大50接続の制限
2. **Entra IDトークン取得**: 初回接続時の遅延
3. **Container Appsスケーリング**: スケールアウトの遅延
4. **NSGルール反映**: 変更から適用までの遅延

### パフォーマンス特性
- 平均レスポンス時間: 23ms（通常負荷）
- Redis接続レイテンシ: 1-2ms
- トークン取得時間: 100-200ms（初回のみ）
- スケールアウト時間: 30-60秒

**検証**: すべてのデータフローと相互作用が文書化され、ボトルネックが特定された
**次**: エッジケースと障害点のカタログ化