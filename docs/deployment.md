# デプロイメントガイド

このガイドでは、Azure Container Apps Chaos LabをAzureサブスクリプションにデプロイする手順を説明します。

## アーキテクチャ概要

Azure Chaos Labは、**Azure Verified Module (AVM) v0.2.0**を基盤とした、Infrastructure as Code による完全宣言的なデプロイメントを実現しています。

### 主要な特徴

- **Container App Upsert戦略**: AVM v0.2.0による条件付きデプロイメント
- **統合ヘルスプローブ**: containerProbesパラメータによる宣言的管理
- **外部依存排除**: postprovisionフック不使用、純粋なInfrastructure as Code
- **マネージドID統合**: Redis接続とACRアクセスの自動設定

## 前提条件

1. **Azureサブスクリプション**に以下のリソースプロバイダーが登録されていること：
   - Microsoft.App
   - Microsoft.Cache
   - Microsoft.ContainerRegistry
   - Microsoft.OperationalInsights

2. **インストール済みツール**：
   - Azure CLI v2.75.0以上
   - Azure Developer CLI (`azd`) v1.18.0以上
   - Docker v28.3以上
   - jq v1.6以上（JSONデータ処理）
   - Git
   - Bash シェル（Linux/macOS標準搭載、WindowsはWSL2/Git Bash/Azure Cloud Shell）
   - Python 3.13以上（負荷テスト実行用）

3. **権限**：
   - サブスクリプション/リソースグループへのContributorロール
   - マネージドアイデンティティの作成権限
   - ネットワーク構成権限

## ステップ1: クローンと準備

```bash
# リポジトリのクローン
git clone https://github.com/torumakabe/aca-chaos-lab.git
cd aca-chaos-lab

# Azure Developer CLIの初期化
azd init

# プロンプトが表示されたら：
# - 環境名: 一意の名前を選択（例: "chaoslab-dev"）
# - Azureサブスクリプション: サブスクリプションを選択
# - Azureロケーション: サポートされているリージョンを選択（例: "eastus"）
```

## ステップ2: 環境の設定

`.azure/<environment-name>/.env`を作成または修正：

```bash
# オプション: リソースグループ名を指定
AZURE_RESOURCE_GROUP_NAME=rg-chaos-lab

# オプション: コンテナレジストリ名（グローバルに一意である必要があります）
AZURE_CONTAINER_REGISTRY_NAME=acrchaoslab<unique>

# オプション: Redis Enterprise名
REDIS_NAME=redis-chaos-lab
```

## ステップ3: インフラストラクチャとアプリケーションのデプロイ

```bash
# すべてをデプロイ
azd up

# 以下が実行されます：
# 1. リソースグループの作成
# 2. インフラストラクチャのデプロイ（Bicep）
# 3. コンテナイメージのビルドとプッシュ
# 4. Container Appsへのアプリケーションデプロイ
# 5. ヘルスプローブの宣言的設定（AVM v0.2.0 containerProbesパラメータ）
```

### デプロイメントの特徴

- **外部スクリプト不要**: postprovisionフックは使用せず、すべてBicepテンプレート内で完結
- **ヘルスプローブ統合**: Liveness（TCP 8000、60秒遅延）とReadiness（HTTP /health、10秒遅延）が自動設定
- **一元管理**: すべてのリソース設定がInfrastructure as Codeとして管理

### 実際のデプロイ結果（2025年8月14日 AVM v0.2.0移行後）

```
Deploying services (azd deploy)

  (✓) Done: Deploying service app
  - Endpoint: https://ca-app-wjrjbjnb4etie.wittysand-98a6c05f.japaneast.azurecontainerapps.io/

SUCCESS: Your application was provisioned and deployed to Azure
```

**デプロイ時間**: 約4分46秒（AVM v0.2.0による効率化）
**特徴**: postprovisionフック削除により、デプロイメントが簡素化され高速化

## ステップ4: Redisアクセスの設定

デプロイ後、Redis Enterpriseのアクセスを手動で設定する必要があります：

1. Azure Portalに移動
2. Redis Enterpriseリソースを見つける
3. 「データベース」→ データベースを選択
4. 「アクセス制御」→「アクセスポリシーの追加」をクリック
5. 設定：
   - 名前: `container-app-access`
   - 権限: `Read`、`Write`
   - ユーザー: Container Appのマネージドアイデンティティを追加

## ステップ5: デプロイの確認

1. アプリケーションURLを取得：
   ```bash
   azd show
   # "app"エンドポイントURLを確認
   ```

2. ヘルスエンドポイントをテスト：
   ```bash
   curl https://<your-app>.azurecontainerapps.io/health
   ```

   期待される応答：
   ```json
   {
     "status": "healthy",
     "redis": {
       "connected": true,
       "latency_ms": 2
     },
     "timestamp": "2025-07-28T08:54:03.671855+00:00"
   }
   ```

3. Redis接続を確認：
   ```bash
   curl https://<your-app>.azurecontainerapps.io/
   ```

   期待される応答：
   ```json
   {
     "message": "Hello from Container Apps Chaos Lab",
     "redis_data": "Data created at 2025-07-28T05:13:39.317321+00:00",
     "timestamp": "2025-07-28T08:54:11.928616+00:00"
   }
   ```

## ステップ6: モニタリングの設定

Application Insightsは自動的に設定されます。テレメトリを表示するには：

1. Azure PortalでApplication Insightsに移動
2. 確認項目：
   - ライブメトリクス（リアルタイムデータ）
   - トランザクション検索（リクエスト）
   - 失敗（エラー追跡）
   - パフォーマンス（応答時間）

## 手動デプロイオプション

