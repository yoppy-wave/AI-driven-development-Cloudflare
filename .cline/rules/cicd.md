---
paths:
  - ".github/cicd/**"
  - ".github/workflows/cicd*.yml"
  - ".github/workflows/reusable-*.yml"
  - ".github/scripts/cicd_config.py"
  - ".github/scripts/cicd_config_test.py"
  - "tests/cicd_workflows_test.py"
---

# CI/CD共通基盤の開発指示

- PR起点でクラウド認証情報を使用する操作は、再利用ワークフローの`workflow_call.secrets`で必要な名前を明示し、callerから必要な名前だけを`jobs.<job_id>.secrets`で受け渡す。再利用ワークフロー内でEnvironmentを割り当てたjobは、同名のEnvironment Secretを優先して使用する。
- preview、staging、productionのGitHub Environmentにはrequired reviewersを設定する。PR起点のpreviewはFork以外かつOWNER、MEMBER、COLLABORATORだけを対象にする。
- 再利用ワークフローはGitHub Actionsの仕様に従い、`.github/workflows/`直下に置き、`on.workflow_call`で入力・Secrets・出力を明示する。サブディレクトリへ置かない。
- `.github/cicd/application.json`をCI/CDの有効化契約として扱う。Cloudflare、Preview Environment、各環境へのデプロイは明示的に`true`になるまで無効のままにし、無効時にCloudflare認証やデプロイコマンドを実行しない。
- PRではテスト・build・設定検証を必ず先行し、クラウド認証が必要なPreview EnvironmentはFork PRで作成しない。`pull_request_target`でPRコードをcheckoutしてSecretsを渡す実装は追加しない。
- デプロイは信頼済みブランチまたは`workflow_dispatch`からだけ実行する。productionではGitHub Environmentを使い、承認者・Secrets・権限をリポジトリ設定で分離する。
- Cloudflare認証はGitHub Environmentの`CLOUDFLARE_API_TOKEN`と`CLOUDFLARE_ACCOUNT_ID` Secretで管理する。アプリが採用するCloudflareサービスに必要な最小権限のAPI Tokenを作成し、未確定なら有効化しない。
