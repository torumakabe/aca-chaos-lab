### 設計 - Redis接続リセット機能の技術設計 - 2025-07-30
**目的**: Redis接続リセットAPIの詳細設計を文書化する
**コンテキスト**: 分析フェーズが完了し、要件が明確化された
**決定**: 既存のカオスAPIパターンに従い、即座の接続切断方式を採用
**実行**: design.mdの更新と実装計画の策定

## API設計詳細

### POST /chaos/redis-reset エンドポイント
```python
@app.post("/chaos/redis-reset")
async def reset_redis_connections(request: RedisResetRequest = None):
    """Redis接続をリセット"""
    try:
        # リクエストパラメータの処理
        force = True
        if request and hasattr(request, 'force'):
            force = request.force
        
        # 接続リセット実行
        connections_closed = await redis_client.reset_connections()
        
        # 状態更新
        chaos_state.redis_last_reset = datetime.utcnow()
        
        # トレーシング
        span = trace.get_current_span()
        if span:
            span.set_attribute("chaos.redis_reset.connections_closed", connections_closed)
            span.set_attribute("chaos.redis_reset.force", force)
        
        # レスポンス
        return {
            "status": "redis_connections_reset",
            "connections_closed": connections_closed,
            "timestamp": chaos_state.redis_last_reset.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Redis reset failed: {e}")
        raise HTTPException(status_code=500, detail="Redis reset failed")
```

### GET /chaos/status エンドポイントの拡張
```python
@app.get("/chaos/status")
async def get_chaos_status():
    """カオス状態を取得（Redis接続状態を含む）"""
    # 既存の負荷とハング状態
    status = {
        "load": {...},
        "hang": {...}
    }
    
    # Redis接続状態を追加
    redis_status = await redis_client.get_connection_status()
    redis_status["last_reset"] = (
        chaos_state.redis_last_reset.isoformat() 
        if chaos_state.redis_last_reset 
        else None
    )
    status["redis"] = redis_status
    
    return status
```

## RedisClient クラスの拡張

### 接続管理の改善
```python
class RedisClient:
    def __init__(self, host: str, port: int = 10000):
        self.host = host
        self.port = port
        self.ssl = True
        self.credential = DefaultAzureCredential()
        self.client: Optional[redis.Redis] = None
        self._connection_count = 0
        self._lock = asyncio.Lock()  # スレッドセーフティ
        
    async def ensure_connected(self):
        """接続を確実に確立"""
        async with self._lock:
            if not self.client:
                await self.connect()
    
    async def reset_connections(self) -> int:
        """既存の接続をすべて切断"""
        async with self._lock:
            closed_count = 0
            if self.client:
                try:
                    # 接続プールの情報を取得
                    pool_info = self.client.connection_pool
                    closed_count = len(pool_info._available_connections) + len(pool_info._in_use_connections)
                    
                    # すべての接続をクローズ
                    await self.client.close()
                    await self.client.connection_pool.disconnect()
                    
                    # 状態をクリア
                    self.client = None
                    self._connection_count = 0
                    
                    logger.info(f"Redis connections reset: {closed_count} connections closed")
                except Exception as e:
                    logger.error(f"Error during Redis reset: {e}")
                    raise
            
            return closed_count
```

## エラーハンドリングの考慮

### リセット中の操作処理
```python
async def get(self, key: str):
    """キーの値を取得（自動再接続付き）"""
    try:
        await self.ensure_connected()
        return await self.client.get(key)
    except redis.ConnectionError:
        # 接続エラー時は自動的に再接続を試行
        logger.warning("Redis connection lost, attempting reconnect...")
        self.client = None  # 既存の接続をクリア
        await self.ensure_connected()
        return await self.client.get(key)
```

## テスト計画

### 単体テスト
```python
async def test_redis_reset_endpoint():
    """Redis接続リセットAPIのテスト"""
    # モックRedisクライアント
    mock_redis = AsyncMock()
    mock_redis.reset_connections.return_value = 3
    
    # APIコール
    response = await client.post("/chaos/redis-reset")
    
    # 検証
    assert response.status_code == 200
    assert response.json()["connections_closed"] == 3
    assert "timestamp" in response.json()

async def test_redis_auto_reconnect():
    """リセット後の自動再接続テスト"""
    # 接続リセット
    await redis_client.reset_connections()
    
    # 次の操作で自動再接続
    result = await redis_client.get("test_key")
    
    # 接続が再確立されていることを確認
    assert redis_client.client is not None
```

### 統合テスト
```python
async def test_redis_reset_with_concurrent_operations():
    """同時操作中のリセットテスト"""
    # 複数の並行操作を開始
    tasks = [
        redis_client.get(f"key_{i}") for i in range(10)
    ]
    
    # リセットを実行
    reset_task = redis_client.reset_connections()
    
    # すべてのタスクを実行
    results = await asyncio.gather(*tasks, reset_task, return_exceptions=True)
    
    # エラーと成功が混在することを確認
    errors = [r for r in results if isinstance(r, Exception)]
    assert len(errors) > 0  # 一部の操作は失敗する
```

## 実装の優先順位

1. **RedisClientクラスの拡張** - reset_connections()メソッドの実装
2. **カオスAPIエンドポイント** - /chaos/redis-resetの追加
3. **ステータスAPI拡張** - Redis接続状態の追加
4. **エラーハンドリング** - 自動再接続ロジック
5. **テスト実装** - 単体テストと統合テスト
6. **ドキュメント更新** - API仕様書とREADME

**出力**: Redis接続リセット機能の技術設計完了
**検証**: 既存のアーキテクチャと整合性があり、実装可能な設計
**次**: フェーズ3（実装）に進む