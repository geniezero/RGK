#!/usr/bin/env bash
# =====================================================================
#  IA Platform - lancement (macOS / Linux)
#  1. cree l'environnement Python .venv au premier lancement
#     et installe les dependances (requirements.txt)
#  2. active l'environnement
#  3. demarre l'application : streamlit run app.py
#  Port different :  PORT=8600 ./lancer.sh
# =====================================================================
set -e
cd "$(dirname "$0")"
PORT="${PORT:-8501}"

if [ ! -f ".venv/bin/activate" ]; then
    echo "Premier lancement : creation de l'environnement Python .venv ..."
    PY="$(command -v python3 || command -v python || true)"
    if [ -z "$PY" ]; then
        echo "Python 3 est introuvable. Installez-le depuis https://www.python.org puis relancez ce script."
        exit 1
    fi
    "$PY" -m venv .venv
fi

# activation de l'environnement
# shellcheck disable=SC1091
source .venv/bin/activate

# installation (ou mise a jour) des dependances si requirements.txt a change
if ! cmp -s requirements.txt .venv/requirements.installe; then
    echo "Installation des dependances ..."
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    cp requirements.txt .venv/requirements.installe
fi

# pas de question "email" de Streamlit au premier lancement
if [ ! -f "$HOME/.streamlit/credentials.toml" ]; then
    mkdir -p "$HOME/.streamlit"
    printf '[general]\nemail = ""\n' > "$HOME/.streamlit/credentials.toml"
fi

echo ""
echo "IA Platform demarre : http://localhost:${PORT}   (Ctrl+C pour arreter)"
echo ""
streamlit run app.py --server.port "${PORT}"
