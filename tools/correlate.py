"""Replay full or compact Windows JSONL against timestamped KVM phases.

No network/device access; accepts a truncated final JSON line but rejects
malformed records in the middle of a log. Published original truncation is
documented in the evidence manifest.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re


def instant(value):
    result = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timestamps must contain a timezone')
    return result


def analyze(windows_path, trial_path):
    raw = Path(windows_path).read_bytes()
    records, ignored = [], []
    lines = raw.decode('utf-8-sig').splitlines()
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            if any(item.strip() for item in lines[index+1:]):
                raise ValueError(f'Malformed JSON at non-terminal line {index+1}') from None
            ignored.append(index+1)
            continue
        if not isinstance(value, dict):
            raise ValueError(f'Expected object at line {index+1}')
        records.append(value)
    samples = [r for r in records if r.get('type') == 'sample' or
               ('type' not in r and {'utc','active_gdi_monitors','changed'} <= r.keys())]
    if not samples:
        raise ValueError('No Windows samples')
    times = [instant(r['utc']) for r in samples]
    for r in samples:
        if type(r['active_gdi_monitors']) is not int or r['active_gdi_monitors'] < 0:
            raise ValueError('Invalid active monitor count')
        if type(r['changed']) is not bool:
            raise ValueError('Invalid changed flag')
    gaps = [(b-a).total_seconds() for a,b in zip(times,times[1:])]
    if any(g <= 0 for g in gaps):
        raise ValueError('Windows sample timestamps must strictly increase')
    trial = json.loads(Path(trial_path).read_text(encoding='utf-8'))
    phases = list(re.findall(r'^(\w+_UTC)=(\S+)$', trial['stdout'], re.M))
    ordered = sorted([(name, instant(value)) for name,value in phases], key=lambda pair: pair[1])
    coverage = []
    for i, (name, start) in enumerate(ordered):
        end = next((time for _,time in ordered[i+1:] if time > start), times[-1]+dt.timedelta(microseconds=1))
        part = [r for r,time in zip(samples,times) if start <= time < end]
        coverage.append({'phase': name, 'start': start.isoformat(), 'end': end.isoformat(),
                         'samples':len(part), 'active_counts':sorted({r['active_gdi_monitors'] for r in part}),
                         'changed_true_samples':sum(r['changed'] for r in part)})
    changes = []
    previous = None
    for r in samples:
        state = {'active_gdi_monitors':r['active_gdi_monitors']}
        if 'displays' in r:
            state['displays'] = r['displays']
        if state != previous:
            changes.append({'utc':r['utc'], 'active_gdi_monitors':r['active_gdi_monitors']})
            previous = state
    first_phase = min((time for _,time in ordered), default=None)
    last_phase = max((time for _,time in ordered), default=None)
    return {'windows_file':Path(windows_path).name, 'windows_sha256':hashlib.sha256(raw).hexdigest(),
            'trial_file':Path(trial_path).name, 'trial_exit_status':trial.get('exit_status'),
            'samples':len(samples), 'first_sample':samples[0]['utc'], 'last_sample':samples[-1]['utc'],
            'active_counts':sorted({r['active_gdi_monitors'] for r in samples}),
            'state_observations':changes, 'changed_true_samples':[r['utc'] for r in samples if r['changed']],
            'maximum_gap_seconds':max(gaps, default=0),
            'gaps_over_1_1_seconds':[{'from':samples[i]['utc'],'to':samples[i+1]['utc'],'seconds':g}
                                    for i,g in enumerate(gaps) if g > 1.1],
            'ignored_incomplete_terminal_lines':ignored,
            'covers_all_recorded_phases':bool(ordered and times[0] <= first_phase and times[-1] >= last_phase),
            'phase_coverage':coverage,
            'limitations':['Clock offset was not independently calibrated.',
                           'Sampling can miss brief transitions; no electrical HPD or fresh DDC measurement.',
                           'The initial state observation is a baseline, not a disconnect.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('windows_log', type=Path)
    parser.add_argument('trial_report', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    result = json.dumps(analyze(args.windows_log,args.trial_report),indent=2)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(result,encoding='utf-8')
    else:
        print(result,end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
