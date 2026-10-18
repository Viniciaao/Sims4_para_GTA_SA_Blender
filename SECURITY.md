# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| 1.0.8 | ✅ |
| < 1.0.8 | ⚠️ Atualize |

## Reporting a Vulnerability

Abra uma Issue privada ou envie para o dono do repositório via GitHub. Não divulgue publicamente antes de correção.

Vulnerabilidades de parsing DFF (ex: buffer overflow em chunks) são tratadas com prioridade — o `core.py` valida todos os tamanhos antes de ler.
