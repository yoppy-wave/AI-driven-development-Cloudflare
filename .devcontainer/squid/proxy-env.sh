# New login and interactive Bash shells opt in without changing disabled shells.
if [ -f "$HOME/.local/state/devcontainer-squid/enabled" ]; then
    export HTTP_PROXY=http://127.0.0.1:3128 HTTPS_PROXY=http://127.0.0.1:3128
    export http_proxy=http://127.0.0.1:3128 https_proxy=http://127.0.0.1:3128
    export NO_PROXY=localhost,127.0.0.1,::1 no_proxy=localhost,127.0.0.1,::1
fi
