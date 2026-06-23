# Security Policy

## Supported Versions

Security fixes are handled on the default branch unless a maintainer announces
otherwise.

## Reporting a Vulnerability

Please do not open a public issue for a suspected vulnerability.

Report security concerns privately to the project maintainer. Include:

- affected component and version or commit
- reproduction steps
- expected impact
- any logs or proof of concept that do not expose real secrets or private data

Do not include production credentials, personal data, API keys, tokens, OTPs, or
private customer material in reports.

## Secret Handling

Never commit `.env` files, service-account files, private keys, database dumps,
uploaded customer documents, generated PDFs with personal data, or local storage
directories. Use `.env.example` files for documented configuration only.
