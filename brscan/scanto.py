import subprocess
import os
import time
import datetime
import wand.image
import glob


class ScanError(Exception):
    """Raised whenever the scanner hardware/driver doesn't give us back a
    usable image - paper jam, ADF emptied mid-run, cable pulled, etc.
    Callers are expected to catch this per-job, not let it kill the daemon.
    """


def pnmtopdf(pnmfile, pdffile, resolution=None):
    with wand.image.Image(filename=pnmfile, resolution=resolution) as pnm:
        with pnm.convert('pdf') as pdf:
            pdf.save(filename=pdffile)
    os.remove(pnmfile)


scan_options = {
    'device': '--device-name',
    'resolution': '--resolution',
    'mode': '--mode',
    'source': '--source',
    'brightness': '--brightness',
    'contrast': '--contrast',
    'width': '-x',
    'height': '-y',
    'left': '-l',
    'top': '-t',
}


def add_scan_options(cmd, options):
    for name, arg in scan_options.items():
        if name in options:
            cmd += [arg, str(options[name])]
    return [str(c) for c in cmd]


def _run(cmd, **kwargs):
    print('# ' + ' '.join(cmd))
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        raise ScanError('%s exited with code %d' % (cmd[0], result.returncode))
    return result


def _merge_pages(pnmfiles, resolution, dst, now):
    """Convert every captured .pnm frame to its own pdf, then merge into
    one multi-page pdf. Used for both ADF batches and multi-shot flatbed
    scans, so a single code path handles "1 page" through "N pages"."""
    if not pnmfiles:
        raise ScanError('scan produced no output (interrupted before any '
                         'page was captured)')
    pdffiles = ['%s.pdf' % pnmfile[:-4] for pnmfile in pnmfiles]
    for pnmfile, pdffile in zip(pnmfiles, pdffiles):
        pnmtopdf(pnmfile, pdffile, resolution)

    outfile = os.path.join(dst, 'scan_%s.pdf' % now)
    if len(pdffiles) == 1:
        os.rename(pdffiles[0], outfile)
    else:
        _run(['pdfunite'] + pdffiles + [outfile])
        for f in pdffiles:
            os.remove(f)
    return outfile


def scanto(func, options):
    print('scanto %s %s' % (func, options))
    options = options.copy()
    dst = options.get('dir', '/tmp')

    os.makedirs(dst, exist_ok=True)
    now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    adf = options.pop('adf', False)
    # Fixed page count for flatbed multi-page scans (glass has no feeder,
    # so we can't detect "more paper" the way ADF does - this is a known
    # ceiling; a "press a key for another page" flow would need a second
    # UDP round-trip and is a bigger change than this bug/feature ask).
    pages = int(options.pop('pages', 1))
    pages_delay = float(options.pop('pages_delay', 3))
    resolution = options.get('resolution')

    if adf:
        cmd = add_scan_options(
            ['scanadf', '--output-file',
             os.path.join(dst, 'scan_%s_%%d.pnm' % now)],
            options)
        try:
            _run(cmd)
        finally:
            # scanadf may have written some frames before failing partway
            # through the feed - collect whatever exists either way so a
            # jam on page 3 of 5 still yields a 2-page pdf instead of
            # crashing the whole daemon and losing everything.
            pnmfiles = sorted(glob.glob(os.path.join(dst, 'scan_%s_*.pnm' % now)))
        pdffile = _merge_pages(pnmfiles, resolution, dst, now)
    else:
        pnmfiles = []
        for i in range(pages):
            if i > 0:
                time.sleep(pages_delay)
            cmd = add_scan_options(['scanimage'], options)
            pnmfile = os.path.join(dst, 'scan_%s_%d.pnm' % (now, i))
            with open(pnmfile, 'wb') as pnm:
                print('# ' + ' '.join(cmd))
                result = subprocess.run(cmd, stdout=pnm)
            if result.returncode != 0:
                os.remove(pnmfile)
                raise ScanError('scanimage exited with code %d on page %d'
                                 % (result.returncode, i + 1))
            pnmfiles.append(pnmfile)
        pdffile = _merge_pages(pnmfiles, resolution, dst, now)

    print('Wrote', pdffile)
    return pdffile
