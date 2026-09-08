import argparse
import contextlib
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import run_experiment


class HardwareBoundary(unittest.TestCase):
    def test_preview_does_not_connect(self):
        with patch.object(run_experiment.subprocess,'run') as run, contextlib.redirect_stdout(io.StringIO()) as output:
            status=run_experiment.main(['--host','my-kvm','--expected-hostname','my-kvm'])
        run.assert_not_called()
        self.assertEqual(status,0)
        self.assertIn('PREVIEW ONLY',output.getvalue())
        self.assertIn('StrictHostKeyChecking=yes',output.getvalue())
        self.assertIn('BatchMode=yes',output.getvalue())

    def test_remote_arguments_reject_shell_injection(self):
        for value in ['-oProxyCommand=bad','host;touch bad','$(id)','host\ncommand','root@host','host space']:
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                run_experiment.hostname(value)

    def test_scripts_require_explicit_execution_and_hardware_guards(self):
        for name in run_experiment.SCRIPTS.values():
            text=(ROOT/'experiments'/name).read_text(encoding='utf-8')
            gate=text.index('[ "$#" = 3 ] && [ "$3" = --execute ]')
            first_mutation=text.index('write8 0xff 0x04 0x5a')
            self.assertLess(gate,first_mutation)
            self.assertIn('[ "$(hostname)" = "$1" ]',text)
            self.assertIn('sleep 45; sh "$1/recover.sh"',text)
            self.assertIn('trap cleanup 0',text)


if __name__=='__main__':
    unittest.main()
