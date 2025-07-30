### 分析 - データフローと相互作用のマッピング - 2025-07-30
**目的**: システム内のすべてのデータフローと相互作用を詳細にマッピングする
**コンテキスト**: アーキテクチャ設計書の分析とコード構造の理解完了
**決定**: データフローを正常系、異常系、負荷系の3つのカテゴリに分類して文書化
**実行**: 各フローのシーケンス図と相互作用パターンを作成

## システム相互作用図

### 主要コンポーネント間の相互作用
```mermaid
graph TB
    CLIENT[External Client]
    LOCUST[Locust Load Tester]
    INGRESS[Container Apps Ingress]
    APP[FastAPI Application]
    REDIS[Azure Managed Redis]
    ENTRA[Entra ID]
    AI[Application Insights]
    LAW[Log Analytics]
    NSG[Network Security Group]
    SCRIPTS[Management Scripts]
    
    CLIENT -->|HTTPS| INGRESS
    LOCUST -->|HTTPS Load| INGRESS
    INGRESS -->|HTTP| APP
    APP -->|Token Request| ENTRA
    APP -->|Redis Protocol| REDIS
    APP -->|Telemetry| AI
    APP -->|Logs| LAW
    NSG -.->|Block/Allow| REDIS
    SCRIPTS -->|Azure CLI| NSG
    SCRIPTS -->|Azure CLI| APP
```

## 正常時のデータフロー

### 1. アプリケーション起動フロー
```mermaid
sequenceDiagram
    participant CA as Container App
    participant MI as Managed Identity
    participant ENTRA as Entra ID
    participant AI as App Insights
    participant REDIS as Redis
    
    CA->>CA: Load environment variables
    CA->>CA: Initialize FastAPI
    CA->>AI: Configure OpenTelemetry
    CA->>MI: Request identity token
    MI->>ENTRA: Get access token
    ENTRA-->>MI: Return token
    MI-->>CA: Provide token
    CA->>REDIS: Test connection with token
    REDIS-->>CA: Connection successful
    CA->>AI: Log startup complete
```

### 2. HTTPリクエスト処理フロー（正常系）
```mermaid
sequenceDiagram
    participant CLIENT as Client
    participant INGRESS as Ingress
    participant APP as FastAPI
    participant REDIS as Redis
    participant AI as App Insights
    
    CLIENT->>INGRESS: GET / (HTTPS)
    INGRESS->>APP: Forward request
    APP->>APP: Create trace span
    APP->>REDIS: GET chaos_lab:counter:requests
    REDIS-->>APP: Return counter value
    APP->>REDIS: INCR chaos_lab:counter:requests
    REDIS-->>APP: Acknowledge
    APP->>AI: Send telemetry
    APP-->>INGRESS: HTTP 200 + JSON
    INGRESS-->>CLIENT: HTTPS response
```

### 3. ヘルスチェックフロー
```mermaid
sequenceDiagram
    participant PROBE as Health Probe
    participant APP as FastAPI
    participant REDIS as Redis
    
    PROBE->>APP: GET /health
    APP->>APP: Check internal state
    APP->>REDIS: PING
    REDIS-->>APP: PONG
    APP->>APP: Calculate latency
    APP-->>PROBE: {"status": "healthy", "redis": {"connected": true, "latency_ms": 5}}
```

## 障害時のデータフロー

### 1. Redis接続障害フロー（NSGブロック）
```mermaid
sequenceDiagram
    participant CLIENT as Client
    participant APP as FastAPI
    participant NSG as NSG
    participant REDIS as Redis
    participant AI as App Insights
    
    Note over NSG: DenyRedisTraffic rule active
    CLIENT->>APP: GET /
    APP->>APP: Get Redis connection
    APP->>NSG: Connect to Redis
    NSG--X APP: Connection blocked
    APP->>APP: Handle ConnectionError
    APP->>AI: Log error event
    APP-->>CLIENT: HTTP 503 {"error": "Redis connection failed"}
```

### 2. 認証障害フロー
```mermaid
sequenceDiagram
    participant APP as FastAPI
    participant MI as Managed Identity
    participant ENTRA as Entra ID
    participant REDIS as Redis
    participant AI as App Insights
    
    APP->>MI: Request token
    MI->>ENTRA: Get access token
    ENTRA-->>MI: Token expired/invalid
    MI-->>APP: Authentication failed
    APP->>REDIS: Connect with invalid token
    REDIS-->>APP: Authentication error
    APP->>AI: Log auth failure
    APP->>APP: Return degraded response
```

### 3. ハングアップフロー
```mermaid
sequenceDiagram
    participant CLIENT as Client
    participant APP as FastAPI
    participant MONITOR as Container Monitor
    
    CLIENT->>APP: POST /chaos/hang {"duration_seconds": 0}
    APP->>APP: Set hang_active = true
    APP->>APP: await asyncio.Event()
    Note over APP: Infinite wait
    CLIENT->>CLIENT: Timeout waiting
    MONITOR->>APP: Health check timeout
    MONITOR->>MONITOR: Mark unhealthy
    MONITOR->>APP: Restart container
```

## 負荷時のデータフロー

