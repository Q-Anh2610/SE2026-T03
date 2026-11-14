"""Run from repo root. Local evidence; never performs any remote Git write."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/reports/23001889-vt011'
SOURCE = ROOT / 'backend/app/ingestion/export_metadata.py'
API = ROOT / 'backend/tests/vt011/api.py'
TESTS = 'backend/tests/vt011'
os.chdir(ROOT)
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONPATH'] = os.pathsep.join([str(ROOT/'backend'),str(ROOT/'backend/tests')])


def execute(filename, args, expected=0):
    result = subprocess.run([sys.executable, *args], stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding='utf-8')
    (OUT/filename).write_text(result.stdout,encoding='utf-8')
    if result.returncode != expected:
        raise RuntimeError(f'{filename}: exit={result.returncode}, expected={expected}; inspect log')
    return result.stdout


# Tái lập red ở cùng môi trường cuối; không dùng import error làm evidence.
api_bytes=API.read_bytes()
try:
    API.write_bytes((OUT/'api.red.txt').read_bytes())
    red=execute('red-reproduced.txt',['-m','pytest',TESTS+'/test_api.py::test_t01_download_contract','-q'],1)
    assert 'assert 404 == 200' in red
finally:
    API.write_bytes(api_bytes)

execute('green.txt',['-m','pytest',TESTS,'-q'])
original=SOURCE.read_bytes()
guard='if source not in principal.sources:'
try:
    content=original.decode('utf-8')
    assert content.count(guard)==1
    SOURCE.write_text(content.replace(guard,'if False:  # deliberate bug: removed scope validation'),encoding='utf-8')
    (OUT/'mutation.diff').write_text('- '+guard+'\n+ if False:  # removed scope validation\n',encoding='utf-8')
    mutation=execute('mutation.txt',['-m','pytest',TESTS+'/test_api.py::test_t05_cannot_export_other_source','-q'],1)
    assert 'assert 200 == 403' in mutation
finally:
    SOURCE.write_bytes(original)

execute('coverage.txt',['-m','pytest',TESTS,'-q','--cov=app.ingestion.export_metadata',
    '--cov=vt011.api','--cov-branch','--cov-report=term-missing',
    '--cov-report=json:docs/reports/23001889-vt011/coverage.json'])
for i in range(3):
    execute(f'concurrency-repeat-{i+1}.txt',['-m','pytest',TESTS+'/test_api.py::test_t11_concurrent_scope_and_permission_isolation','-q'])
collection=subprocess.run([sys.executable,'-m','pytest',TESTS,'--collect-only','-q'],
    stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',check=True)
nodeids=['backend/'+line.strip() for line in collection.stdout.splitlines() if '::test_' in line]
execute('reverse-order.txt',['-m','pytest',*reversed(nodeids),'-q'])
execute('load-execution.txt',['-c',
    "import json;from pathlib import Path;from vt011.load import run_load;"
    "r=run_load();Path('docs/reports/23001889-vt011/load.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');"
    "print('Load completed; raw results saved to load.json')"])
load=json.loads((OUT/'load.json').read_text(encoding='utf-8'))
assert load['errors']==0
execute('environment.txt',['-m','pip','freeze'])
publication_path=OUT/'PUBLICATION.json'
publication=json.loads(publication_path.read_text(encoding='utf-8')) if publication_path.exists() else {}
integrity={
    'baseline':'63122a3a05a920a847793253a4527a871d5aa6e8',
    'source_sha256_restored':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    'original_source_sha256':hashlib.sha256(original).hexdigest(),
    'mutation_killed':True,'red_correct_reason':True,
    'github_policy':'Issue112 clean branch publication authorized; no PR/merge; mutation local only',
    'branch_or_pr':publication.get('pr_url'),'local_commits':publication.get('local_mutation_commits',[]),
}
assert integrity['source_sha256_restored']==integrity['original_source_sha256']
(OUT/'integrity.json').write_text(json.dumps(integrity,indent=2),encoding='utf-8')
print('Local experiments complete. No remote Git write performed by this script.')
