# Contributing

Start with the findings, experiment guide, and roadmap. Keep measured results
separate from code-derived interpretations and proposed fixes.

For a new experiment, provide the exact model/build/MCU version, script hash,
initial register values, connected inputs, recovery strategy, timestamped
trace, source-side observation, and explicit limitations. Test a new sequence
on a spare before a connected-source trial. Do not remove the public scripts'
guards to broaden an existing experiment.

Before submitting changes:

```sh
python -m unittest discover -s tests -v
python tools/check_publication.py
```

On a system with Bash, also run `bash -n` on each file under `experiments/`.
Never add raw credentials, private hostnames, monitor instance identifiers,
device dumps, or vendor binaries. Publish only reviewed/anonymized evidence,
with hashes and a description of any transformations. Contributions use the
repository's MIT license for original code and documentation.

Review Git author/committer names and email addresses as well as file contents
before publication. Project-maintained anonymized commits use the name
`Comet X HDMI Persistence Contributors` and `contributors@cometx.invalid`.
Do not include private identifiers in scan rules or test fixtures; use invented
examples. Historical shorthand KVM02/KVM03/TR2 is approved for this evidence.
