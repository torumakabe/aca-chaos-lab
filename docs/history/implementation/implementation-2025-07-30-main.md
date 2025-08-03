### [実装] - [main.bicepへのアラートモジュール統合] - [2025-07-30T10:45:00]

**目的**: alert-rulesモジュールをmain.bicepに統合し、アラート機能を有効化する

**コンテキスト**: 
- alert-rules.bicepモジュールの作成完了
- Container Appモジュールの出力を使用

**決定**: 
- モジュール名: 'alert-rules'
- dependsOn: containerAppモジュール
- 出力にアラートIDを追加

**実行**: 
1. main.bicepにalertRulesモジュール定義を追加:
   - containerAppモジュールの後に配置
   - containerApp.outputs.containerAppNameを渡す
   - dependsOnでcontainerAppへの依存を明示
2. 出力セクションに追加:
   - AZURE_ALERT_5XX_ID: 5xxエラーアラートのリソースID
   - AZURE_ALERT_RESPONSE_TIME_ID: 応答時間アラートのリソースID

**出力**: 
- main.bicep更新完了
- アラートモジュールが正しく統合された

**検証**: 
- モジュール間の依存関係が正しく設定されている
- パラメータの受け渡しが正しい
- 出力が適切に定義されている

**次**: フェーズ4の検証に進む