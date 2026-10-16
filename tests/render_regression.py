#!/usr/bin/env python3
"""Synthetic cover regression: no network, qpdf, private assets or shell escape."""
import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
import fitz

REPO=Path(__file__).resolve().parents[1]

def run(output, engine, filename, expect_success=True):
    command=[engine,'-no-shell-escape','-interaction=nonstopmode','-halt-on-error',filename]
    cache=output/'.texmf-cache';cache.mkdir(exist_ok=True,mode=0o700)
    env={**os.environ,'TEXMFCACHE':str(cache),'TEXMFVAR':str(cache),'TEXMFCONFIG':str(cache)}
    p=subprocess.run(command,cwd=output,env=env,text=True,capture_output=True)
    (output/(Path(filename).stem+'-'+engine+'.console.log')).write_text(p.stdout+p.stderr)
    if expect_success: assert p.returncode==0, filename+': engine failed; inspect local log'
    else: assert p.returncode!=0, filename+': expected rejection did not occur'
    return {'argv':command,'exit':p.returncode}

def tex(options,title='Quiet Stars',back='A fictional harbour and its patient keeper.'):
    return r'\documentclass['+options+r"""]{kdpcover}
\begin{document}
\putSpine[synthetic-art.pdf]{Quiet Stars -- Ada Example}
\putTitle{"""+title+r"""}
\putAuthor{Ada Example}
\putTLDR{A synthetic cover regression with no private content.}
\putBack{"""+back+r"""}
\putPicture{synthetic-art.pdf}
\putVersion{Synthetic test only}
\end{document}
"""

