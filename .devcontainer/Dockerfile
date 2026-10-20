# Python, Git, GitHub CLI, common development tools, and the non-root vscode user.
# Node.js is added by the Feature in devcontainer.json.
ARG PYTHON_VERSION=3.12
FROM mcr.microsoft.com/devcontainers/python:${PYTHON_VERSION}-bookworm

USER root

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        build-essential \
        curl \
        git \
        jq \
        ripgrep \
        squid \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

# Squid runs on demand as vscode, without a system service or root permissions.
COPY .devcontainer/squid/proxy.py .devcontainer/squid/squid.conf /usr/local/share/devcontainer-squid/
COPY .devcontainer/squid/proxy-env.sh /etc/profile.d/devcontainer-squid.sh
RUN ln -s /usr/local/share/devcontainer-squid/proxy.py /usr/local/bin/dev-proxy \
    && chmod 755 /usr/local/share/devcontainer-squid/proxy.py \
    && printf '\n. /etc/profile.d/devcontainer-squid.sh\n' >> /home/vscode/.bashrc

USER vscode
