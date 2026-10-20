# AI-driven development

新しいアプリケーション開発を始めるための、AI駆動開発テンプレートです。WSL2上のVS Code Dev Containersを開発環境とし、Python 3.12、Node.js 24、Git、GitHub CLI、Clineなどの開発支援拡張機能を利用できる構成を用意しています。

現在はアプリケーション本体を実装していません。含まれるのは、AWS CDKの最小構成、Lambdaのサンプル、テスト、GitHub ActionsのCI/CD・AI Issueワークフロー、および開発基盤の設定です。AWS CDKによるクラウド操作と各環境へのデプロイは、初期状態では無効です。

## 最短で開発を始める

1. プロジェクト管理者は、[GitHubリポジトリの初回設定](docs/github-repository-setup.md) を実施します。
2. 開発者は、[開発者セットアップ](docs/developer-setup.md) に従ってWSL2、Docker Engine、VS Code、Dev Containerを準備します。
3. 日々の作業は、[開発ガイド](docs/development-guide.md) に従います。

Dev Container内で初回検証を行う場合は、次を実行します。

```bash
npm ci
python -m pip install -r requirements-dev.lock
npm run typecheck
npm test
python -m pytest
npm run synth
```

## ドキュメント

- [GitHubリポジトリの初回設定](docs/github-repository-setup.md): プロジェクト管理者がGitHub・AWS管理画面とリポジトリ設定で行う初期設定
- [開発者セットアップ](docs/developer-setup.md): 各開発者が端末・アカウントで行う準備
- [開発ガイド](docs/development-guide.md): 日々の実装、テスト、PR、AI Issueワークフローの利用方法
- [AWS CDKアーキテクチャ](docs/aws-cdk-architecture.md): AWS CDK、Stack、preview環境の設計

アプリケーションを実装した後は、このREADMEをアプリケーションの概要、機能、利用方法へ置き換え、開発基盤に関する詳細は上記ドキュメントを参照してください。
