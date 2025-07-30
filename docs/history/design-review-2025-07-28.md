### [設計] - [設計レビューと改善計画] - [2025-07-28T19:00:00Z]
**目的**: 既存設計をレビューし、特定された改善項目の実装計画を策定する
**コンテキスト**: 信頼度98%でプロジェクトは完成しているが、軽微な改善機会が存在
**決定**: 適応的実行戦略を採用し、優先度に基づいて改善を実施
**実行**: 改善項目の詳細設計と実装計画の作成
**出力**: 

## 適応的実行戦略

### 信頼度スコア: 98%（高信頼度）
- プロジェクトは完全に機能している
- 改善は任意だが、実施により品質がさらに向上
- 標準的な段階的改善アプローチを採用

## 改善項目の技術設計

### 1. スクリプトの一貫性向上（優先度: 高）

#### 現状の問題
- `list-network-failures.sh`と`restore-deployment.sh`がazd環境変数を参照していない
- 他のスクリプト（inject-*.sh）は既にazd対応済み

#### 設計方針
```bash
# azd-env-helper.shをソース
source "$(dirname "$0")/azd-env-helper.sh"

# パラメータのデフォルト値を設定
RESOURCE_GROUP="${1:-$AZURE_RESOURCE_GROUP}"
NSG_NAME="${2:-$AZURE_NSG_NAME}"
CONTAINER_APP_NAME="${3:-$AZURE_CONTAINER_APP_NAME}"

# パラメータチェック
if [ -z "$RESOURCE_GROUP" ] || [ -z "$NSG_NAME" ]; then
    echo "Error: Required parameters missing"
    exit 1
fi
```

#### 期待される結果
- すべてのスクリプトがazd環境変数を参照
- パラメータなしでの実行が可能
- 一貫性のあるユーザー体験

### 2. 型ヒントの追加（優先度: 中）

#### 対象ファイル
`src/app/chaos.py`の以下の関数：
- `cpu_intensive_task()`
- `memory_intensive_task()`
- `start_load_internal()`
- `start_hang_internal()`

#### 設計方針
```python
from typing import Optional, Dict, Any
import asyncio
from datetime import datetime

async def cpu_intensive_task() -> None:
    """CPU集約的なタスクを実行する."""
    ...

async def memory_intensive_task(size_mb: int) -> list[bytes]:
    """メモリ集約的なタスクを実行する."""
    ...

async def start_load_internal(level: str, duration: int) -> None:
    """負荷生成を内部的に開始する."""
    ...
```

#### 期待される結果
- mypyエラーの解消
- IDEサポートの向上
- コードの自己文書化

### 3. Redis接続プール最適化（優先度: 中）

#### 現状
- redis-pyのデフォルト設定を使用
- 接続プールサイズが固定

#### 設計方針
```python
# config.py
class Settings(BaseSettings):
    # Redis接続プール設定
    redis_max_connections: int = 50
    redis_connection_timeout: int = 5
    redis_socket_timeout: int = 5
    redis_retry_on_timeout: bool = True

# redis_client.py
self.client = redis.Redis(
    host=self.host,
    port=self.port,
    ssl=True,
    username=username,
    decode_responses=True,
    max_connections=settings.redis_max_connections,
    socket_timeout=settings.redis_socket_timeout,
    socket_connect_timeout=settings.redis_connection_timeout,
    retry_on_timeout=settings.redis_retry_on_timeout,
)
```

#### 期待される結果
- 環境変数による接続プール設定の調整が可能
- 高負荷時のパフォーマンス向上
- 接続エラーの削減

### 4. エラーメッセージ標準化（優先度: 低）

#### 設計方針
```python
# models.py
class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: str
    request_id: Optional[str] = None

# エラーハンドラー
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal Server Error",
            detail=str(exc) if settings.debug else None,
            timestamp=datetime.utcnow().isoformat(),
            request_id=request.headers.get("X-Request-ID")
        ).model_dump()
    )
```

#### 期待される結果
- 一貫性のあるエラーレスポンス
- デバッグの容易化
- APIクライアントでのエラー処理の簡素化

### 5. カオス機能拡張（優先度: 低）

#### メモリリークシミュレーション
```python
class MemoryLeakManager:
    def __init__(self):
        self.leaked_objects: list[bytes] = []
        self.leak_active = False
    
    async def start_leak(self, rate_mb_per_minute: int):
        self.leak_active = True
        while self.leak_active:
            # 1MBずつメモリをリーク
            self.leaked_objects.append(b'x' * 1024 * 1024)
            await asyncio.sleep(60 / rate_mb_per_minute)
```

#### ディスクI/O負荷
```python
async def disk_io_load(duration_seconds: int, write_size_mb: int):
    end_time = time.time() + duration_seconds
    temp_file = Path("/tmp/chaos_disk_test")
    
    while time.time() < end_time:
        # ランダムデータを書き込み
        data = os.urandom(write_size_mb * 1024 * 1024)
        async with aiofiles.open(temp_file, 'wb') as f:
            await f.write(data)
        
        # 読み込み
        async with aiofiles.open(temp_file, 'rb') as f:
            await f.read()
        
        await asyncio.sleep(0.1)
    
    # クリーンアップ
    temp_file.unlink(missing_ok=True)
```

## 実装計画

### フェーズ1: 高優先度改善（推定: 30分）
1. list-network-failures.shのazd対応
2. restore-deployment.shのazd対応
3. テストと動作確認

### フェーズ2: 中優先度改善（推定: 3時間）
1. chaos.pyへの型ヒント追加
2. Redis接続プール設定の実装
3. 単体テストの更新

### フェーズ3: 低優先度改善（推定: 5時間）
1. エラーメッセージ標準化
2. メモリリーク機能の実装
3. ディスクI/O負荷機能の実装
4. 統合テストの追加

## エラー処理と単体テスト戦略

### スクリプトのエラー処理
- set -euo pipefailの使用
- エラーメッセージの明確化
- 終了コードの適切な設定

### 型ヒントのテスト
- mypyによる静的型チェック
- 既存のテストがパスすることを確認

### 新機能のテスト
- 各機能に対する単体テスト作成
- モックを使用したエッジケーステスト
- 負荷テストシナリオへの統合

**検証**: 改善計画が明確で、リスクが低く、段階的に実施可能
**次**: フェーズ3: 実装 - 優先度順に改善を実施