### 1. 内部負荷生成フロー
```mermaid
sequenceDiagram
    participant CLIENT as Client
    participant APP as FastAPI
    participant CPU as CPU Task
    participant MEM as Memory Task
    participant AI as App Insights
    
    CLIENT->>APP: POST /chaos/load {"level": "high", "duration_seconds": 60}
    APP->>APP: Set load parameters
    APP->>CPU: Start CPU intensive tasks
    APP->>MEM: Start memory allocation
    APP-->>CLIENT: {"status": "load_started"}
    
    loop Every second for 60s
        CPU->>CPU: Perform calculations
        MEM->>MEM: Allocate/deallocate memory
        APP->>AI: Send metrics (CPU%, Memory MB)
    end
    
    APP->>APP: Clear load state
```

### 2. 外部負荷フロー（Locust）
```mermaid
sequenceDiagram
    participant LOCUST as Locust Workers
    participant INGRESS as Ingress
    participant APP1 as App Replica 1
    participant APP2 as App Replica 2
    participant REDIS as Redis
    participant SCALER as Autoscaler
    
    par Concurrent requests
        LOCUST->>INGRESS: 1000 req/s
        INGRESS->>APP1: Forward 50%
        INGRESS->>APP2: Forward 50%
    end
    
    APP1->>REDIS: High frequency ops
    APP2->>REDIS: High frequency ops
    
    Note over APP1,APP2: CPU > 70%
    SCALER->>SCALER: Detect high load
    SCALER->>INGRESS: Scale to 5 replicas
```

### 3. カスケード障害フロー
```mermaid
sequenceDiagram
    participant SCRIPT as Chaos Script
    participant NSG as NSG
    participant APP as FastAPI
    participant REDIS as Redis
    participant CLIENT as Clients
    
    SCRIPT->>NSG: Add DenyRedisTraffic rule
    CLIENT->>APP: Normal requests
    APP->>REDIS: Connection attempt
    NSG--X APP: Blocked
    APP->>APP: Redis unavailable
    
    SCRIPT->>APP: POST /chaos/load high
    APP->>APP: Start high CPU/memory
    
    CLIENT->>APP: More requests
    APP-->>CLIENT: Slow responses
    
    Note over APP: Resource exhaustion
    APP-->>CLIENT: Timeouts begin
```

## 管理操作フロー

### 1. NSGルール操作フロー
```mermaid
sequenceDiagram
    participant ADMIN as Administrator
    participant SCRIPT as inject-network-failure.sh
    participant AZCLI as Azure CLI
    participant NSG as NSG
    participant APP as Application
    
    ADMIN->>SCRIPT: Execute script
    SCRIPT->>SCRIPT: Load azd environment
    SCRIPT->>AZCLI: az network nsg rule create
    AZCLI->>NSG: Add DenyRedisTraffic
    NSG-->>AZCLI: Rule created
    SCRIPT->>ADMIN: Display rule details
    
    Note over APP: Redis connections start failing
```

### 2. デプロイメント障害注入フロー
```mermaid
sequenceDiagram
    participant ADMIN as Administrator
    participant SCRIPT as inject-deployment-failure.sh
    participant AZCLI as Azure CLI
    participant ACA as Container Apps
    
    ADMIN->>SCRIPT: Execute with bad image
    SCRIPT->>AZCLI: az containerapp update
    AZCLI->>ACA: Create new revision
    ACA->>ACA: Pull non-existent image
    ACA-->>AZCLI: Image pull failed
    SCRIPT->>ADMIN: Show failure status
    
    Note over ACA: Previous revision remains active
```

## データモデル相互作用

### Redis データ操作パターン
```python
# カウンター操作
GET "chaos_lab:counter:requests" → int/None
INCR "chaos_lab:counter:requests" → int

# サンプルデータ操作
SET "chaos_lab:data:sample" '{"timestamp": "...", "value": "..."}' → OK
GET "chaos_lab:data:sample" → JSON string

# ヘルスチェック記録
SET "chaos_lab:health:last_check" "2025-07-30T12:00:00Z" → OK
EXPIRE "chaos_lab:health:last_check" 300 → 1
```

### 内部状態管理
```python
# グローバル状態（メモリ内）
chaos_state = ChaosState()

# 状態更新フロー
POST /chaos/load → chaos_state.load_active = True
                 → chaos_state.load_level = "high"
                 → chaos_state.load_end_time = now() + duration

# 状態確認フロー
GET /chaos/status → return chaos_state.to_dict()

# 自動クリーンアップ
Background task → if now() > load_end_time:
                    chaos_state.load_active = False
```

## テレメトリフロー

### OpenTelemetry トレーシング
```mermaid
graph LR
    REQ[HTTP Request] --> SPAN1[HTTP Server Span]
    SPAN1 --> SPAN2[Redis Operation Span]
    SPAN2 --> SPAN3[Token Acquisition Span]
    SPAN1 --> SPAN4[Chaos Operation Span]
    SPAN1 --> AI[Application Insights]
    
    SPAN2 -.-> ATTR1[redis.host]
    SPAN2 -.-> ATTR2[redis.operation]
    SPAN3 -.-> ATTR3[auth.method]
    SPAN4 -.-> ATTR4[chaos.type]
```

### メトリクス収集
```python
# カスタムメトリクス
- redis.connection.success: Counter
- redis.connection.failure: Counter
- redis.operation.latency: Histogram
- chaos.load.active: Gauge
- chaos.load.level: Gauge
- app.memory.usage: Gauge
- app.cpu.usage: Gauge
```

**出力**: データフローと相互作用の包括的なマッピング完了
**検証**: すべての主要なデータフローパターンと相互作用が文書化された
**次**: エッジケースと障害のカタログ化に進む