### フェーズ3: 実装 - 設定調整とデプロイ - 2025-07-28T12:30:00Z
**目的**: 設定を確認し、Azure環境にデプロイする
**コンテキスト**: 
- 仕様変更を反映済み
- コードとインフラストラクチャは実装済み
- Redisポートは既に10000に設定されている
**決定**: Azure Developer CLIを使用してデプロイを実行
**実行**: 

## 1. 設定確認

### Redisポート設定
- ✅ **確認完了**: redis_port = 10000（config.pyで設定済み）
- Azure Managed Redisのデフォルトポートと一致

### 環境変数マッピング
- ✅ **azd環境変数の自動マッピング**:
  - `AZURE_REDIS_HOST` → `redis_host`
  - `AZURE_REDIS_PORT` → `redis_port`
  - `AZURE_MANAGED_IDENTITY_CLIENT_ID` → `azure_client_id`
  - `APPLICATIONINSIGHTS_CONNECTION_STRING` → 同名

## 2. Azure環境セットアップ

### azdプロジェクト初期化
```bash
# プロジェクトルートで実行
azd init

# 環境名を入力（例: dev）
# サブスクリプションを選択
# リージョンを選択（例: japaneast）
```

### 認証
```bash
azd auth login
```

## 3. インフラストラクチャとアプリケーションのデプロイ

### ワンコマンドデプロイ
```bash
azd up
```

このコマンドで以下が実行されます：
1. **インフラストラクチャのプロビジョニング**:
   - VNet（Container Appsサブネット: 10.0.1.0/24）
   - Container Apps環境（Consumptionワークロードプロファイル）
   - Azure Managed Redis（プライベートエンドポイント）
   - Container Registry
   - 監視リソース（Log Analytics、Application Insights）

2. **アプリケーションのデプロイ**:
   - Dockerイメージのビルド
   - Container Registryへのプッシュ
   - Container Appへのデプロイ
   - マネージドアイデンティティの設定

## 4. デプロイ後の確認事項

### 環境変数の確認
```bash
# デプロイされた環境変数を確認
azd env get-values
```

### エンドポイントURLの取得
```bash
# アプリケーションURLを取得
APP_URL=$(azd env get-value AZURE_CONTAINER_APP_URI)
echo "Application URL: $APP_URL"
```

### ヘルスチェック
```bash
# ヘルスチェックエンドポイントをテスト
curl "${APP_URL}/health"
```

## 5. 予想される結果

### 成功時の出力例
```
Deploying services (azd deploy)

  (✓) Done: Deploying service app
  - Endpoint: https://ca-aca-chaos-lab-xxx.azurecontainerapps.io/

SUCCESS: Your application was provisioned and deployed to Azure
```

### ヘルスチェックレスポンス例
```json
{
  "status": "healthy",
  "redis": {
    "connected": true,
    "latency_ms": 5
  },
  "timestamp": "2025-07-28T12:45:00Z"
}
```

**出力**: デプロイ手順と確認項目
**検証**: 設定確認完了、デプロイ準備完了
**次**: 実際のデプロイ実行と動作検証