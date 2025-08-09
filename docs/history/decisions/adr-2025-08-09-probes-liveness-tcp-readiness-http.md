# ADR: Liveness を TCP、Readiness を HTTP に分離する

- 日付: 2025-08-09
- ステータス: 承認/適用済み

## 背景 / コンテキスト

これまで Liveness/Readiness の両方で HTTP `GET /health` を使用していました。
`/health` は Redis などの外部依存を確認し、障害時には 503 を返します。
高負荷や下流障害時に Liveness まで失敗して再起動を誘発するリスクがあり、誤再起動の懸念が指摘されました。

## 決定

- Liveness Probe は TCP ソケットチェックに変更し、アプリがポートを受け付けているか（プロセス/イベントループが生存か）を確認する。
- Readiness Probe は引き続き HTTP `GET /health` を使用し、外部依存（Redis 等）の健全性でトラフィック受け入れ可否を判断する。

## 目的 / 意図

- 外部依存障害や一過性の 5xx により Liveness が落ちて不必要な再起動が発生することを防ぐ。
- 生存監視（Liveness）と受け入れ可否（Readiness）を明確に分離し、役割に応じた検知特性にする。

## 採用したパラメータ

- Liveness (TCP)
  - `port: 8000`
  - `initialDelaySeconds: 60`
  - `periodSeconds: 10`
  - `timeoutSeconds: 10`
  - `failureThreshold: 5`
  - `successThreshold: 1`
- Readiness (HTTP)
  - `path: /health`, `port: 8000`, `scheme: HTTP`
  - `initialDelaySeconds: 10`
  - `periodSeconds: 5`
  - `timeoutSeconds: 3`
  - `failureThreshold: 2`
  - `successThreshold: 2`

## 代替案の検討

- Liveness を HTTP `/health` のまま維持
  - 短所: 外部依存やアプリ層の一時的な遅延で誤再起動しやすい。
  - 結論: 不採用。
- Liveness 用の超軽量 HTTP エンドポイント（例: `/healthz`）を追加
  - 長所: アプリ層での最小ハンドラ確認ができる。
  - 短所: 実装追加が必要。今回は要件外のため見送り。
  - 結論: 今回は不採用（将来の選択肢としては有効）。

## 影響 / トレードオフ

- メリット:
  - 外部依存による誤再起動の抑制。
  - 高負荷時の自己影響（HTTP処理）を低減。
  - ハング/ポート未受け付け時は正しく再起動誘発。
- デメリット:
  - TCP のみでは業務的な不健康（部分劣化）を検出できない → Readiness で担保。
  - 極端な接続飽和（SYN backlog 枯渇など）では Liveness も失敗し得る → `timeout`/`failureThreshold` を緩和して誤検知を軽減。

## 実装

- スクリプト修正: `scripts/add-health-probes.sh`
  - Liveness を `tcpSocket` に変更。
  - Readiness のしきい値を調整（上記パラメータ）。
  - 既存設定があっても望ましい設定を再適用する挙動に統一。
- ドキュメント修正:
  - `README.md`、`docs/history/...` の該当箇所を更新。

## 今後の展望（オプション）

- 必要に応じて Liveness 用の超軽量 `/healthz` を追加し、さらに堅牢性を高める。
- プローブ設定の環境変数化（環境ごとのチューニングを容易に）。

