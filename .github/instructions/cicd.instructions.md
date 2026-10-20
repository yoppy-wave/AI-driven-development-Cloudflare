---
applyTo: ".github/cicd/**,.github/workflows/cicd*.yml,.github/workflows/reusable-*.yml,.github/scripts/cicd_config.py,.github/scripts/cicd_config_test.py,.github/scripts/preview_cleanup.py,.github/scripts/preview_cleanup_test.py,tests/cicd_workflows_test.py"
---

# CI/CD共通基盤の開発指示

- PR起点のクラウド認証情報は再利用ワークフローの`workflow_call.secrets`で明示し、callerから必要な名前だけを`jobs.<job_id>.secrets`で受け渡す。実行jobには対象GitHub Environmentを必ず割り当て、同名のEnvironment Secretを優先して使用する。`preview`、`staging`、`production`にはrequired reviewersを設定する。
- `pull_request`からクラウド操作する際はFork判定だけでなく、作成者の`author_association`をOWNER、MEMBER、COLLABORATORに限定し、`pull_request_target`へ変更しない。
- PR一時環境のcleanupはPR元ブランチ名からStack名を再計算し、設定済みAWSリージョンのCloudFormationを参照する。コメントへの環境情報記録は行わない。
- 再利用ワークフローはGitHub Actionsの仕様に従い、`.github/workflows/`直下に置き、`on.workflow_call`で入力・Secrets・出力を明示する。サブディレクトリへ置かない。
- `.github/cicd/application.json`をCI/CDの有効化契約として扱う。AWS CDK、Preview Environment、各環境へのデプロイは明示的に`true`になるまで無効のままにし、無効時にAWS認証、`cdk deploy`、`cdk destroy`を実行しない。
- PRではテスト・build・設定検証を必ず先行し、クラウド認証が必要なPreview EnvironmentはFork PRで作成しない。`pull_request_target`でPRコードをcheckoutしてSecretsを渡す実装は追加しない。
- PR一時環境の作成・更新・削除は共通命名関数で同じブランチ由来Stack名を使う。管理タグとPR番号が一致しないStackや共有環境は更新・自動削除しない。
- デプロイは信頼済みブランチまたは`workflow_dispatch`からだけ実行する。productionではGitHub Environmentを使い、承認者・Secrets・権限をリポジトリ設定で分離する。
- AWS認証はGitHub Actions OIDCの短期認証を使い、Role ARNは対象GitHub Environmentの`AWS_ROLE_TO_ASSUME` Secretで管理する。AWSアダプター以外へAWS固有のSecretsやURL形式を混在させない。未確定なら有効化せず、必要な設定と人間の確認事項を報告する。
