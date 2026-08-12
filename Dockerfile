# syntax=docker/dockerfile:1.6
FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /workspace

# Build dependencies for compiling C extensions (dd.cudd)
RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      printf '%s\n' \
        'Types: deb' \
        'URIs: https://mirrors.tuna.tsinghua.edu.cn/debian' \
        'Suites: trixie trixie-updates' \
        'Components: main' \
        'Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg' \
        '' \
        'Types: deb' \
        'URIs: https://mirrors.tuna.tsinghua.edu.cn/debian-security' \
        'Suites: trixie-security' \
        'Components: main' \
        'Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg' \
        > /etc/apt/sources.list.d/debian.sources; \
    else \
      printf '%s\n' \
        'deb https://mirrors.tuna.tsinghua.edu.cn/debian trixie main' \
        'deb https://mirrors.tuna.tsinghua.edu.cn/debian trixie-updates main' \
        'deb https://mirrors.tuna.tsinghua.edu.cn/debian-security trixie-security main' \
        > /etc/apt/sources.list; \
    fi; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      bash ca-certificates coreutils \
      build-essential git wget; \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt /workspace/requirements.txt

RUN set -eux; \
    python -m pip install --upgrade pip; \
    python -m pip install -r /workspace/requirements.txt

# Copy the rest of the repository (DQreuse excluded via .dockerignore)
COPY . /workspace

# Build and install dd from the vendored tarball with CUDD enabled
RUN set -eux; \
    test -f /workspace/third_party/dd-0.6.0.tar.gz; \
    tar -xzf /workspace/third_party/dd-0.6.0.tar.gz -C /tmp; \
    cd /tmp/dd-0.6.0; \
    export DD_FETCH=1 DD_CUDD=1 DD_CUDD_ZDD=1; \
    export PIP_DISABLE_PIP_VERSION_CHECK=1; \
    export PIP_DEFAULT_TIMEOUT=120; \
    python -m pip wheel . -v --no-build-isolation -w /tmp/wheels; \
    ls -lah /tmp/wheels; \
    python -m pip install --no-deps --force-reinstall /tmp/wheels/dd-0.6.0-*.whl

# Verify dd.cudd import in a separate RUN (simpler and avoids heredoc parsing issues)
RUN python -c "import sys, dd, pkgutil; print('python:', sys.version); print('dd file:', dd.__file__); print('dd.cudd loader:', pkgutil.find_loader('dd.cudd')); import dd.cudd; print('dd.cudd OK')"

# Install the library itself after the canonical backend has been verified.
RUN python -m pip install --no-deps /workspace && \
    python -c "from qseqsim import QSeqSimulator; print('qseqsim package OK:', QSeqSimulator)"

RUN chmod +x /workspace/ae/scripts/*.sh

CMD ["bash"]
