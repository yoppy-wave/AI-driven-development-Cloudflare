---
paths:
  - "bin/**"
  - "lib/**"
  - "lambda/**"
  - ".github/workflows/*aws-cdk*.yml"
  - "docs/aws-cdk-architecture.md"
---

# AWS CDKの開発指示

- AWSリソースはTypeScriptのCDK Stackで宣言し、LambdaのPython実装は`lambda.Code.fromAsset()`で参照する。独自ハッシュでLambda更新を判定しない。
- PR一時環境のStack名は共通命名関数でPR元ブランチ名から生成する。管理タグとPR番号で所有を検証し、共有環境のdestroyを自動化しない。
- `cdk deploy`、`cdk destroy`、`cdk bootstrap`、AWSアカウントへの認証は、対象アカウント、リージョン、Stack、変更・削除対象、復旧方法を確認した明示承認なしに実行しない。
- CI/CDではGitHub Actions OIDCを使い、IAMロールは最小権限にする。アカウントID、Role ARN、アクセスキー、接続情報をソースやStack Outputに埋め込まない。
- 変更前後に`npm run typecheck`、`npm test`、`npm run synth`を実行する。実クラウドとの差分確認が承認されている場合だけ`cdk diff`を使う。
