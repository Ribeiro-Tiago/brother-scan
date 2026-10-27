import sys
import yaml


def load_config(path):
    """Load and parse the YAML config file. Exits with a clear message on
    a missing file or menu rather than letting a raw traceback out."""
    try:
        with open(path) as configfile:
            # yaml.load() without a Loader was removed in PyYAML 5.1+;
            # safe_load is also just the right choice for untrusted config.
            config = yaml.safe_load(configfile) or {}
    except FileNotFoundError as e:
        print('Error: %s: %s' % (e.strerror, e.filename))
        sys.exit(1)
    except IsADirectoryError:
        # What a docker bind mount of a host file that doesn't exist gives you
        print('Error: config file %s is a directory - check the host path '
              'mounted there exists' % path)
        sys.exit(1)
    if not config.get('menu'):
        print('Error: no menu configured in %s' % path)
        sys.exit(1)
    return config


def flatten_menu(menu, func=None):
    """Walk config['menu'] to arbitrary depth and yield (func, user, entry)
    triples, same shape the old hardcoded two-level loop produced.

    A node is a *leaf* (an actual scan destination) if any of its values is
    not itself a dict - e.g. {'dir': '/tmp', 'resolution': 200}. A node
    whose values are all dicts is a grouping level and gets recursed into,
    so menu.file.User1 and menu.file.homeoffice.User1 both work; the
    grouping levels only exist to keep large configs organized, they never
    reach the scanner. The leaf's own key is still what gets matched
    against the USER field the scanner sends and advertised via SNMP, so
    two leaves anywhere in the tree sharing both a top-level func and a
    leaf key remain ambiguous - same constraint as the old two-level file.
    """
    for key, value in menu.items():
        if func is None:
            # top level: FILE, EMAIL, etc.
            yield from flatten_menu(value, func=key.upper())
            continue
        is_leaf = not value or any(not isinstance(v, dict) for v in value.values())
        if is_leaf:
            yield func, key, value
        else:
            yield from flatten_menu(value, func=func)
