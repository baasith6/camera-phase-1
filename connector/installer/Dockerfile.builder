FROM debian:bookworm-slim

ARG WINDOWS_PYTHON_VERSION=3.11.9
ARG INNO_SETUP_VERSION=6.7.3
ARG WINSW_VERSION=2.12.0

# Wine does not implement the Win32 NUMA-topology API
# (GetNumaNodeProcessorMaskEx). Intel's OpenMP runtime - pulled in by
# numpy/ultralytics - calls it at import time to plan thread affinity,
# treats the "not implemented" result as fatal, and aborts the process
# (PyInstaller then sees "SubprocessDiedError ... exit code 3" while
# scanning ultralytics's binary dependencies). These variables tell
# OpenMP to skip hardware topology detection entirely instead of
# probing an API Wine can't answer.
ENV DEBIAN_FRONTEND=noninteractive \
    WINEARCH=win64 \
    WINEPREFIX=/opt/wine \
    WINEDEBUG=-all \
    PYTHONUNBUFFERED=1 \
    KMP_AFFINITY=disabled \
    KMP_TOPOLOGY_METHOD=flat \
    OMP_NUM_THREADS=1

RUN dpkg --add-architecture i386 \
    && apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl jq python3 unzip wine64 wine32 xvfb xauth \
    && ln -s /usr/lib/wine/wine64 /usr/local/bin/wine64 \
    && ln -s /usr/lib/wine/wineserver64 /usr/local/bin/wineserver \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /toolchain

RUN mkdir -p "$WINEPREFIX/drive_c/Python311" \
    && curl -fL --retry 5 \
      "https://www.python.org/ftp/python/${WINDOWS_PYTHON_VERSION}/python-${WINDOWS_PYTHON_VERSION}-embed-amd64.zip" \
      -o python-embed.zip \
    && unzip -q python-embed.zip -d "$WINEPREFIX/drive_c/Python311" \
    && sed -i 's/^#import site/import site/' "$WINEPREFIX/drive_c/Python311/python311._pth" \
    && curl -fL --retry 5 "https://bootstrap.pypa.io/get-pip.py" -o get-pip.py \
    && xvfb-run -a wine64 C:\\Python311\\python.exe Z:\\toolchain\\get-pip.py \
    && wineserver -w \
    && rm python-embed.zip get-pip.py

RUN curl -fL --retry 5 \
      "https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-${INNO_SETUP_VERSION}.exe" \
      -o inno-setup.exe \
    && (xvfb-run -a wine64 inno-setup.exe /VERYSILENT /SUPPRESSMSGBOXES \
      /NORESTART /DIR=C:\\InnoSetup || true) \
    && wineserver -w \
    && test -s "$WINEPREFIX/drive_c/InnoSetup/ISCC.exe" \
    && rm inno-setup.exe

COPY connector/requirements.txt connector/requirements-build.txt /requirements/
RUN xvfb-run -a wine64 C:\\Python311\\python.exe -m pip install --disable-pip-version-check \
      -r Z:\\requirements\\requirements.txt -r Z:\\requirements\\requirements-build.txt \
      "numpy>=1.26,<2" \
      imageio-ffmpeg==0.6.0 \
    && wineserver -w

RUN mkdir -p /toolchain/files \
    && find "$WINEPREFIX/drive_c/Python311/Lib/site-packages/imageio_ffmpeg/binaries" \
      -type f -name '*.exe' -exec cp '{}' /toolchain/files/ffmpeg.exe \; \
    && test -s /toolchain/files/ffmpeg.exe \
    && curl -fL --retry 5 \
      "https://github.com/winsw/winsw/releases/download/v${WINSW_VERSION}/WinSW.NET461.exe" \
      -o /toolchain/files/WinSW-x64.exe

COPY version.json /src/version.json
COPY connector /src/connector
COPY connector/installer/docker-entrypoint.sh /usr/local/bin/onETIX-installer-build
# Defensive normalization: if this file (or any script COPYed from the host)
# was checked out on Windows with CRLF line endings, the shebang becomes
# "#!/bin/sh\r" and the container fails at exec with a confusing
# "no such file or directory" error - not because the file is missing, but
# because \r is part of the interpreter name. Strip \r regardless of the
# host's git autocrlf setting so this never blocks a fresh clone/build again.
RUN sed -i 's/\r$//' /usr/local/bin/onETIX-installer-build \
    && chmod +x /usr/local/bin/onETIX-installer-build

VOLUME ["/output"]
ENTRYPOINT ["/usr/local/bin/onETIX-installer-build"]
