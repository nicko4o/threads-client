# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

We take the security of `threads-client` and user credentials seriously.

If you discover a security vulnerability (such as a secret leakage, improper token handling, or unsafe serialization), please **DO NOT** open a public issue.

Instead, please report it via:
1. **GitHub Private Vulnerability Reporting**: Go to the Security tab of the repository and click "Report a vulnerability".
2. **Email**: Contact the repository maintainer directly.

Please include:
- A description of the vulnerability.
- Minimal steps or proof-of-concept script to reproduce.
- Any potential impact on Meta access tokens or application secrets.

We will acknowledge receipt within 48 hours and work with you on a coordinated disclosure and patch release.

## Credential Safety Guidelines

- `threads-client` is designed to automatically redact `access_token` from error logs.
- Never commit `.env` files or hardcoded Meta tokens to Git.
- Use environment variables or secret managers to pass `access_token` and `app_secret`.
