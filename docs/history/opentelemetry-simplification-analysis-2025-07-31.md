### [分析] - [OpenTelemetry実装の現状分析] - [2025-07-31 10:00]

**目的**: OpenTelemetry実装の現状を理解し、Azure公式ドキュメントに基づいたシンプル化のための明確な要件を定義する

**コンテキスト**: ユーザーから「OpenTelemetry実装のシンプル化」という要求を受け、Azure公式ドキュメントを参照して最適な実装方法を特定する

**決定**: Azure Monitor OpenTelemetryの自動計装機能を活用し、手動のspan管理を削減する

**実行**: 
1. 現在の実装の分析
2. Azure公式ドキュメントの推奨方法の確認
3. シンプル化の機会の特定

**出力**: 

## 現在の実装 vs Azure推奨実装

### 現在の実装の問題点

1. **手動のspan管理**
```python
# main.py
if tracer:
    with tracer.start_as_current_span("root_endpoint") as span:
        return await _root_with_span(span, request)
else:
    return await _root_with_span(None, request)
```

2. **不要な無効化設定**
```python
instrumentation_options={
    "azure_sdk": {"enabled": False},
    "django": {"enabled": False},
    "flask": {"enabled": False},
    "psycopg2": {"enabled": False},
}
```

3. **複雑な初期化プロセス**
- 手動でFastAPIInstrumentor.instrument_app()を呼び出し
- 個別にRedisInstrumentor().instrument()を呼び出し
- カスタムtracerの作成

### Azure公式ドキュメントの推奨方法

1. **シンプルな初期化**
```python
from azure.monitor.opentelemetry import configure_azure_monitor

configure_azure_monitor(
    connection_string="your-connection-string"
)
```

2. **自動計装**
- FastAPIは公式サポートされており、自動的に計装される
- 手動のspan作成は不要

3. **Redis計装**
- RedisInstrumentor().instrument()は引き続き必要（configure_azure_monitorに含まれない）

## シンプル化の提案

### 新しいtelemetry.pyの構造
```python
"""Application Insights telemetry setup - Simplified."""

import logging
import os

from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry.instrumentation.redis import RedisInstrumentor

logger = logging.getLogger(__name__)


def setup_telemetry():
    """Configure Azure Application Insights telemetry."""
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

    if not connection_string:
        logger.warning(
            "APPLICATIONINSIGHTS_CONNECTION_STRING not set, telemetry disabled"
        )
        return

    try:
        # Azure Monitor automatically instruments FastAPI
        configure_azure_monitor(
            connection_string=connection_string,
            logger_name="aca-chaos-lab",
        )

        # Redis needs separate instrumentation
        RedisInstrumentor().instrument()

        logger.info("Application Insights telemetry configured successfully")

    except Exception as e:
        logger.error(f"Failed to configure Application Insights: {e}")
```

### main.pyの変更
- グローバルtracerを削除
- _root_with_span, _health_with_spanメソッドを削除
- 直接ビジネスロジックを実装（自動計装に任せる）

## EARS記法による要件定義

1. **REQ-OTEL-001**: システムは常にAzure Monitor OpenTelemetryの自動計装を使用するものとする
2. **REQ-OTEL-002**: [Application Insights接続文字列が設定されていない場合]、システムはテレメトリなしで正常に動作するものとする
3. **REQ-OTEL-003**: システムは常にRedis操作を自動的にトレースするものとする
4. **REQ-OTEL-004**: [HTTPリクエストが発生したとき]、システムは自動的にトレーススパンを生成するものとする（手動介入なし）
5. **REQ-OTEL-005**: システムは常に最小限の設定でOpenTelemetryを初期化するものとする

## 依存関係と制約

### 維持すべき機能
- Application Insightsへのテレメトリ送信
- Redis操作のトレーシング
- エラー時の適切なログ出力
- テレメトリ無効時の正常動作

### 削除可能な要素
- 手動のspan作成と管理
- 不要なinstrumentation_options
- グローバルtracer変数
- カスタムトレーサーの作成
- excluded_urlsの設定（必要に応じて後で追加可能）

## リスク評価

### 低リスク
- 自動計装はAzure公式の推奨方法
- 既存の機能は維持される
- コード量が大幅に削減される

### 考慮事項
- カスタム属性の追加が必要な場合は、別途対応が必要
- /healthエンドポイントの除外設定が必要な場合は、configure_azure_monitorのオプションで対応

**検証**: 
- Azure公式ドキュメントに基づいた実装
- 大幅なコード削減が可能
- 保守性の向上

**次**: フェーズ2（設計）に進み、詳細な技術設計を作成

## 信頼度評価

**信頼度スコア: 98%**

**根拠:**
- Azure公式ドキュメントに基づいた実装
- FastAPIは公式サポートされている
- 自動計装は実績のある安定した機能
- コード削減によりバグの可能性が減少
- 既存のテストで検証可能

**推奨アプローチ:**
高信頼度のため、標準的な実装アプローチで進める。Azure Monitor OpenTelemetryの自動計装機能を最大限活用し、手動のspan管理を完全に削除する。