### [実装] - [alert-rules.bicepモジュール作成] - [2025-07-30T10:40:00]

**目的**: Container Apps応答監視用のアラートルールBicepモジュールを作成する

**コンテキスト**: 
- 5xxエラーと応答時間の2つのメトリクスアラートを実装
- アクショングループは定義しない
- 既存のContainer Appリソースを参照

**決定**: 
- Microsoft.Insights/metricAlerts@2018-03-01を使用
- location: 'global'（メトリクスアラートの要件）
- 評価頻度1分、ウィンドウサイズ5分

**実行**: 
1. alert-rules.bicepファイルを作成
2. パラメータ定義:
   - location: リソースのリージョン
   - tags: リソースタグ
   - containerAppName: 監視対象のContainer App名
3. 5xxエラーアラート実装:
   - メトリクス: Requests
   - ディメンション: StatusCodeCategory = '5xx'
   - 閾値: 5回/5分
4. 応答時間アラート実装:
   - メトリクス: ResponseTime
   - 閾値: 平均5000ms
5. 出力定義: 各アラートのリソースID

**出力**: infra/modules/alert-rules.bicep作成完了

**検証**: 
- Bicep構文の妥当性を確認
- Container Appsメトリクス仕様との整合性を確認
- タグとリソース命名規則の一貫性を確認

**次**: main.bicepへのモジュール統合