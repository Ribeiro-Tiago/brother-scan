"""Minimal assert-based self-check. Run with: python3 test_scanto.py
No pytest/fixtures - mocks the two subprocess calls (scanimage/pdfunite)
so it runs without real scanner hardware or driver installed."""
import os
import tempfile
from unittest import mock

from brscan.scanto import scanto, ScanError

PNM_1PX = b'P5\n1 1\n255\n\xff'


def _ok(cmd, stdout=None, **kw):
    if stdout is not None:
        stdout.write(PNM_1PX)
    return mock.Mock(returncode=0)


def _fail(cmd, stdout=None, **kw):
    return mock.Mock(returncode=1)


def main():
    with tempfile.TemporaryDirectory() as d:
        with mock.patch('subprocess.run', side_effect=_ok):
            out = scanto('FILE', {'dir': d, 'resolution': 100})
        assert os.path.exists(out)

        with mock.patch('subprocess.run', side_effect=_ok), \
             mock.patch('time.sleep'):
            out = scanto('FILE', {'dir': d, 'resolution': 100, 'pages': 3})
        assert os.path.exists(out)

        with mock.patch('subprocess.run', side_effect=_fail):
            try:
                scanto('FILE', {'dir': d, 'resolution': 100})
                assert False, 'expected ScanError'
            except ScanError:
                pass
        assert not [f for f in os.listdir(d) if f.endswith('.pnm')]

    print('OK')


if __name__ == '__main__':
    main()
