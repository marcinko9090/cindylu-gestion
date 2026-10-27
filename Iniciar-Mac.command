#!/bin/bash
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null; then
 echo 'Instala Python 3.11 o superior desde python.org.'; read -r; exit 1
fi
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt || exit 1
.venv/bin/python app.py
