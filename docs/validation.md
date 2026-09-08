# Publication validation — September 8, 2026

The initial public export was checked locally before creating the GitHub
repository. No new live KVM experiments were performed during packaging.

- Nine automated tests passed: all three published evidence cases, malformed
  and truncated JSONL handling, timestamp ordering, SSH argument validation,
  preview-only behavior, and script execution guards.
- Both public shell scripts passed Bash syntax checks and rejected invocation
  without required execution arguments before hardware access.
- Published evidence hashes matched the manifest. Local Markdown links and
  private-data/file-type checks passed.
- Portable offline extraction/disassembly ran against the original matching
  artifacts supplied outside the checkout.
- The synthetic CPU harness passed eight HPA cases, four EDID RAM write cases,
  and eight EDID bank-assignment cases. These remain synthetic instruction
  tests, not live EDID/DDC validation.
- Original artifact hashes, FIT payload hashes, kernel switch-table entries,
  vendor utility CRC table, and firmware layout checks passed.

Before publication, a further privacy review replaced personal license and Git
attribution with project contributor attribution and removed a site-specific
hostname scan rule. The original commit was rewritten rather than retaining
identifying attribution in an earlier commit. Approved shorthand and technical
test context were preserved. Three additional privacy boundary tests passed,
bringing the local suite to twelve tests. A separate local check compared the
publishable files against private identifiers and the locally held credential;
it reported no matches and did not print or publish the credential.

CI replays the dependency-free evidence/guard checks on Linux and Windows.
It does not contact a KVM or download firmware. Offline binary verification
requires the privately supplied artifacts and is intentionally outside CI.

Use `python tools/check_publication.py` before publishing changes. Raw future
device logs should remain in ignored `runs/` until reviewed and anonymized.
