"""Check the proposed public file set, evidence integrity, and local links."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    'prefixed internal device name': re.compile(r'\b[a-z0-9_-]+(?:kvm|rack)\d+\b',re.I),
    'private Windows home': re.compile(r'[A-Z]:[\\/]Users[\\/][A-Za-z0-9_.-]+',re.I),
    'private SSH key': re.compile(r'-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----'),
    'literal SSH public key': re.compile(r'ssh-(?:ed25519|rsa)\s+AAAA'),
    'monitor instance identifier': re.compile(r'UID\d{3,}'),
    'Tailscale hostname': re.compile(r'\btail[a-z0-9]+\.ts\.net\b',re.I),
    'literal secret assignment': re.compile(r'''(?:password|access_token|auth_token)\s*[:=]\s*["'][^"'\s]{6,}["']''',re.I),
}
EMAIL = re.compile(r'\b[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,})\b', re.I)


def privacy_issues(text):
    issues = [name for name, pattern in PATTERNS.items() if pattern.search(text)]
    # Examples and the project's synthetic Git author address are not contacts.
    for match in EMAIL.finditer(text):
        domain = match.group(1).lower()
        if domain.endswith(('.invalid', '.test')) or domain in {'example.com', 'example.org', 'example.net'}:
            continue
        issues.append('personal or operational email address')
        break
    return issues


def public_files():
    if (ROOT/'.git').exists():
        result = subprocess.run(['git','ls-files','--cached','--others','--exclude-standard','-z'],
                                cwd=ROOT,capture_output=True,check=True)
        return sorted({ROOT/p.decode('utf-8') for p in result.stdout.split(b'\0') if p})
    excluded = {'.git','.venv','venv','__pycache__','output','runs'}
    return sorted(p for p in ROOT.rglob('*') if p.is_file() and not (set(p.relative_to(ROOT).parts)&excluded))


def check():
    errors = []
    files = public_files()
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        lower = relative.lower()
        if (path.suffix.lower() in {'.bin','.img','.dtb','.pem','.key','.zip'} or
            'password' in lower or 'known_hosts' in lower or
            ('inputs/' in lower and path.name not in {'README.md','expected-sha256.json'})):
            errors.append(relative+': excluded artifact type')
        data = path.read_bytes()
        if len(data)>2_000_000 or b'\0' in data:
            errors.append(relative+': oversized or binary file')
            continue
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError:
            errors.append(relative+': not UTF-8 text')
            continue
        for name in privacy_issues(text):
            errors.append(relative+': '+name)
        if path.suffix == '.md':
            for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)',text):
                target = target.split('#',1)[0].strip('<>')
                if not target or re.match(r'^[a-z]+:',target,re.I):
                    continue
                if not (path.parent/unquote(target)).exists():
                    errors.append(relative+': missing local link '+target)
    manifest = json.loads((ROOT/'evidence/2026-09-08/manifest.json').read_text(encoding='utf-8'))
    for item in manifest:
        path = (ROOT/item['path']).resolve()
        if not path.is_relative_to(ROOT):
            errors.append('Manifest path escapes checkout')
            continue
        if not path.is_file():
            errors.append(item['path']+': missing evidence')
            continue
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=item['published_sha256'] or len(data)!=item['published_bytes']:
            errors.append(item['path']+': evidence hash/size mismatch')
    return files,errors


def main():
    files,errors = check()
    if errors:
        print('\n'.join(errors))
        return 1
    print(f'PASS: {len(files)} public files; evidence hashes, private-data checks, and local Markdown links.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
