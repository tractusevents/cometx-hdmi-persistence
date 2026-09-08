# Live experiment procedure

These scripts temporarily change hardware registers. They are adapted from
the recorded scripts for the tested RM4PE / MCU 1.1. They are not a persistent
service, supported vendor API, or full four-port fix.

## Preconditions

1. Use an owner-controlled RM4PE matching chip ID `2705` and MCU version
   `1.1`, with recovery access. Test on a spare first.
2. Configure an OpenSSH alias and key-based root login outside this repo.
   Independently verify the SSH host key using your normal process. The runner
   requires an existing known-host entry and never accepts a new key for you.
3. Determine the exact output of `hostname` on the target. The remote script
   checks that value independently of the SSH alias.
4. Choose the connection profile: `source-free` requires no HDMI sources and
   initial channel C; `connected-b` requires B selected and connected with
   normal HPD feedback, with A, C, and D empty.
5. For a connected source, start the [Windows logger](../windows/README.md),
   keep its process open, and avoid simultaneous UI/API switching or upgrades.

## Preview, then execute

The placeholder alias/hostname below must be replaced with your configured
target. First run without `--execute`; it makes **no SSH connection**:

```sh
python tools/run_experiment.py --host my-kvm --expected-hostname my-kvm --profile source-free --experiment resumed
```

Read the displayed script name and local source. When ready to run that
experiment on your unit, append `--execute` to the same command. For the
source-connected test, explicitly choose `--profile connected-b` after
meeting its preconditions and starting the logger.

`--experiment paused` keeps the MCU in its wait loop until return to B.
`--experiment resumed` resumes on D, C, and B for approximately six seconds
each, then pauses to inspect all required state. Both use the direct selector
field rather than a normal ff05 switch. Linux's channel cache, MCU routing
objects, and USB selection stay B during the experiment.

The wrapper uses OpenSSH from PATH, or a path supplied with `--ssh`. SSH
configuration, private keys, and raw execution logs belong outside version
control. The default `runs/` output is ignored. No password helper is included.

## What the scripts change

- Pause/resume mailbox `ff04`.
- Selector `0001[6:4]`, preserving unrelated bits: D, C, B.
- In the source-free profile only, establish B's five HPA mask bits before
  the trial. In the connected-B profile those bits must already be enabled.
- Restore exact saved selector/mask bytes afterward.
- The spare returns to its original C through normal switching after cleanup.

The resumed variant stops if the selector, mode, masks, or required B feedback
changes. It verifies MCU service using `ffff=01` and advancing heartbeat.
There are no EDID writes or firmware flashes.

## Recovery and limits

The script arms a separate Linux process that attempts recovery after 45
seconds. It restores the selector before MCU resume, verifies saved bytes,
and disarms after successful recovery. In the resumed connected-B variant,
if B feedback does not recover, it uses an ordinary empty-C→B switch as a
fallback and checks B again.

This covers ordinary script/session failure while Linux and I2C remain
functional. It does not cover a hung bus, failed Linux system, power loss,
or every unexpected firmware state. An SSH timeout alone does not resume
the MCU. The runner saves timeout output and reports restoration as
unverified; inspect the device before running anything else.

Register reads during normal operation can be misleading. Require paused
`ffff=00` before internal reads/writes, save actual values, and never treat
`0314=cc` as a force-HPD command: the decoded selected-input writes are
consistent with event acknowledgments.

## Next experiment boundary

Do not connect a second source and bypass these guards to extend this script.
Capture acquisition on another live source requires a new reviewed sequence
that accounts for MCU receiver/route state and preserves all required ports.
See the [roadmap](roadmap.md).
