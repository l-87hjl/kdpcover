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


def strip_comments(text):
    """TeX comments consume the remainder of their line, including the newline."""
    result = []
    for line in text.splitlines(keepends=True):
        for index, char in enumerate(line):
            if char != '%': continue
            slashes = 0
            for previous in reversed(line[:index]):
                if previous != '\\': break
                slashes += 1
            if slashes % 2 == 0:
                line = line[:index]
                break
        result.append(line)
    return ''.join(result)


def resource_file(root, source_dir, target, pdf_only=False):
    if re.match(r'[a-z][a-z0-9+.-]*(?::|%3a)|[/\\]{2}', target, re.I):
        raise ValueError('Network/protocol resources are disabled.')
    if any(c in target for c in r'\{}%#^~'):
        raise ValueError('Resource indirection or special TeX path syntax is unsupported.')
    value = source_dir / target
    extensions = ('.pdf',) if pdf_only else ('.pdf', '.png', '.jpg', '.jpeg')
    if value.suffix:
        candidates = [value] if value.suffix.lower() in extensions else []
    else:
        candidates = [value.with_suffix(ext) for ext in extensions if value.with_suffix(ext).exists() or value.with_suffix(ext).is_symlink()]
    if len(candidates) != 1:
        raise ValueError('Resource must resolve to one existing supported file; use an explicit extension.')
    actual = private_path(root, candidates[0])
    if not actual.is_file(): raise ValueError('Resource must be an existing local file.')
    if any(c in str(actual) for c in r'\{}%#^~'):
        raise ValueError('Selected resource path is unsupported by the trusted TeX subset.')
    return actual


def prepare_source(source, root):
    if source.suffix.lower() != '.tex': raise ValueError('Cover source must be a trusted .tex file.')
    text = strip_comments(source.read_text())
    if re.search(r'\\(?:write|openin|openout|read|input|include|directlua|special|PassOptionsToClass|PassOptionsToPackage)\b', text):
        raise ValueError('Raw file/shell/executable helpers are outside the trusted cover subset.')
    declarations = list(re.finditer(r'\\documentclass\b', text))
    match = re.match(r'\s*\\documentclass\s*(?:\[([^\[\]]*)\])?\s*\{kdpcover\}', text)
    if len(declarations) != 1 or not match:
        raise ValueError('Use one literal kdpcover documentclass at the start of the source.')
    options = [item.strip() for item in (match.group(1) or '').split(',') if item.strip()]
    keys = {}
    for index, option in enumerate(options):
        key, separator, value = option.partition('=')
        key = key.strip()
        if key in keys: raise ValueError('Duplicate class options are unsupported.')
        keys[key] = (index, value.strip() if separator else None)
    if ('pages' in keys) == ('pdf' in keys):
        raise ValueError('Specify exactly one active pages= count or local pdf= input.')
    if 'pages' in keys:
        raw = keys['pages'][1]
        if not raw or not re.fullmatch(r'[0-9]+', raw): raise ValueError('Active pages= must be a literal positive integer.')
        pages = int(raw)
    else:
        index, raw = keys['pdf']
        if not raw: raise ValueError('Active pdf= needs a local PDF path.')
        pdf = resource_file(root, source.parent, raw, pdf_only=True)
        info = subprocess.check_output(['pdfinfo', str(pdf)], text=True)
        count = re.search(r'^Pages:\s+(\d+)', info, re.M)
        if not count: raise ValueError('Cannot verify the selected interior page count.')
        pages = int(count.group(1))
        options[index] = 'pdf=' + str(pdf)
    if pages < 24: raise ValueError('A private production-path cover needs at least 24 pages.')
    text = '\\documentclass[' + ','.join(options) + ']{kdpcover}' + text[match.end():]
    patterns = [r'\\(?:putPicture|includegraphics)(?:\[[^]]*\])?\{([^{}]+)\}', r'\\putSpine\[([^]]+)\]']
    for pattern in patterns:
        def replace(match):
            actual = resource_file(root, source.parent, match.group(1))
            a, z = match.span(1)
            return match.group(0)[:a-match.start()] + str(actual) + match.group(0)[z-match.start():]
        text = re.sub(pattern, replace, text)
    return text, pages


def validate_source(source, root):
    return prepare_source(source, root)[0]


