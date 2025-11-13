# 分析: Container App デプロイタイムアウト (2025-11-13)

## 背景

Azure Developer CLI (`azd up`) による Container App のデプロイが 20分以上かかり `Operation expired` でタイムアウトする問題が発生。

## コンテキスト

- **変更の目的**: PR #5694 の azd エンハンスメントにより、イメージが ACR にない状態でも Container App を Bicep で宣言的にデプロイ可能にする
- **azd バージョン**: 1.21.1
- **使用している AVM モジュール**: `br/public:avm/res/app/container-app:0.8.0`
- **環境**: VNet 統合、プライベートエンドポイント使用

## 実行した調査

### 1. デプロイ状態の確認

```bash
az containerapp list -g rg-aca-chaos-lab-dev
```

**結果**:
- `ProvisioningState`: Failed
- `RunningStatus`: Running
- `latestRevisionName`: null
- `latestReadyRevisionName`: null

→ **Container App リソースは作成されたが、リビジョンが全く作成されていない**

### 2. Activity Log の確認

```json
{
  "Level": "Error",
  "Message": "Failed to provision revision for container app 'ca-app-wjrjbjnb4etie'. Error details: Operation expired.",
  "Operation": "Create or Update Container App",
  "Status": "Failed",
  "Time": "2025-11-13T00:24:13.35611Z"
}
```

### 3. Container Registry の確認

```bash
az acr repository list -n crwjrjbjnb4etie
```

**結果**: 空（リポジトリなし）

→ **ACR にイメージがプッシュされていない**

### 4. 使用イメージの確認

```bash
az containerapp show -n ca-app-wjrjbjnb4etie --query "properties.template.containers[].image"
```

**結果**: `mcr.microsoft.com/k8se/quickstart:latest`

→ Bicep のデフォルト値が使用されている

### 5. インフラ状態の確認

✅ **正常なコンポーネント**:
- Container Apps Environment (外部モード、VNet 統合)
- Redis Enterprise (Running、プライベートエンドポイント経由)
- Private DNS Zones (正しく構成)
- Container Registry (作成済み、プライベートエンドポイント経由)

## 根本原因

### 確認された問題

1. **`containerAppImageName` パラメータが未設定**
   - `.env` ファイルに設定なし
   - Bicep のデフォルト値 `mcr.microsoft.com/k8se/quickstart:latest` が使用される

2. **リビジョン作成に20分以上かかりタイムアウト**
   - イメージ pull の問題の可能性
   - AVM 0.8.0 モジュールの既知の問題の可能性

3. **azd の期待動作との不一致**
   - azd #5694 は「Bicep でリビジョンを管理、upsert 不要」を実現
   - しかし、`containerAppImageName` を azd が自動設定していない
   - `azd package` でビルドされたイメージ名が Bicep に渡されていない

## 問題の仮説

### 仮説 A: azd の統合が不完全
- `azd package` はイメージをビルドするが、そのイメージ名を `containerAppImageName` パラメータとして Bicep に渡していない
- 結果として、デフォルトのパブリックイメージが使用され、何らかの理由で pull に失敗

### 仮説 B: AVM 0.8.0 の問題
- AVM Container App モジュール 0.8.0 に、初回デプロイ時のタイムアウト問題がある
- リビジョン作成のタイムアウト設定が不適切

### 仮説 C: プローブ設定の影響
- Liveness プローブ `initialDelaySeconds: 60` が長すぎる
- ただし、リビジョン自体が作成されていないため、プローブ以前の問題

## 次のステップ（設計フェーズ）

以下の調査と設計を提案:

1. **azd の出力パラメータ確認**
   - `azd package` が生成するイメージ名の確認
   - `containerAppImageName` への受け渡し方法の設計

2. **AVM モジュールバージョンの検証**
   - 最新バージョン（0.11.0 以降）への更新検討
   - バージョン間の breaking changes 確認

3. **デプロイ戦略の再設計**
   - Option A: `containerAppImageName` を `.env` に明示的に設定
   - Option B: azd hooks でイメージ名を動的に設定
   - Option C: 一時的にデフォルトイメージでデプロイし、その後更新

4. **タイムアウト回避策**
   - Container App の `activeRevisionsMode` 設定確認
   - リビジョン作成のタイムアウト設定調整（可能であれば）

## 参考資料

- [azure-dev PR #5694: support bicep containerapp revisions](https://github.com/Azure/azure-dev/pull/5694)
- [AVM Container App モジュール](https://github.com/Azure/bicep-registry-modules/tree/main/avm/res/app/container-app)
- [既存の ADR: Liveness/Readiness プローブ設定](../decisions/adr-2025-08-09-probes-liveness-tcp-readiness-http.md)