def measure(pdf,expected_width,spine_expected=True):
    doc=fitz.open(pdf);assert len(doc)==1;page=doc[0]
    assert abs(page.rect.width/72-expected_width)<.001 and abs(page.rect.height/72-9.25)<.001
    lines=[{'text':''.join(s['text'] for s in l['spans']),'bbox':l['bbox'],'dir':tuple(l['dir'])} for b in page.get_text('dict')['blocks'] for l in b.get('lines',[])]
    spine=[l for l in lines if l['dir']!=(1.0,0.0)]
    assert bool(spine)==spine_expected,'spine suppression/placement mismatch'
    for block in page.get_text('dict')['blocks']:
        for line in block.get('lines',[]):
            if tuple(line['dir'])!=(1.0,0.0):assert all(s['color']==0xffffff for s in line['spans']),'spine text is not visible white ink on black band'
    front=[];group='title'
    for line in lines:
        if line['bbox'][0]<=page.rect.width/2+25 or line['dir']!=(1.0,0.0):continue
        if line['text'].startswith('by '):group='author'
        elif line['text'].startswith('TL;DR'):group='blurb'
        elif line['text'].startswith('Synthetic test'):group='version'
        front.append((group,line))
    for i,(ga,a) in enumerate(front):
        for gb,b in front[i+1:]:
            if ga!=gb:assert (fitz.Rect(a['bbox'])&fitz.Rect(b['bbox'])).is_empty,'cover text collision between layout boxes'
    for line in spine:
        assert line['bbox'][0]>=441+4.5-.25 and line['bbox'][2]<=page.rect.width-441-4.5+.25,'spine text outside safe physical spine'
    # Suggested 2 x 1.2 barcode rectangle, .25 in inside back trim/spine.
    barcode=fitz.Rect(441-18-144,666-9-18-86.4,441-18,666-9-18)
    for line in lines:
        assert (fitz.Rect(line['bbox'])&barcode).is_empty,'text intrudes into barcode reservation'
    fonts=subprocess.check_output(['pdffonts',str(pdf)],text=True)
    for line in fonts.splitlines()[2:]:assert re.search(r'\byes\s+yes\s+yes\b',line)
    return {'media_inches':[page.rect.width/72,page.rect.height/72],'spine_text':bool(spine),'fonts':fonts}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();output=args.output.resolve()
    for parent in [output,*output.parents]:assert not (parent/'.git').exists(),'outputs must stay outside Git'
    assert not output.exists() or not any(output.iterdir()),'choose an empty synthetic output directory'
    output.mkdir(parents=True,exist_ok=True,mode=0o700)
    for name in ('kdpcover.ins','kdpcover.dtx'):shutil.copy2(REPO/name,output/name)
    commands=[run(output,'pdflatex','kdpcover.ins')]
    art=fitz.open();page=art.new_page(width=216,height=216);page.draw_circle((108,108),70,color=(0,0,0),width=2);page.draw_line((20,20),(196,196),color=(.3,.3,.3));art.save(output/'synthetic-art.pdf');art.close()
    results={}
    for name,options,width,spine in [('cream-200','pages=200,paper=cream,6x9',12.75,True),('white-200','pages=200,paper=white,6x9',12.7004,True),('cream-60','pages=60,paper=cream,6x9',12.4,False)]:
        (output/(name+'.tex')).write_text(tex(options));commands.append(run(output,'pdflatex',name+'.tex'));results[name]=measure(output/(name+'.pdf'),width,spine)
    (output/'fit-title.tex').write_text(tex('pages=200,paper=cream,6x9','The Harbour of Quiet Stars'))
    commands.append(run(output,'pdflatex','fit-title.tex'));results['fit-title']=measure(output/'fit-title.pdf',12.75,True)
    fitted=fitz.open(output/'fit-title.pdf');assert max(s['size'] for b in fitted[0].get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans'])<31
    title='The Harbour of Quiet Stars and the Exceptionally Long Journey Beyond the Northern Observatory'
    (output/'long-title.tex').write_text(tex('pages=200,paper=cream,6x9',title))
    p=subprocess.run(['pdflatex','-no-shell-escape','-interaction=nonstopmode','-halt-on-error','long-title.tex'],cwd=output,text=True,capture_output=True)
    (output/'long-title.console.log').write_text(p.stdout+p.stderr)
    if p.returncode==0:results['long-title']=measure(output/'long-title.pdf',12.75,True)
    else:
        assert 'Title does not fit' in p.stdout
        results['long-title']={'rejected_before_collision':True}
    # Too much content must fail clearly; it must not silently overlap.
    (output/'oversized-title.tex').write_text(tex('pages=200,6x9','An exceptionally long synthetic heading '*35))
    commands.append(run(output,'pdflatex','oversized-title.tex',False))
    for name,opts in [('zero','pages=0'),('negative','pages=-1'),('fraction','pages=20.5'),('cream-over-limit','pages=777,paper=cream'),('white-over-limit','pages=829,paper=white'),('unknown-stock','pages=200,paper=unknown')]:
        (output/(name+'.tex')).write_text(tex(opts));commands.append(run(output,'pdflatex',name+'.tex',False))
    # Every direct-class text helper must reject an unbreakable token at its minimum.
    for helper in ['putTitle','putAuthor','putTLDR','putBack']:
        name='wide-'+helper
        (output/(name+'.tex')).write_text(r'\documentclass[pages=200,6x9]{kdpcover}\begin{document}'+chr(92)+helper+'{'+'N'*120+r'}\end{document}')
        commands.append(run(output,'pdflatex',name+'.tex',False))
        assert 'does not fit its safe layout box' in (output/(name+'-pdflatex.console.log')).read_text()
    for helper in ['putTitle','putAuthor','putTLDR','putBack']:
        for label, separator in [('paragraph',r'\par '),('line',r'\\[2pt] ')]:
            name='wide-'+helper+'-'+label
            (output/(name+'.tex')).write_text(r'\documentclass[pages=200,6x9]{kdpcover}\begin{document}'+chr(92)+helper+'{'+'N'*120+separator+r'Short final line}\end{document}')
            commands.append(run(output,'pdflatex',name+'.tex',False))
            assert 'does not fit its safe layout box' in (output/(name+'-pdflatex.console.log')).read_text()
    (output/'wide-original-title.tex').write_text(tex('pages=200,6x9','N'*52))
    commands.append(run(output,'pdflatex','wide-original-title.tex',False))
    (output/'fit-unbroken.tex').write_text(tex('pages=200,6x9','N'*30))
    commands.append(run(output,'pdflatex','fit-unbroken.tex'))
    results['fit-unbroken']=measure(output/'fit-unbroken.pdf',12.75,True)
    fitted=fitz.open(output/'fit-unbroken.pdf')
    assert 'N'*30 in fitted[0].get_text(),'fitted unbreakable title lost text'
    # Synthetic 200-page interior proves shell-free page counting on installed engines.
    doc=fitz.open()
    for _ in range(200):doc.new_page(width=432,height=648)
    doc.save(output/'synthetic-interior.pdf');doc.close()
    for engine in ('pdflatex','xelatex','lualatex'):
        if not shutil.which(engine):continue
        name='count-'+engine;(output/(name+'.tex')).write_text(tex('pdf=synthetic-interior.pdf,paper=white,6x9'))
        commands.append(run(output,engine,name+'.tex'));results[name]=measure(output/(name+'.pdf'),12.7004,True)
    # Guarded production-path invocation also uses only synthetic external inputs.
    (output/'guarded.tex').write_text(tex('pages=200,paper=white,6x9'))
    p=subprocess.run(['python3',str(REPO/'scripts/cover_build.py'),'--private-root',str(output),'--source',str(output/'guarded.tex'),'--output',str(output/'guarded.pdf')],text=True,capture_output=True)
    (output/'guarded.console.log').write_text(p.stdout+p.stderr);assert p.returncode==0,'guarded cover build failed'
    results['guarded']=measure(output/'guarded.pdf',12.7004,True)
    # Extensionless graphics compile from the canonical checked resource.
    (output/'extensionless.tex').write_text(tex('pages=200,paper=cream,6x9').replace('synthetic-art.pdf','synthetic-art'))
    p=subprocess.run(['python3',str(REPO/'scripts/cover_build.py'),'--private-root',str(output),'--source',str(output/'extensionless.tex'),'--output',str(output/'extensionless.pdf')],text=True,capture_output=True)
    assert p.returncode==0,'safe extensionless resource failed'
    results['extensionless']=measure(output/'extensionless.pdf',12.75,True)
    assert json.loads((output/'extensionless.build.json').read_text())['effective_pages']==200
    # A source that changes the effective count after validation fails closed.
    (output/'changed-count.tex').write_text(tex('pages=200,6x9').replace(r'\begin{document}',r'\makeatletter\kdp@pages=10\makeatother\begin{document}'))
    p=subprocess.run(['python3',str(REPO/'scripts/cover_build.py'),'--private-root',str(output),'--source',str(output/'changed-count.tex'),'--output',str(output/'changed-count.pdf')],text=True,capture_output=True)
    assert p.returncode!=0 and not (output/'changed-count.pdf').exists(),'effective count mismatch passed'
    (output/'render-regression.json').write_text(json.dumps({'results':results,'commands':commands},indent=2)+'\n')
    print(json.dumps({k:{kk:vv for kk,vv in v.items() if kk!='fonts'} for k,v in results.items()},indent=2));print('Synthetic cover rendered regression passed.')

if __name__=='__main__':main()
