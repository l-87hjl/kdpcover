#!/usr/bin/env python3
"""Build one trusted local cover with external private storage and no shell escape."""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

def outside_git(path):
    value = Path(path).resolve()
    for ancestor in (value, *value.parents):
        if (ancestor / '.git').exists():
            raise ValueError('Private paths must stay outside Git worktrees.')
    return value

def private_path(root, value):
    value = outside_git(value)
    if not value.is_relative_to(root):
        raise ValueError('Selected input/output is outside the private root.')
    return value

def validate_source(source, root):
    if source.suffix.lower() != '.tex': raise ValueError('Cover source must be a trusted .tex file.')
    text = source.read_text()
    if re.search(r'\\(?:write|openin|openout|read|input|include|directlua|special)\b', text):
        raise ValueError('Raw file/shell/executable helpers are outside the trusted cover subset.')
    matches = list(re.finditer(r'\\(?:putPicture|includegraphics)(?:\[[^]]*\])?\{([^{}]+)\}', text))
    matches += list(re.finditer(r'\\putSpine\[([^]]+)\]', text))
    for match in matches:
        target = match.group(1)
        if re.match(r'[a-z][a-z0-9+.-]*(?::|%3a)|[/\\]{2}', target, re.I):
            raise ValueError('Network/protocol graphics are disabled.')
        private_path(root, source.parent / target)
    pages = re.search(r'\bpages\s*=\s*(\d+)\b', text)
    if pages and int(pages.group(1)) < 24:
        raise ValueError('A private production-path cover needs at least 24 pages.')
    if not pages and not re.search(r'\bpdf\s*=', text):
        raise ValueError('Specify the actual interior pages= count or a local pdf= input.')
    for match in re.finditer(r'\bpdf\s*=\s*([^,\]\s]+)', text):
        pdf = private_path(root, source.parent / match.group(1))
        info = subprocess.check_output(['pdfinfo', str(pdf)], text=True)
        count = re.search(r'^Pages:\s+(\d+)', info, re.M)
        if not count or int(count.group(1)) < 24:
            raise ValueError('Interior PDF is below the production page minimum.')
    return text

def build(root, source, destination):
    root = outside_git(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    source = private_path(root, source)
    destination = private_path(root, destination)
    if destination.exists(): raise ValueError('Existing output preserved; choose a new versioned output path.')
    validate_source(source, root)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    log = ''
    with tempfile.TemporaryDirectory(prefix='.cover-build-', dir=root) as folder:
        work = Path(folder)
        for name in ['kdpcover.ins', 'kdpcover.dtx', 'kdpcover-signature.pdf',
                     'kdpcover-vol-1.pdf', 'kdpcover-vol-2.pdf', 'kdpcover-vol-3.pdf', 'kdpcover-vol-4.pdf']:
            shutil.copy2(REPO / name, work / name)
        # Only this fresh private cache may replace its generated class.
        ins = work / 'kdpcover.ins'
        ins.write_text(ins.read_text().replace('\\keepsilent', '\\keepsilent\n\\askforoverwritefalse', 1))
        env = {**os.environ, 'TEXINPUTS': str(work) + os.pathsep + str(source.parent) + os.pathsep,
               'TMPDIR': str(work), 'TMP': str(work), 'TEMP': str(work)}
        for input_file in [work / 'kdpcover.ins', source]:
            command = ['pdflatex', '-no-shell-escape', '-interaction=nonstopmode', '-halt-on-error',
                       '-output-directory', str(work), str(input_file)]
            result = subprocess.run(command, cwd=work if input_file.suffix == '.ins' else source.parent, env=env, text=True, capture_output=True)
            log += result.stdout + result.stderr
            destination.with_suffix('.build.log').write_text(log)
            destination.with_suffix('.build.log').chmod(0o600)
            if result.returncode or re.search(r'Overfull \\[hv]box|Missing character:', log):
                if destination.exists(): destination.unlink()
                raise ValueError('Cover validation failed; inspect the log in private output storage.')
        result_pdf = work / (source.stem + '.pdf')
        shutil.copyfile(result_pdf, destination)
        destination.chmod(0o600)
        record = {'source_commit': subprocess.check_output(['git', '-C', str(REPO), 'rev-parse', 'HEAD'], text=True).strip(),
                  'source_dirty': bool(subprocess.check_output(['git', '-C', str(REPO), 'status', '--porcelain'], text=True).strip()),
                  'class_source_sha256': hashlib.sha256((REPO / 'kdpcover.dtx').read_bytes()).hexdigest(),
                  'pdf_sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
                  'pdflatex': subprocess.check_output(['pdflatex', '--version'], text=True).splitlines()[0]}
        destination.with_suffix('.build.json').write_text(json.dumps(record, indent=2) + '\n')
        destination.with_suffix('.build.json').chmod(0o600)
    return destination

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-root', required=True, type=Path)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        destination = args.output or args.private_root / 'output' / (args.source.stem + '.pdf')
        build(args.private_root, args.source, destination)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print('Cover build stopped: ' + (str(error) if isinstance(error, ValueError) else 'local dependency/file error; details withheld.'))
        return 1
    print('Cover built in private storage. Review geometry/text and retain the exact build record.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
