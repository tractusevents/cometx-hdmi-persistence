# Evidence provenance and publication

The public evidence is a curated export of experiments performed on two
owner-controlled RM4PE units on September 8, 2026. The connected unit is
labelled `kvm-connected`, the source-free spare `kvm-lab`, and the Windows
computer `SOURCE-B`.

Historical shorthand `KVM02`, `KVM03`, and `TR2` is also retained. These labels
are approved for publication; full internal hostnames are excluded.

The [manifest](../evidence/2026-09-08/manifest.json) records original SHA-256,
published SHA-256, byte lengths, and omitted truncated lines for each file.
Original files remain in the private research workspace; they are not
uploaded here. Different hashes are expected because this export is
anonymized and JSON formatting is normalized.

## Transformations

- Replaced private device/computer names, user-home paths, and monitor
  instance/interface identifiers with stable aliases.
- Normalized temporary recovery-directory process IDs to `RUN`.
- Retained UTC timestamps, sample counts, register values, source/model
  information, monitor model names, flags, and state transitions.
- Excluded incomplete final JSON lines from two pasted logs. The complete
  records cover the relevant tests; the manifest records the omission.
- Retained original script hashes in hardware reports. Those identify the
  private scripts actually run, not the adapted public scripts.

Hardware and monitor models, port connections, timestamps, and references to
Parsec/NDI remain as experimental context. This is a de-identified research
record, not a claim that the test setup itself is secret or undisclosed.

The initial commit and copyright notice use project contributor attribution.
Its author and committer email is the synthetic, non-deliverable address
`contributors@cometx.invalid`. GitHub account activity and repository ownership
are separate platform metadata; rewriting Git history does not anonymize them.

The public live scripts use the same hardware sequence as their recorded
versions but replace private host bindings with an explicit expected hostname
and profile, require an execution argument, and reject any additional connected source in the connected-B profile. These public adaptations
have syntax/guard tests; the historical hardware observations refer to the
original scripts.

The detailed notebook and reports preserve chronology, including earlier
inconclusive observations and limitations later resolved. Their legacy
tool/output names may refer to private-workspace artifacts not included here.
The curated findings and reproduction guide describe the current public tree.

## Material intentionally excluded

SSH credentials/keys/known-hosts files, raw device configuration trees,
network details, proprietary firmware blobs, boot images, device trees,
original EDID binaries, full generated disassemblies, and dependency bundles
are excluded. This is an allowlist export, not a copy of the original working
directory. Future raw logs belong in ignored `runs/` until reviewed.

`tools/check_publication.py` checks file types, common private-data patterns
(including personal/operational email addresses and prefixed device names),
evidence integrity, and local Markdown links. It is a guardrail, not proof
that arbitrary new data is safe to publish. Review proposed additions.
