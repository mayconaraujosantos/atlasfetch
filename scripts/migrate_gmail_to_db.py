#!/usr/bin/env python3
"""Migra credentials.json e token.json para a tabela gmail_oauth_config."""

import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
sys.path.insert(0, os.path.join(_root, "src"))

from atlasfetch.infrastructure.persistence.database import (
    init_db,
    get_gmail_oauth_config,
    set_gmail_oauth_config,
)

init_db()
creds, token = get_gmail_oauth_config()
if creds and token:
    print("Já existe no banco.")
    sys.exit(0)

p, t = "credentials.json", "token.json"
if os.path.exists(p) and os.path.exists(t):
    with open(p, encoding="utf-8") as f:
        creds_json = f.read()
    with open(t, encoding="utf-8") as f:
        token_json = f.read()
    set_gmail_oauth_config(credentials_json=creds_json, token_json=token_json)
    print("Migrado para o banco.")
else:
    print("Arquivos credentials.json e token.json não encontrados.")
    sys.exit(1)
