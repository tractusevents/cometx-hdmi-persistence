"""Preview or explicitly execute a guarded direct-selector experiment over SSH.

Only two allowlisted scripts; no password-file or host-key enrollment feature.
SSH must already work with key authentication and a verified known_hosts entry.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = {'paused':'direct-selector-paused.sh', 'resumed':'direct-selector-resumed.sh'}


def hostname(value):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,252}',value):
        raise argparse.ArgumentTypeError('Use a DNS name, IPv4 address, or SSH alias; no shell metacharacters')
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',required=True,type=hostname,help='Preconfigured SSH alias or hostname')
    parser.add_argument('--expected-hostname',required=True,type=hostname,help='Exact output of hostname on this KVM')
    parser.add_argument('--profile',choices=('source-free','connected-b'),default='source-free')
    parser.add_argument('--experiment',choices=tuple(SCRIPTS),default='resumed')
    parser.add_argument('--ssh',default='ssh',help='OpenSSH executable or path')
    parser.add_argument('--log-dir',type=Path,default=ROOT/'runs')
    parser.add_argument('--execute',action='store_true',help='Actually connect and perform the experiment')
    args = parser.parse_args(argv)
    script = (ROOT/'experiments'/SCRIPTS[args.experiment]).read_bytes()
    digest = hashlib.sha256(script).hexdigest()
    remote = f'sh -s -- {args.expected_hostname} {args.profile} --execute'
    command = [args.ssh,'-o','StrictHostKeyChecking=yes','-o','BatchMode=yes',
               '-o','PreferredAuthentications=publickey','-o','ConnectTimeout=8',
               '-o','ConnectionAttempts=1','-o','ServerAliveInterval=10',
               '-o','ServerAliveCountMax=2','-l','root',args.host,remote]
    print('Script:',SCRIPTS[args.experiment], '\nSHA-256:',digest)
    print('Profile:',args.profile, '\nSSH command:',shlex.join(command))
    if not args.execute:
        print('PREVIEW ONLY: no connection or hardware change. Read docs/experiments.md before adding --execute.')
        return 0
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    timed_out = False
    try:
        completed = subprocess.run(command,input=script,capture_output=True,timeout=65,check=False)
        status,stdout,stderr = completed.returncode,completed.stdout,completed.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        status,stdout,stderr = None,exc.stdout or b'',exc.stderr or b''
    report = {'utc':stamp,'host':args.host,'expected_hostname':args.expected_hostname,
              'profile':args.profile,'experiment':args.experiment,'script_sha256':digest,
              'exit_status':status,'timed_out':timed_out,
              'stdout':stdout.decode('utf-8',errors='replace'),
              'stderr':stderr.decode('utf-8',errors='replace')}
    args.log_dir.mkdir(parents=True,exist_ok=True)
    destination = args.log_dir/(stamp+'-'+args.experiment+'.json')
    destination.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(report['stdout'],end='')
    print(report['stderr'],end='')
    print('Saved:',destination)
    if timed_out:
        print('SSH timed out. Independent recovery may run, but restoration has NOT been verified. Inspect the KVM before another test.')
        return 124
    return status


if __name__ == '__main__':
    raise SystemExit(main())