def reserve_artifacts(root, destination):
    artifacts = {}
    try:
        for name, path in [('output', destination), ('log', destination.with_suffix('.build.log')), ('record', destination.with_suffix('.build.json'))]:
            if os.path.lexists(path): raise ValueError('Existing companion preserved.')
            path = private_path(root, path)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            artifacts[name] = (path, fd, os.fstat(fd))
        return artifacts
    except Exception:
        close_artifacts(artifacts, False, keep_log=False)
        raise ValueError('Existing output/companion preserved or path outside private storage.') from None


def write_artifact(artifact, data):
    fd = artifact[1]
    if isinstance(data, str): data = data.encode()
    os.ftruncate(fd, 0)
    os.lseek(fd, 0, os.SEEK_SET)
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view):]


def close_artifacts(artifacts, success, keep_log=True):
    for name, (path, fd, owned) in artifacts.items():
        os.close(fd)
        if not success and not (keep_log and name == 'log'):
            try:
                current = path.lstat()
                if (current.st_dev, current.st_ino) == (owned.st_dev, owned.st_ino): path.unlink()
            except FileNotFoundError:
                pass


def build(root, source, destination):
    root = outside_git(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    source = private_path(root, source)
    if os.path.lexists(destination): raise ValueError('Existing output preserved; choose a new versioned output path.')
    destination = private_path(root, destination)
    if destination.exists(): raise ValueError('Existing output preserved; choose a new versioned output path.')
    validated, expected_pages = prepare_source(source, root)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    artifacts = reserve_artifacts(root, destination)
    success = False
    try:
        log = ''
        with tempfile.TemporaryDirectory(prefix='.cover-build-', dir=root) as folder:
            work = Path(folder)
            for name in ['kdpcover.ins', 'kdpcover.dtx', 'kdpcover-signature.pdf',
                         'kdpcover-vol-1.pdf', 'kdpcover-vol-2.pdf', 'kdpcover-vol-3.pdf', 'kdpcover-vol-4.pdf']:
                shutil.copy2(REPO / name, work / name)
            ins = work / 'kdpcover.ins'
            ins.write_text(ins.read_text().replace('\\keepsilent', '\\keepsilent\n\\askforoverwritefalse', 1))
            # Compile the checked copy: canonical concrete resources, active options, no source-directory search.
            checked = work / 'validated-cover.tex'
            checked.write_text(validated)
            env = {**os.environ, 'TEXINPUTS': str(work) + os.pathsep,
                   'TMPDIR': str(work), 'TMP': str(work), 'TEMP': str(work)}
            for input_file in [ins, checked]:
                command = ['pdflatex', '-no-shell-escape', '-interaction=nonstopmode', '-halt-on-error',
                           '-output-directory', str(work), str(input_file)]
                result = subprocess.run(command, cwd=work, env=env, text=True, capture_output=True)
                log += result.stdout + result.stderr
                write_artifact(artifacts['log'], log)
                if result.returncode or re.search(r'Overfull \\[hv]box|Missing character:', log):
                    raise ValueError('Cover validation failed; inspect the log in private output storage.')
            effective = re.findall(r'^KDP-COVER-PAGES=(\d+)\s*$', log, re.M)
            if effective != [str(expected_pages)]:
                raise ValueError('Effective rendered page count differs from the validated active option.')
            result_pdf = work / 'validated-cover.pdf'
            write_artifact(artifacts['output'], result_pdf.read_bytes())
            record = {'source_commit': subprocess.check_output(['git', '-C', str(REPO), 'rev-parse', 'HEAD'], text=True).strip(),
                      'source_dirty': bool(subprocess.check_output(['git', '-C', str(REPO), 'status', '--porcelain'], text=True).strip()),
                      'effective_pages': expected_pages,
                      'class_source_sha256': hashlib.sha256((REPO / 'kdpcover.dtx').read_bytes()).hexdigest(),
                      'pdf_sha256': hashlib.sha256(result_pdf.read_bytes()).hexdigest(),
                      'pdflatex': subprocess.check_output(['pdflatex', '--version'], text=True).splitlines()[0]}
            write_artifact(artifacts['record'], json.dumps(record, indent=2) + '\n')
        success = True
        return destination
    finally:
        close_artifacts(artifacts, success)

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
