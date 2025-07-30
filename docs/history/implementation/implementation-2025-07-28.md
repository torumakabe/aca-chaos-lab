### [実装] - [スクリプトのazd環境変数統合] - [2025-07-28T19:30:00Z]
**目的**: list-network-failures.shとrestore-deployment.shをazd環境変数に対応させる
**コンテキスト**: 他のスクリプトと同様の利便性を提供し、一貫性を向上
**決定**: shellcheck警告に対応しながら実装
**実行**: 
1. 両スクリプトにazd-env-helper.shのソースを追加
2. パラメータのデフォルト値設定とフォールバック実装
3. shellcheck警告の解決（SC1091対応）
4. azd-env-helper.shの変数名を統一（AZURE_プレフィックス）

**出力**: 
## 変更内容

### list-network-failures.sh
- azd-env-helper.shをソース（shellcheck警告抑制付き）
- パラメータをオプション化し、azd環境変数にフォールバック
- エラーメッセージを改善し、環境変数の使用方法を追加

### restore-deployment.sh
- 同様にazd-env-helper.shをソース
- パラメータのオプション化とフォールバック実装
- ユーザーガイダンスの改善

### azd-env-helper.sh
- 変数名をAZURE_プレフィックスで統一
- 既存のinject-*.shスクリプトとの互換性を維持

## shellcheck対応
- `# shellcheck source=/dev/null`でソースファイルの警告を抑制
- 変数展開時の`${VAR:-}`パターンで未定義変数の警告を防止

**検証**: すべてのスクリプトがazd環境変数を参照可能になった
**次**: chaos.pyへの型ヒント追加（中優先度タスク）