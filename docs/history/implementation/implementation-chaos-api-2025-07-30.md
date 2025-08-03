### 実装 - Chaos APIエンドポイントの追加 - 2025-07-30
**目的**: Redis接続リセットAPIとステータス拡張を実装する
**コンテキスト**: RedisClientクラスの拡張が完了
**決定**: 既存のカオスAPIパターンに従い、エラーハンドリングを統一
**実行**: chaos.pyとmodels.pyの変更
**出力**: 以下の変更を実装
- models.pyにRedisResetRequest/Responseモデルを追加
- ChaosStatusResponseにredisフィールドを追加
- ChaosStateクラスにredis_last_resetを追加
- POST /chaos/redis-resetエンドポイントを実装
- GET /chaos/statusにRedis接続状態を追加
**検証**: エラーハンドリングとレスポンス形式の一貫性を確認
**次**: テストコードの作成