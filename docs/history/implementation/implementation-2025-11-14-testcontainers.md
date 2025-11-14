# Testcontainersベース統合テスト実装

## 実装日
2025-11-14

## 概要
Testcontainersを使用したローカル環境での統合テストを実装し、3層テスト構造（unit/integration/e2e）を確立しました。

## 実装内容

### 1. RedisClient Access Key認証モードの追加

#### 変更ファイル
- `src/app/redis_client.py`

#### 追加機能
- `use_entra_auth: bool = True` パラメータ（デフォルトはEntra ID認証）
- `password: str | None = None` パラメータ（Access Key使用時）
- `_connect_with_access_key()` メソッド実装
- `delete()` メソッド追加
- `incr()` メソッド追加（`increment()`のエイリアス）

#### 設計判断
- 本番環境: Entra ID認証（`use_entra_auth=True`、デフォルト）
- テスト環境: Access Key認証（`use_entra_auth=False`）
- 認証方式を実行時に切り替え可能

### 2. Testcontainersベース統合テスト

#### 新規ファイル
- `src/tests/integration/conftest.py` - Redis コンテナフィクスチャ
- `src/tests/integration/test_redis_integration.py` - Redis操作テスト (5 tests)
- `src/tests/integration/test_app_integration.py` - RedisClient統合テスト (2 tests)

#### テスト内容
**Redis操作テスト**:
- `test_redis_connection` - ping確認
- `test_redis_set_get` - 値の保存と取得
- `test_redis_delete` - キーの削除
- `test_redis_incr` - カウンタのインクリメント
- `test_create_direct_redis_client` - 直接クライアント作成

**RedisClient統合テスト**:
- `test_redis_client_basic_operations` - 接続、set、get、delete
- `test_redis_client_counter` - インクリメント操作

### 3. テスト階層化

#### ディレクトリ構造
```
tests/
├── unit/          # 単体テスト（モック使用）- 51 tests
├── integration/   # 統合テスト（Testcontainers）- 7 tests
└── e2e/          # E2Eテスト（Azureデプロイ環境）
```

#### pytest マーカー設定
- `unit`: 単体テスト
- `integration`: 統合テスト
- `e2e`: E2Eテスト

### 4. CI/CD統合

#### GitHub Actions変更
- `.github/workflows/ci.yml`
  - `tests` ジョブ名を `Unit Tests` に変更
  - 新規 `Integration Tests` ジョブを追加
  - 並列実行可能な構成

### 5. ドキュメント更新

#### 更新ファイル
- `docs/requirements.md`
  - REQ-TEST-001: 統合テスト環境要件
  - REQ-TEST-002: テスト階層化要件
  - REQ-TEST-003: CI/CD統合要件

- `docs/design.md`
  - テスト戦略設計セクション追加
  - RedisClient認証設計詳細
  - Testcontainersフロー図

- `docs/deployment.md`
  - テストによる検証セクション追加
  - E2Eテスト実行手順
  - テスト環境理解の表

- `README.md`
  - 統合テストセクション全面改訂
  - E2Eテストセクション追加
  - テスト戦略まとめ表

- `src/Makefile`
  - `test-e2e` ターゲット追加
  - `test` ターゲットにマーカー追加

### 6. 実行スクリプト

#### 新規スクリプト
- `src/tests/e2e/run-e2e-tests.sh` - E2Eテスト実行スクリプト
- `src/tests/e2e/conftest.py` - E2Eテスト用フィクスチャ

#### 変更スクリプト
- `src/tests/run-integration-tests.sh`
  - azd環境変数依存を削除
  - Testcontainersのみに依存
  - マーカー指定追加（`-m integration`）

## テスト結果

### 実行結果
```
単体テスト: 51 passed
統合テスト: 7 passed (Redis 5 + App 2)
総合: 58 tests passing
```

### カバレッジ
- 単体テスト: 85%以上
- 統合テスト: Redis操作全般
- E2E テスト: 基本APIエンドポイント

## 技術的な決定

### TestClient問題の解決
当初、FastAPIの`TestClient`を使ってアプリケーション統合テストを試みましたが、以下の問題が発生：

**問題**:
- `TestClient`は独自のイベントループを作成
- アプリスタートアップ時に本番Redis（localhost:10000）への接続を試行
- `monkeypatch`による環境変数変更が間に合わない
- Settings オブジェクトがロード済みで変更不可

**解決策**:
- アプリケーション統合テストをRedisClient直接テストに変更
- TestClientベースのテストはE2Eテストとして分離
- シンプルで安定したテスト設計を実現

### Access Key vs Entra ID認証

| 環境 | 認証方式 | プロトコル | 用途 |
|------|---------|-----------|------|
| 本番 | Entra ID | `rediss://` (TLS) | Azure Managed Redis |
| テスト | Access Key | `redis://` (平文) | Testcontainers |

**設計理由**:
- Testcontainers環境にEntra ID認証は不要
- シンプルなAccess Key（パスワードなし）で接続
- 本番とテストで異なる認証を使い分け

## 影響範囲

### 追加依存関係
- `pyproject.toml`: `testcontainers[redis]>=4.0.0`

### 破壊的変更
なし（既存機能は完全互換）

### 新規機能
- ローカル環境での統合テスト実行
- CI/CDでのTestcontainers統合テスト
- RedisClientの柔軟な認証モード切り替え

## 次のステップ

### 短期
- [ ] E2Eテストの拡充（カオスAPI等）
- [ ] 統合テストのエラーケース追加

### 中期
- [ ] 負荷テスト統合の検討
- [ ] カバレッジ目標90%達成

### 長期
- [ ] 他のコンポーネント（Application Insights等）の統合テスト追加

## 参考リソース

- [Testcontainers Python Documentation](https://testcontainers-python.readthedocs.io/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [Redis Python Client](https://redis-py.readthedocs.io/)

## コミット情報

**ブランチ**: `refactor/test-structure-separation`
**コミットメッセージ**: 
```
feat: Add Testcontainers-based integration tests with Access Key auth

- Add RedisClient support for Access Key authentication (use_entra_auth=False)
- Add delete() and incr() methods to RedisClient
- Create integration tests using Testcontainers for Redis
- Separate test types: unit, integration (Testcontainers), e2e (deployed)
- Update CI to run integration tests in separate job
- Update documentation with Testcontainers info
```

## レビュー観点

ドキュメントレビュー時の確認ポイント：

### 要件定義（requirements.md）
- [ ] REQ-TEST-001〜003の要件が明確か
- [ ] Testcontainersの前提条件が記載されているか

### 設計書（design.md）
- [ ] テスト階層構造が図で説明されているか
- [ ] 認証モードの切り替え設計が理解できるか
- [ ] Testcontainersフローが明確か

### デプロイガイド（deployment.md）
- [ ] テスト実行手順が正確か
- [ ] E2Eテストとの違いが説明されているか
- [ ] テスト環境理解の表が役立つか

### README.md
- [ ] 統合テストセクションが初見でわかりやすいか
- [ ] 前提条件（Docker）が明記されているか
- [ ] テスト戦略まとめ表が有用か

### 実行可能性
- [ ] ドキュメント通りに実行してテストが成功するか
- [ ] エラー時のトラブルシューティング情報は十分か
