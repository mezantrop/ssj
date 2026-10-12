#!/bin/sh

# Usage:
#   build.sh | build.sh clean

[ "$1" = 'clean' ] && {
    rm -rf build dist ssj.spec
    exit 0
}

PLATFORM=$(uname -s)
VENV_PATH=.venv-${PLATFORM}
VENV_PYTHON=${VENV_PATH}/bin/python3
BUILD_PATH=build/${PLATFORM}
DIST_PATH=dist/${PLATFORM}

[ ! -f ${VENV_PYTHON} ] && {
    python3 -m venv ${VENV_PATH} || exit 1
}

${VENV_PYTHON} -m pip install --upgrade pip || exit 1
${VENV_PYTHON} -m pip install --upgrade paramiko pyinstaller || exit 1

${VENV_PYTHON} -m PyInstaller \
    --clean \
    --noconfirm \
    --onefile \
    --console \
    --workpath ${BUILD_PATH} \
    --distpath ${DIST_PATH} \
    ssj.py