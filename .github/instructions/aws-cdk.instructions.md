---
applyTo: "bin/**,lib/**,lambda/**,.github/workflows/*aws-cdk*.yml,docs/aws-cdk-architecture.md"
---

# AWS CDKの開発指示

- AWSリソースはTypeScriptのCDK Stackで宣言し、LambdaのPython実装は`lambda.Code.fromAsset()`で参照する。独自ハッシュでLambda更新を判定しない。
- PR一時環境のStack名は共通命名関数でPR元ブランチ名から生成する。管理タグとPR番号で所有を検証し、共有環境のdestroyを自動化しない。
- AWS認証はGitHub Actions OIDCの短期認証を使い、Role ARNはGitHub Environmentの`AWS_ROLE_TO_ASSUME` Secretで管理する。
- `cdk deploy`、`cdk destroy`、`cdk bootstrap`は人間の明示承認なしに実行しない。
