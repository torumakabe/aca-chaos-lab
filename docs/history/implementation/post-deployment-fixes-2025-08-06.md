# デプロイ後の改善実施記録 - 2025-08-06

## 概要
カオスメトリクス簡素化（duration_histogram削除）の実装完了後、Azure環境でのテストにより2つの問題が発見され、改善を実施した。

## 発見された問題と解決

### 問題1: カスタムメトリクスがApplication Insightsに記録されない
**時刻**: 2025-08-06 17:00頃

#### 症状
- `chaos_operation_active`メトリクスがApplication Insightsに表示されない
- `redis_connection_status`は正常に記録される

#### 原因分析
1. 両メトリクスの実装パターンは同一（毎回`create_gauge`を呼ぶ）
2. 主な違い：
   - `redis_connection_status`: ディメンションなし
   - `chaos_operation_active`: ディメンションあり `{"operation": operation}`
3. Application Insightsの設定確認：
   - `CustomMetricsOptedInType: "NoDimensions"`
   - ディメンション付きカスタムメトリクスを受け入れない設定

#### 解決策
**Bicepテンプレートの修正** (infra/modules/monitoring.bicep)
```bicep
properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
    #disable-next-line BCP037
    CustomMetricsOptedInType: 'WithDimensions'  # 追加
}
```

#### 結果
- ✅ ディメンション付きメトリクスが正常に記録されるように改善
- ✅ `chaos_operation_active`がApplication Insightsで確認可能

### 問題2: loadメトリクスの重複による混乱
**時刻**: 2025-08-06 17:30頃

#### 症状
- `chaos_load_active`メトリクスの値が2になる
- Application Insightsでの表示が直感的でない

#### 原因分析
`load_generator`関数で3つのメトリクスが記録されていた：
1. `cpu_load` - CPU負荷の個別追跡
2. `memory_load` - メモリ負荷の個別追跡
3. `load` - 全体の負荷操作（冗長）

並列実行により、3つのメトリクスが同時にactiveとなり、合計値が2になっていた。

#### 解決策
**chaos.pyの修正**
```python
# load_generator関数から以下を削除：
- record_chaos_metrics("load", True)
- record_chaos_metrics("load", False)

# cpu_loadとmemory_loadの個別メトリクスのみ残す
```

#### 結果
- ✅ 各メトリクスが独立して0または1の値を持つ
- ✅ 直感的で理解しやすい表示
- ✅ CPU負荷とメモリ負荷を個別に監視可能

## 実装の詳細

### 変更ファイル
1. `infra/modules/monitoring.bicep`
   - CustomMetricsOptedInType設定を追加
   
2. `src/app/chaos.py`
   - load_generator関数から冗長なメトリクス記録を削除
   - 行数: 削除2行

### テスト結果
- ユニットテスト: 54/54合格
- 品質チェック: ruff、mypy全て合格
- Azure環境での動作確認: 正常

## 教訓と改善点

### 教訓
1. **環境固有の設定を考慮**
   - ローカルテストだけでなく、実環境の設定確認が重要
   - Application Insightsの設定がメトリクス記録に影響

2. **メトリクスの設計**
   - シンプルで直感的な設計が重要
   - 冗長なメトリクスは混乱の元

3. **ディメンション付きメトリクスの注意点**
   - Application Insightsのデフォルト設定では無効
   - 明示的な有効化が必要

### 今後の改善提案
1. デプロイ前チェックリストにApplication Insights設定確認を追加
2. メトリクス設計のベストプラクティスをドキュメント化
3. 環境設定のバリデーションスクリプト作成

## 最終的なメトリクス構成

### 削除されたメトリクス
- `chaos_operation_duration_seconds` (histogram) - フェーズ3で削除
- `chaos_load_active` - 本修正で削除

### 現在のメトリクス
| メトリクス名 | タイプ | ディメンション | 値の範囲 |
|------------|--------|--------------|----------|
| chaos_operation_active | Gauge | operation={cpu_load, memory_load, hang, redis_reset} | 0 or 1 |
| redis_connection_status | Gauge | なし | 0 or 1 |
| redis_connection_latency_ms | Histogram | なし | 0-N ms |

## 検証完了
- Application Insightsでメトリクスの記録を確認
- 各操作のactive/inactiveが正しく追跡される
- ディメンションによる操作種別の識別が可能