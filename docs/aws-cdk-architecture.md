# AWS CDKアーキテクチャ

AWSリソースはTypeScriptの`ApplicationStack`で定義し、Python Lambdaは`lambda.Code.fromAsset("lambda")`で配布します。Stack名は固定の`app`名前空間を使用し、共有環境は`app-development`、`app-staging`、`app-production`です。PR一時環境は`app-<正規化したPR元ブランチ名>`です。

ブランチ名はASCII英数字以外の文字をそれぞれ`-`に置換し、小文字化、前後の`-`除去、先頭30文字への切り詰め、切り詰め後の末尾`-`除去の順で正規化します。`feature/Add_Login`は`app-feature-add-login`、`fix/API_Error`は`app-fix-api-error`になります。空の結果と共有環境名との衝突は拒否します。命名の実装は依存パッケージ不要の`lib/preview-stack-name.cjs`に集約し、CDKとPython管理helperの両方から使用します。

CDKのpreviewでは`--context environment=pr-<PR番号> --context previewBranch=<ブランチ名>`を渡します。`pr-<PR番号>`は環境タグの識別用で、Stack名には使いません。Construct IDとCloudFormationの物理Stack名は同じ関数から決定し、Workflowが指定するStack名も一致させます。同一ブランチは同一Stackを更新します。正規化で同名になった別PRのStackは、作成・更新・削除前のタグ検証で拒否します。

`production`のDynamoDB tableは`RETAIN`、それ以外は`DESTROY`です。Lambda assetにはPythonキャッシュ、pytest cache、単体テストを含めません。

CI/CDの有効化契約は`.github/cicd/application.json`です。すべてのAWS操作は初期状態で無効です。有効化前にpreview / staging / productionのGitHub Environmentへrequired reviewersを設定し、対象環境ごとに最小権限の`AWS_ROLE_TO_ASSUME`をEnvironment Secretとして設定します。

previewはfork外かつOWNER、MEMBER、COLLABORATORのPRだけが対象です。`diff`成功後に`deploy`を直列実行し、同一PRの更新とclose cleanupは同一concurrency groupで最大100件までFIFOキューイングします。実AWS操作直前にはPRのopen状態とhead SHAを再確認します。

cleanupは`pull_request_target`のclosedイベント（Mergeを含む）で起動し、PRコードをcheckoutまたは実行しません。最初に保護された既定ブランチをcheckoutし、そのcommit SHAに固定した管理コードを削除jobでも使用します。既定ブランチの設定を検証し、CDKまたはPreview Environmentが無効ならAWS認証やEnvironment承認jobへ進みません。GitHubへの権限はcontents/PRの読み取りと、AWS jobのOIDCだけです。

削除時はPR元ブランチ名からStack名を再計算し、設定済みリージョンのCloudFormationを検索します。OIDC認証先のアカウントがEnvironment SecretのRole ARNのアカウントと一致すること、Stack名・Stack ARNのアカウントとリージョン、`app:managed-by=ai-driven-development`と`app:preview-pr=<PR番号>`タグを検証します。共有Stackと管理対象と確認できないStackは拒否します。対象不在は正常終了し、AWS接続・権限エラーは失敗として扱います。

PRのclosed状態をjob開始時、AWS認証前、helper開始時、削除直前に再確認し、再オープンされていれば削除を行いません。検証済みの不変なStack IDを指定してCloudFormationの`delete-stack`を実行し、削除完了を待ちます。`DELETE_IN_PROGRESS`でも先にタグを検証し、重複削除せず既存の削除完了だけを待ちます。存在・状態の取得元はCloudFormationのみで、GitHubコメントや外部DBへの環境情報・状態記録はありません。過去のPR番号ベースのStack移行や命名・リージョン変更への互換処理は対象外です。
