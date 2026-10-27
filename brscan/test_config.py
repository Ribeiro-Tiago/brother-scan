"""Minimal assert-based self-check. Run with: python3 -m brscan.test_config"""
import os
import tempfile

from brscan.config import load_config, flatten_menu


def _exits(path):
    try:
        load_config(path)
    except SystemExit:
        return True
    return False


def main():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'config.yaml')
        with open(path, 'w') as f:
            f.write('menu:\n'
                    '  file:\n'
                    '    User1: {dir: /tmp/a, resolution: 200}\n'
                    '    home:\n'
                    '      User2: {dir: /tmp/b}\n'
                    '  email:\n'
                    '    User1: {adf: true}\n')
        config = load_config(path)
        assert sorted(flatten_menu(config['menu'])) == [
            ('EMAIL', 'User1', {'adf': True}),
            ('FILE', 'User1', {'dir': '/tmp/a', 'resolution': 200}),
            ('FILE', 'User2', {'dir': '/tmp/b'}),
        ], config

        # Missing file, a directory (bad docker mount) and no menu all exit
        assert _exits(os.path.join(d, 'missing.yaml'))
        assert _exits(d)
        with open(path, 'w') as f:
            f.write('other: 1\n')
        assert _exits(path)

    print('OK')


if __name__ == '__main__':
    main()