### Bicepを直接使用

```bash
# 変数の設定
RESOURCE_GROUP="rg-chaos-lab"
LOCATION="eastus"

# リソースグループの作成
az group create --name $RESOURCE_GROUP --location $LOCATION

# インフラストラクチャのデプロイ
az deployment group create \
  --resource-group $RESOURCE_GROUP \
  --template-file infra/main.bicep \
  --parameters environmentName=dev

# コンテナのビルドとプッシュ
az acr build --registry <acr-name> --image aca-chaos-lab:latest src/

# 新しいイメージでContainer Appを更新
az containerapp update \
  --name <app-name> \
  --resource-group $RESOURCE_GROUP \
  --image <acr-name>.azurecr.io/aca-chaos-lab:latest
```

### ローカルDockerビルド

```bash
# ローカルビルド
cd src
docker build -t aca-chaos-lab:latest .

# ACR用にタグ付け
docker tag aca-chaos-lab:latest <acr-name>.azurecr.io/aca-chaos-lab:latest

# ACRにプッシュ
az acr login --name <acr-name>
docker push <acr-name>.azurecr.io/aca-chaos-lab:latest
```

## トラブルシューティング

### Container Appが起動しない

1. コンテナログを確認：
   ```bash
   az containerapp logs show \
     --name <app-name> \
     --resource-group $RESOURCE_GROUP \
     --type console
   ```

2. 環境変数を確認：
   ```bash
   az containerapp show \
     --name <app-name> \
     --resource-group $RESOURCE_GROUP \
     --query properties.template.containers[0].env
   ```

### Redis接続エラー

1. マネージドアイデンティティの割り当てを確認：
   ```bash
   az containerapp identity show \
     --name <app-name> \
     --resource-group $RESOURCE_GROUP
   ```

2. Redisネットワーク接続を確認：
   - プライベートエンドポイントが作成されているか確認
   - VNet統合を確認
   - NSGルールを確認

3. Redisアクセスポリシーを検証：
   - マネージドアイデンティティが追加されているか確認
   - 権限にRead/Writeが含まれているか確認

### Application Insightsが機能しない

1. 接続文字列を確認：
   ```bash
   az containerapp show \
     --name <app-name> \
     --resource-group $RESOURCE_GROUP \
     --query "properties.template.containers[0].env[?name=='APPLICATIONINSIGHTS_CONNECTION_STRING'].value"
   ```

2. Application Insightsリソースが存在することを確認
3. 適切なネットワーク接続を確保

## アプリケーションの更新

### Azure Developer CLIを使用

```bash
# 更新と再デプロイ
azd deploy
```

### 手動更新

```bash
# 新しいイメージのビルド
cd src
docker build -t <acr-name>.azurecr.io/aca-chaos-lab:v2 .
docker push <acr-name>.azurecr.io/aca-chaos-lab:v2

# 新しいリビジョンの作成
az containerapp update \
  --name <app-name> \
  --resource-group $RESOURCE_GROUP \
  --image <acr-name>.azurecr.io/aca-chaos-lab:v2 \
  --revision-suffix v2
```

## セキュリティチェックリスト

- [ ] Container Appはマネージドアイデンティティを使用
- [ ] RedisはEntra IDのみで設定（パスワードなし）
- [ ] ネットワークトラフィックはVNetを通過
- [ ] コンテナレジストリはRBACが設定済み
- [ ] Application Insightsのデータは暗号化
- [ ] NSGルールは制限的
- [ ] 環境変数にシークレットなし

## コスト管理

コストを最小限に抑えるために：

1. **Redis Enterprise**: Balanced_B0 SKU（最低ティア）を使用
2. **Container Apps**: 使用しない時はゼロにスケール
3. **Application Insights**: 高ボリューム時はサンプリングを設定
4. **Log Analytics**: 適切な保持期間を設定

## クリーンアップ

すべてのリソースを削除するには：

```bash
# Azure Developer CLIを使用
azd down --purge

# または手動で
az group delete --name $RESOURCE_GROUP --yes
```

## Container App Upsert戦略

このプロジェクトは、Azure Verified Module (AVM) の Container App upsert戦略を使用してデプロイされます。

### upsert戦略の特徴

- **インクリメンタル更新**: 既存のContainer Appを完全に置換せずに、変更された部分のみを更新
- **設定保持**: 明示的に変更されない設定値を自動的に保持
- **条件付きイメージ更新**: 新しいコンテナイメージが指定された場合のみ更新、そうでなければ既存イメージを維持
- **ダウンタイム削減**: 全体の置換ではなく部分更新によりダウンタイムを最小化

### 実装詳細

```bicep
// AVMモジュールの使用
module containerApp 'br/public:avm/ptn/azd/container-app-upsert:0.1.2' = {
  name: 'container-app'
  params: {
    // 条件付きイメージ更新ロジック
    imageName: !empty(containerAppImageName) ? containerAppImageName : ''
    exists: false // モジュールが自動的に存在を判定
    // その他のパラメータ...
  }
}
```

### デプロイ動作

1. **初回デプロイ**: 通常のContainer App作成と同じ動作
2. **更新デプロイ**: 
   - 新しいイメージが指定された場合: イメージを更新
   - イメージが空の場合: 既存のイメージを保持
   - 環境変数等の変更: 指定された変更のみ適用
   - 未指定の設定: 既存の値を保持

### 利点

- **運用効率**: 不要な設定変更を避けて運用の安定性を向上
- **Azure推奨**: Microsoftが公式に推奨するベストプラクティス
- **azd統合**: Azure Developer CLIとの完全な互換性
- **保守性**: 標準化されたAVMモジュールによる保守の簡素化
