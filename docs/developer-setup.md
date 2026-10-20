# 開発者セットアップ

この文書は、新しく参加する開発者が自分の端末とアカウントを準備し、Dev Container内で開発を始めるまでの手順です。GitHub・AWSのプロジェクト初期設定は[GitHubリポジトリの初回設定](github-repository-setup.md)、日々の作業は[開発ガイド](development-guide.md)を参照してください。

認証情報、APIキー、パスワードをソースコード、Git管理対象ファイル、READMEへ保存しないでください。

## 準備の分担

| 各開発者が手動で準備するもの | Dev Containerが準備するもの |
| --- | --- |
| WSL2、Linuxディストリビューション、Docker Engine、VS Code | Python 3.12系の開発環境 |
| VS CodeのWSL / Dev Containers拡張機能 | Node.js 24系 |
| GitHubアカウント、Git設定、GitHub CLI認証 | Git、GitHub CLI、`rg`などのツール |
| リポジトリのclone | プロジェクト直下の`.venv` |
| ClineなどのAIツールに対する個人の認証 | Cline、Python、Ruff、ESLint、Prettier、GitHub Actions拡張機能 |
| 会社のプロキシ・証明書・ネットワーク要件への対応 | このリポジトリで定義したVS Code設定とポート転送 |

## 1. 端末とアカウントの準備

### WSL2、Docker Engine、VS Code

Windowsでローカル開発する場合は、WSL2、Linuxディストリビューション、Docker Engine、VS Codeを**各自で手動インストール**します。このリポジトリはOSやDocker Engineの導入を自動化しません。Docker Desktopは必須ではありません。

