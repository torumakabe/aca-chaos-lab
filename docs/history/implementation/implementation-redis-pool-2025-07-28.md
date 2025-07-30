### [実装] - [Redis接続プール設定の最適化] - [2025-07-28T20:00:00Z]
**目的**: Redis接続プールの設定を環境変数で調整可能にする
**コンテキスト**: 高負荷時のパフォーマンス向上と接続エラーの削減
**決定**: 設定クラスに接続プールパラメータを追加し、RedisClientで使用
**実行**: 
1. config.pyに4つの新しい設定を追加
   - redis_max_connections (デフォルト: 50)
   - redis_socket_timeout (デフォルト: 5秒)
   - redis_socket_connect_timeout (デフォルト: 5秒)
   - redis_retry_on_timeout (デフォルト: true)
2. RedisClientのコンストラクタにsettingsパラメータを追加
3. Redis接続時に設定値を使用
4. main.pyでRedisClient初期化時にsettingsを渡すよう修正

**出力**: 
## 変更内容

### 環境変数
新しく追加された環境変数：
- `REDIS_MAX_CONNECTIONS`: 接続プールの最大接続数
- `REDIS_SOCKET_TIMEOUT`: ソケットタイムアウト（秒）
- `REDIS_SOCKET_CONNECT_TIMEOUT`: 接続タイムアウト（秒）
- `REDIS_RETRY_ON_TIMEOUT`: タイムアウト時のリトライ有効化

### 実装の詳細
- 設定値はSettingsクラスから取得され、RedisClientに渡される
- getattr()を使用して設定値の存在を安全にチェック
- デフォルト値は従来の動作を維持

### 使用例
```bash
# 高負荷環境での設定例
export REDIS_MAX_CONNECTIONS=100
export REDIS_SOCKET_TIMEOUT=10
export REDIS_SOCKET_CONNECT_TIMEOUT=10
export REDIS_RETRY_ON_TIMEOUT=true
```

**検証**: 設定が環境変数から読み込まれ、Redis接続時に適用される
**次**: 低優先度タスクの実装（エラーメッセージ標準化、カオス機能拡張）