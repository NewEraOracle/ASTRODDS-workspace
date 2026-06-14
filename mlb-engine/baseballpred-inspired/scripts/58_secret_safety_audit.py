from pathlib import Path
import json
import re
import subprocess
from datetime import datetime

ROOT = Path(r"C:\Users\crypt\OneDrive\Images\ASTRODDS-workspace")
BASE = ROOT / "mlb-engine" / "baseballpred-inspired"

REPORT = BASE / "reports" / "58_secret_safety_audit_report.txt"
OUT_JSON = BASE / "reports" / "58_secret_safety_audit.json"

SECRET_PATTERNS = {
    "telegram_bot_token_literal": re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{25,}\b"),
    "generic_api_key_assignment": re.compile(r"(?i)\b(API_KEY|SECRET|TOKEN|PRIVATE_KEY|PASSWORD|WEBHOOK)\b\s*[:=]\s*['\"]?([A-Za-z0-9_\-:/\.]{16,})"),
    "bearer_token_literal": re.compile(r"(?i)\bBearer\s+[A-Za-z0-9_\-\.]{20,}"),
    "private_key_block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}

ALLOWLIST_FILENAMES = {
    ".env.local",
}

SKIP_DIRS = {
    ".git",
    "node_modules",
    ".next",
    "__pycache__",
    ".astrodds",
}

TEXT_EXTS = {
    ".py", ".ps1", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".json", ".md", ".txt", ".css", ".html", ".yml", ".yaml"
}

SAFE_REFERENCE_WORDS = [
    "process.env",
    "env_value",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "TELEGRAM_SIGNALS_CHAT_ID",
    "TELEGRAM_REVIEW_CHAT_ID",
    "ODDS_API_KEY",
    "POLYMARKET",
    "TOKEN'",
    'TOKEN"',
    "API_KEY'",
    'API_KEY"',
]

def run_git(args):
    try:
        result = subprocess.run(["git"] + args, cwd=str(ROOT), capture_output=True, text=True, timeout=60)
        return result.stdout.strip()
    except Exception as e:
        return f"ERROR: {e}"

def is_skipped(path):
    parts = set(path.parts)
    return bool(parts & SKIP_DIRS)

def redact_match(text):
    if len(text) <= 8:
        return "***"
    return text[:4] + "***" + text[-4:]

def is_safe_reference(line, sample):
    s = str(sample or "")
    line_s = str(line or "")

    if any(w in line_s for w in SAFE_REFERENCE_WORDS):
        return True

    # Ignore literal env variable names/placeholders such as TELEGRAM_BOT_TOKEN,
    # API_KEY, TOKEN, or object key names like token: process.env.TELEGRAM_BOT_TOKEN.
    if re.fullmatch(r"[A-Z0-9_]{8,}", s):
        return True

    # Ignore common placeholder values.
    if s.upper() in ["TOKEN", "API_KEY", "SECRET", "PASSWORD", "PRIVATE_KEY", "WEBHOOK"]:
        return True

    return False

def scan_file(path):
    findings = []
    try:
        content = path.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        return findings

    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    if path.name in ALLOWLIST_FILENAMES:
        return findings

    for line_no, line in enumerate(content.splitlines(), start=1):
        for name, pattern in SECRET_PATTERNS.items():
            for m in pattern.finditer(line):
                sample = m.group(0)
                if is_safe_reference(line, sample):
                    continue
                findings.append({
                    "file": rel,
                    "line": line_no,
                    "type": name,
                    "redactedSample": redact_match(sample),
                })
    return findings

def tracked_env_files():
    out = run_git(["ls-files"])
    files = [line.strip() for line in out.splitlines() if line.strip()]
    return [f for f in files if ".env" in f.lower() or f.lower().endswith("env")]

def env_history_files():
    out = run_git(["log", "--all", "--name-only", "--pretty=format:"])
    files = sorted(set(line.strip() for line in out.splitlines() if line.strip()))
    return [f for f in files if ".env" in f.lower() or f.lower().endswith("env")]

def ignored_env_check():
    out = run_git(["check-ignore", "-v", ".env.local", ".env", ".env.production", ".env.development"])
    return out.splitlines() if out else []

def main():
    generated = datetime.utcnow().isoformat() + "Z"

    tracked_env = tracked_env_files()
    history_env = env_history_files()
    ignore_lines = ignored_env_check()
    git_status = run_git(["status", "--short"]).splitlines()

    findings = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if is_skipped(path):
            continue
        if path.suffix.lower() not in TEXT_EXTS:
            continue
        findings.extend(scan_file(path))

    dirty_lines = [x for x in git_status if x.strip()]
    # The audit script/report itself can be dirty during the audit run. That should not make secret safety fail.
    non_audit_dirty = [
        x for x in dirty_lines
        if "58_secret_safety_audit" not in x
    ]

    status = "SAFE_NO_TRACKED_ENV_NO_LITERAL_SECRETS"
    if tracked_env or history_env or findings or non_audit_dirty:
        status = "REVIEW_NEEDED"

    output = {
        "generatedAt": generated,
        "status": status,
        "trackedEnvFiles": tracked_env,
        "envFilesEverCommitted": history_env,
        "ignoreCheck": ignore_lines,
        "literalSecretFindingsRedacted": findings,
        "gitStatusShort": git_status,
        "nonAuditDirtyLines": non_audit_dirty,
        "notes": [
            "This audit does not print full secret values.",
            "Variable names like TELEGRAM_BOT_TOKEN in code are normal if values are loaded from .env.local.",
            "If any real literal secret appears in tracked files or history, rotate that key."
        ],
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(output, indent=2), encoding="utf-8")

    lines = []
    lines.append("ASTRODDS 58 SECRET SAFETY AUDIT REPORT")
    lines.append("=" * 46)
    lines.append(f"Generated: {generated}")
    lines.append("")
    lines.append(f"Status: {status}")
    lines.append("")
    lines.append("Checks:")
    lines.append(f"- Git status dirty lines: {len(dirty_lines)}")
    lines.append(f"- Non-audit dirty lines: {len(non_audit_dirty)}")
    lines.append(f"- Tracked env files: {len(tracked_env)}")
    lines.append(f"- Env files ever committed: {len(history_env)}")
    lines.append(f"- Ignore rules found: {len(ignore_lines)}")
    lines.append(f"- Redacted literal secret findings in tracked/workspace text files: {len(findings)}")
    lines.append("")
    lines.append("Tracked env files:")
    if tracked_env:
        for f in tracked_env:
            lines.append(f"- {f}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("Env files ever committed:")
    if history_env:
        for f in history_env:
            lines.append(f"- {f}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("Ignore check:")
    if ignore_lines:
        for line in ignore_lines:
            lines.append(f"- {line}")
    else:
        lines.append("- no ignore output")
    lines.append("")
    lines.append("Redacted literal secret findings:")
    if findings:
        for f in findings[:50]:
            lines.append(f"- {f['file']}:{f['line']} | {f['type']} | {f['redactedSample']}")
        if len(findings) > 50:
            lines.append(f"- ... {len(findings) - 50} more")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("Interpretation:")
    if status == "SAFE_NO_TRACKED_ENV_NO_LITERAL_SECRETS":
        lines.append("- .env files are not tracked and no obvious literal secrets were found in scanned text files.")
        lines.append("- Code may safely reference env variable names like TELEGRAM_BOT_TOKEN without containing the secret value.")
    else:
        lines.append("- Review needed. If any literal secret is real, rotate that key and remove it from Git history.")
    lines.append("")
    lines.append(f"JSON: {OUT_JSON}")
    lines.append("")
    lines.append("Rule: security audit only. No secret values printed. No scans. No real-money automation.")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print("")
    print(f"Saved: {REPORT}")

if __name__ == "__main__":
    main()