- [MicrosoftのWSLインストールガイド](https://learn.microsoft.com/windows/wsl/install)
- [Docker EngineのUbuntu向け公式手順](https://docs.docker.com/engine/install/ubuntu/)
- [Dockerのインストール後の手順](https://docs.docker.com/engine/install/linux-postinstall/)（Dockerを非rootユーザーで利用する場合）
- [VS CodeのDev Containers利用ガイド](https://code.visualstudio.com/docs/devcontainers/containers)

VS Codeには、少なくともWSL拡張機能とDev Containers拡張機能を導入します。`.vscode/extensions.json`にも推奨拡張機能として登録されています。

### GitHubアカウントとGit

プロジェクト管理者からリポジトリへのアクセスを受け、cloneする**前に**privateリポジトリへのアクセス権限と認証方法を確認します。HTTPSではOSやGit Credential Managerなどの認証機構、SSHではGitHubアカウントへ登録したSSH鍵を使ってcloneします。WSLホスト側にGitHub CLIを必ずインストールする必要はありません。

WSLホスト側のGit認証は`git clone`や`git push`で使う認証であり、Dev Container内の`gh auth login`はGitHub CLIでIssueやPRを操作するための認証です。別の環境として扱い、それぞれ必要な場所で設定します。認証トークンや秘密鍵をソースコード、Git管理対象ファイル、シェル履歴へ保存しないでください。

Gitの表示名とメールアドレスを設定します。以下はDev Container内で設定する例です。

```bash
git config --global user.name "あなたの名前"
git config --global user.email "あなたのメールアドレス"
```

## 2. ローカルでのリポジトリ取得とDev Container起動

WSL側のファイルシステムにcloneします。ファイル操作性能のため、Windows側の`/mnt/c/...`ではなく、たとえば`~/projects/...`を推奨します。

```bash
mkdir -p ~/projects
cd ~/projects
git clone <リポジトリのURL>
cd AI-driven-development-aws
code .
```

VS Code左下が **WSL: Ubuntu** など、WSL接続であることを確認します。Windows側でフォルダーを開いた場合は、まず `Ctrl+Shift+P` → **WSL: Reopen Folder in WSL** を選択します。

次に `Ctrl+Shift+P` → **Dev Containers: Reopen in Container** を選択します。初回はイメージの取得、コンテナのビルド、拡張機能のインストールがあるため、インターネット接続が必要です。通常のフォルダーを開くだけでは、コンテナ作成や拡張機能の導入は始まりません。

コンテナ接続後、`.venv`は自動作成され、Python拡張機能はこの環境を使います。ターミナルで明示的に有効化する場合は次を実行します。

```bash
source .venv/bin/activate
```

Windowsなど別環境で作成済みの`.venv`がある場合は、初回作成前に別名へ退避してください。Pythonバージョンを変える場合も、既存の`.venv`を退避してからコンテナを再ビルドします。

## 3. GitHub Codespacesを利用する場合

GitHub Codespacesでも、リポジトリにある`.devcontainer/devcontainer.json`を利用して開発環境を作成できます。Codespacesを利用する場合、ローカルのWSL2とDocker Engineのセットアップは不要です。

1. GitHub上で対象リポジトリを開き、開発するブランチを選択します。
2. **Code → Codespaces** を開き、**Create codespace** を選択します。
3. ブラウザーまたはVS CodeでCodespaceを開き、環境構築の完了を待ちます。
4. [GitHub公式ドキュメント](https://docs.github.com/en/codespaces/developing-in-a-codespace/creating-a-codespace-for-a-repository)を参照し、組織の利用・課金方針と利用可能な作成方法を確認します。

CodespaceはローカルのDev Containerとは別の実行環境です。ClineなどのAIツールの認証は、利用する環境ごとに設定してください。認証情報をリポジトリへ保存しない方針はCodespacesでも同じです。

## 4. コンテナと個人認証の確認

コンテナ内の新しいターミナルで、環境を確認します。

```bash
python3 --version
node --version
npm --version
git --version
gh --version
rg --version
.venv/bin/python -m pip --version
whoami
```

Pythonは3.12系、Node.jsは24系、ユーザーは`vscode`になる想定です。コンテナ作成時に、現在のワークスペースだけをGitの`safe.directory`へ登録します。

Dev ContainerまたはCodespace内でGitHub CLIを使う場合はログインします。対話画面でGitHub.com、利用するGitプロトコル、ブラウザー認証を選びます。

```bash
gh auth login
gh auth status
```

Dev ContainerまたはCodespaceを削除・再作成すると、コンテナ内のGit設定とGitHub CLI認証は失われる場合があります。その場合は再設定してください。

## 5. AI開発ツールの準備

Dev ContainerはCline拡張機能を自動インストールします。インストール後、VS Codeのサイドバーから利用するプロバイダー、モデル、認証を各自で設定します。手順は[Clineの公式ドキュメント](https://docs.cline.bot/getting-started/installing-cline)を参照してください。

APIキーはClineの設定画面など、個人の安全な認証領域へ入力します。Dockerfile、`.devcontainer/`配下、Git管理対象の設定ファイル、コミットには保存しません。別のAI拡張機能を使う場合は、個人環境で追加するか、プロジェクトとして標準化する必要がある場合は管理者・チームで検討します。

## 6. 依存関係と初回検証

アプリケーション依存関係はDev Containerでは自動導入しません。コンテナ内で次を実行します。

```bash
npm ci
python -m pip install -r requirements-dev.lock
npm run typecheck
npm test
python -m pytest
npm run synth
```

現在のリポジトリには、AWS CDKのTypeScript構成、Lambdaサンプル、Python・TypeScriptのテストがあります。AWS操作は初期状態で無効です。`cdk deploy`、`cdk destroy`、`cdk bootstrap`、AWS認証は、対象アカウント、リージョン、Stack、変更・削除対象、復旧方法を確認した明示承認なしに実行しません。

`Dockerfile`だけを`docker build`しても、Node.js Feature、VS Code拡張機能、`.venv`作成は適用されません。開発環境の構築にはDev Containersを使用してください。`devcontainer.json`やDockerfileを変更した場合は **Dev Containers: Rebuild Container** を実行します。

## 7. 会社ネットワーク・プロキシの確認

会社環境では、clone、Dockerイメージ取得、VS Code拡張機能、npm、PyPI、GitHub CLI、AIサービスへの通信が許可されているかを確認します。プロキシ、独自CA証明書、VPN、パッケージレジストリの設定が必要な場合は、会社の手順に従って各自の環境へ設定します。

### 任意のSquidホワイトリスト

Squidはイメージへインストールしますが、**初期状態は無効**です。ビルド時のapt・Feature取得にこのホワイトリストは適用しません。無効時はプロキシ環境変数を変更せず、従来の開発環境を維持します。

単一コンテナ内で`vscode`ユーザーのSquidを起動します。別コンテナ方式はプロセスを分離できますが、Compose化・共有ネットワーク・ライフサイクルの変更が必要です。今回は既存Dockerfile構成への影響を小さくするため同一コンテナ方式を選びました。systemdやroot権限での常駐サービスは使いません。

待受は`127.0.0.1:3128`だけで、外部インターフェースへ公開しません。VS Codeの自動ポート転送対象からも除外しています。手動転送やDockerのポート公開はしないでください。HTTPは80番、HTTPS CONNECTは443番のみ許可し、ホワイトリスト外は拒否します。IP直接指定から逆引きで許可ドメインへ一致させる動作も無効です。TLS復号・HTTPキャッシュは行いません。

### 有効化・無効化

この変更を取り込んだら **Dev Containers: Rebuild Container** を実行します。リポジトリルートで必要な許可先を編集してから有効化します。AIプロバイダーの候補はコメントなので、利用するものだけコメントを外してください。

```bash
dev-proxy enable --workspace "$PWD"
dev-proxy status
```

有効化後は**新しいBashターミナル**を開きます。ログイン／対話Bashに`HTTP_PROXY`・`HTTPS_PROXY`と小文字版を設定し、`NO_PROXY`・`no_proxy`は`localhost,127.0.0.1,::1`だけにします。現在のBashへ反映する場合は次を実行します。

```bash
source /etc/profile.d/devcontainer-squid.sh
```

有効化の印・ワークスペースの場所は`~/.local/state/devcontainer-squid/enabled`へ保存します。コンテナ再起動時は`postStartCommand`で自動再開します。起動に失敗した場合はコマンドが失敗し、`cache.log`で診断できます。有効化済みのシェルはプロキシが停止しても直接通信へ切り替えません。コンテナ再作成でホームの状態が失われた場合は、再度有効化してください。

VS Codeの拡張ホストは既に起動しているため、ターミナルの環境変数変更だけでは反映されません。**Remote [Dev Container] のユーザー設定**へ以下を追加し、**Developer: Reload Window**を実行します。リポジトリ共通設定には保存せず、既存の会社プロキシ設定は控えておきます。

```json
"http.proxy": "http://127.0.0.1:3128",
"http.proxySupport": "override"
```

Clineがコンテナ側で動いていることを「Developer: Show Running Extensions」で確認します。プロバイダー、SDK、MCPサーバーごとにプロキシ対応が異なるため、実際の操作後に`access.log`で経由を確認してください。APIキーの設定・AI API呼び出しは個人で行い、テストのためにキーをリポジトリへ保存しません。プロバイダー未登録のまま有効化すると、その通信は拒否されます。

無効化するときは次を実行します。

```bash
dev-proxy disable
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy NO_PROXY no_proxy
```

Remoteの`http.proxy`・`http.proxySupport`を導入前の値へ戻し、Reload Window後に新しいターミナルを開きます。会社プロキシを使っていた場合はその環境変数も元に戻します。既存プロセスの環境変数は自動では書き換わりません。Zshなど別のシェル、タスクや拡張が起動する非対話プロセスは、個別に環境変数またはツールのプロキシ設定が必要です。

### 許可先の編集・反映

`.devcontainer/squid/whitelist.txt`に1行1ドメインで記載します。`#`以降はコメントです。通常は`api.example.com`のような正確なホスト名を使います。`.api.example.com`は配下のサブドメインも許可するため、必要性を確認した場合に限ります。`*`、URL、パス、ポート、認証情報は記載できません。`.com`や大手クラウド全体のような広い範囲を許可しないでください。

```bash
dev-proxy reload
```

再読込は構文検証後の短い再起動です。既存CONNECTも切断するため、許可を取り消した宛先の接続が残りません。進行中のダウンロードは再実行してください。`squid.conf`と制御プログラムはイメージにコピーするので、それらの変更はRebuild Containerが必要です。ホワイトリストだけの変更には再ビルド不要です。

| ツール・通信 | 経路と確認点 |
| --- | --- |
| Git HTTPS / GitHub CLI | 新ターミナルのプロキシ環境変数を使用。Git固有の`http.proxy`等がある場合は上書きに注意。Git SSHは対象外 |
| npm / pip | プロキシ環境変数を使用。`.npmrc`・pip設定の独自proxy/index、依存のダウンロード先やリダイレクト先も確認 |
| Cline / VS Code拡張 | Remoteの`http.proxy`を設定。独自HTTPクライアント・SDK・MCPは対応を個別確認。ログに現れなければ制御できたと判断しない |
| VS Code本体・拡張の配布 | Windows/WSLホスト側から取得される場合はこのSquidの対象外。publisher別CDNは拒否ログから必要な正確なホストを追加 |
| Docker build・Feature取得 | コンテナ起動前なので対象外。Docker/ホスト側の設定に従う |

初期リストにはGitHub HTTPS/API/配布用ホスト、npm、PyPIなどを追加していますが、すべてのSDK・拡張・会社レジストリを網羅するものではありません。リダイレクト先も別途判定されます。

### ログとトラブルシューティング

ログの場所は`~/.local/state/devcontainer-squid/`です。ディレクトリは所有ユーザー限定、新規ファイルは所有ユーザーだけが読める権限で作成します。ワークスペース外で、Gitへ保存しません。念のため`*.log`・ローテーション済みログ・`.devcontainer/squid/.local/`もGit/Dockerビルド対象外にしています。

```bash
dev-proxy status
tail -f ~/.local/state/devcontainer-squid/access.log
tail -n 50 ~/.local/state/devcontainer-squid/cache.log
dev-proxy denied
# 現在のログだけを抽出する場合
grep 'TCP_DENIED/' ~/.local/state/devcontainer-squid/access.log
```

`access.log`は「Unix時刻（秒.ミリ秒）、宛先ホスト、ポート、Squid結果/HTTPステータス」の4列です。`TCP_DENIED/403`が拒否、`TCP_TUNNEL/200`が成功したCONNECTなどを表します。CONNECTの記録はトンネル終了時なので、長時間接続はすぐには記録されないことがあります。日時の変換例は`date -d @1792458000`です。

URLパス・クエリ・ユーザー名・Authorization・Cookie・本文は記録しません。Squidの生の診断にもURLが含まれ得るため、`cache.log`はstderrを起動・待受・再設定・停止、権限不足・ポート競合・ファイル欠落・構文エラーなどの定型メッセージへ分類したログです。未知の警告/エラーは詳細を省略し、通常の詳細メッセージは破棄します。生のstderr、コアダンプ、HTTPキャッシュは保存しません。宛先ホスト自体は記録するので、機密値をホスト名に含めないでください。

`cache.log`は1 MiBごとに3世代、`access.log`は5秒ごとのサイズ確認で1 MiB以上ならSquid自身が3世代へローテーションします。access側は確認間隔中の増加分を許すソフト上限で、ディスクの厳密な使用量制限ではありません。常駐cronや外部ログ基盤は不要です。ログはコンテナ削除時に失われます。調査目的で持ち出す場合も宛先情報の取り扱いに注意してください。

通信できないときは次の順に確認します。

1. `dev-proxy status`と`cache.log`で起動・ポート競合・設定ファイルの状態を確認する。
2. プロキシを明示した下記curlで、Squid自体の許可・拒否を確認する。`-v`や認証ヘッダー付きの診断ログ共有は避ける。
3. `dev-proxy denied`で正確な宛先とポートを確認する。必要なドメインだけをホワイトリストへ追加し、`dev-proxy reload`する。
4. 拒否でなく502/503等ならDNS・外部接続・会社の上流プロキシを確認する。この構成には認証付き上流プロキシの自動設定はない。
5. curlは成功してツールが失敗する場合、ツール固有のproxy設定・追加の配布先・CA証明書を確認する。TLS証明書検証を無効化して解決しない。

```bash
# 外部ネットワークが使える環境で実施（許可先は成功、未許可先は403）
curl --proxy http://127.0.0.1:3128 --noproxy '' --max-time 30 -I https://docs.python.org/
curl --proxy http://127.0.0.1:3128 --noproxy '' --max-time 30 -I http://example.com/
```

### 自動テストと制御の限界

```bash
# 単体テスト（Squidや外部通信は不要）
python -m pytest .devcontainer/squid/proxy_test.py -q
# Squid実機・ローカル疑似HTTPサーバーによる統合テスト
# 実行前にdev-proxy disableし、3128番を空ける
SQUID_INTEGRATION=1 python -m pytest .devcontainer/squid/integration_test.py -q
```

統合テストは外部ネットワーク・認証情報不要で、設定パース、起動、HTTP/CONNECTの許可拒否、ログ、疑似機密値の非記録、許可の追加/取消、ローテーション、無効化を確認します。通常のpytestでは実機テストのみ明示的にスキップし、CI/CDの構成は変更しません。

**これは協調的なHTTP/HTTPSプロキシ設定であり、コンテナ全体の強制的な出口制御ではありません。**プロキシを無視するプログラム、SSH、UDP/QUIC、直接ソケット、NO_PROXY対象、ホスト側の通信、ユーザーによる設定解除は制限しません。DNS解決もOS側のネットワークを使います。またCONNECTは宛先ホスト・ポートを許可するもので、暗号化された中身やパスを検査しません。許可ドメイン上のサービスを経由する通信まで安全性を保証するものではありません。

迂回防止が必要な会社運用では、Dockerネットワーク/ホストのファイアウォール等で直接の外向き通信を禁止し、DNSやプロキシへの経路を管理する設計が別途必要です。今回はその制御やWSL2/Docker Engineの導入自動化は行いません。

参考: [Squidのログ形式](https://www.squid-cache.org/Doc/config/logformat/)、[Squidのログ運用](https://wiki.squid-cache.org/SquidFaq/SquidLogs)、[VS Code Remoteのプロキシ設定](https://code.visualstudio.com/docs/remote/troubleshooting)。

## 開発開始チェックリスト

- [ ] ローカル開発の場合、WSL2、Linux、Docker Engine、VS Code、WSL / Dev Containers拡張機能を手動で準備した
- [ ] clone前にprivateリポジトリへのアクセス権限と、HTTPSまたはSSHの認証を確認した
- [ ] ローカル開発の場合、WSL側のファイルシステムへリポジトリをcloneし、VS CodeでWSL接続後にDev Containerを起動できた
- [ ] Codespacesを利用する場合、GitHub上でCodespaceを作成し、既存のDev Container定義による環境構築を完了した
- [ ] コンテナ内でPython 3.12系、Node.js 24系、Git、GitHub CLIを確認できた
- [ ] Gitの表示名・メールアドレスを設定し、`gh auth status`でGitHub認証を確認した
- [ ] Clineなど利用するAIツールの個人認証を完了し、認証情報をリポジトリへ保存していない
- [ ] `npm ci`と`python -m pip install -r requirements-dev.lock`が成功した
- [ ] `npm run typecheck`、`npm test`、`python -m pytest`、`npm run synth`が成功した
- [ ] 必要なプロキシ、VPN、証明書、通信許可を確認した
