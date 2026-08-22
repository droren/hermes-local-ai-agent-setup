#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, os
from datetime import datetime, timezone
from pathlib import Path

EXTS={'.safetensors','.gguf','.ckpt','.pth','.pt'}

def gb(n:int)->float:return round(n/1024**3,3)

def dsize(root:Path)->int:
    total=0
    for base,_,files in os.walk(root):
        for name in files:
            try: total+=(Path(base)/name).stat().st_size
            except OSError: pass
    return total

def ollama(root:Path):
    out=[]; manifests=root/'manifests'; blobs=root/'blobs'
    if not manifests.exists(): return out
    for mf in manifests.rglob('*'):
        if not mf.is_file(): continue
        try:
            rel=mf.relative_to(manifests); p=rel.parts
            if len(p)<4: continue
            registry,namespace=p[0],p[1]; tag=p[-1]; model='/'.join(p[2:-1])
            name=f'{namespace}/{model}:{tag}' if namespace!='library' else f'{model}:{tag}'
            data=json.loads(mf.read_text()); layers=data.get('layers',[]); cfg=data.get('config',{})
            refs=[x.get('digest') for x in [cfg,*layers] if x.get('digest')]
            missing=[d for d in refs if not (blobs/d.replace(':','-')).exists()] if blobs.exists() else refs
            size=sum(int(x.get('size',0) or 0) for x in [cfg,*layers])
            out.append({'id':f'ollama:{name}','name':name,'source':'ollama','state':'cold_available' if not missing else 'available_incomplete','library_path':str(mf),'declared_size_gb':gb(size),'missing_blob_count':len(missing),'runtime_hints':['ollama'],'requires_local_staging':True})
        except Exception as e:
            out.append({'id':f'ollama:{mf}','name':mf.name,'source':'ollama','state':'inventory_error','library_path':str(mf),'error':str(e)})
    return out

def hf(root:Path):
    out=[]; hub=root/'hub' if (root/'hub').exists() else root
    if not hub.exists(): return out
    for md in sorted(hub.glob('models--*')):
        if not md.is_dir(): continue
        repo=md.name[len('models--'):].replace('--','/')
        snaps=md/'snapshots'; ids=[p.name for p in snaps.iterdir() if p.is_dir()] if snaps.exists() else []
        size=dsize(md); hints=['transformers']
        if 'mlx' in repo.lower(): hints.insert(0,'mlx')
        out.append({'id':f'huggingface:{repo}','name':repo,'source':'huggingface','state':'cold_available' if ids and size else 'available_incomplete','library_path':str(md),'size_gb':gb(size),'snapshots':ids,'runtime_hints':hints,'requires_local_staging':True})
    return out

def generic(root:Path,source:str):
    out=[]
    if not root.exists(): return out
    for p in root.rglob('*'):
        if not p.is_file() or p.suffix.lower() not in EXTS or '/.cache/' in str(p): continue
        try:
            out.append({'id':f'{source}:{p.relative_to(root)}','name':p.name,'source':source,'state':'cold_available','library_path':str(p),'size_gb':gb(p.stat().st_size),'runtime_hints':[source],'requires_local_staging':True})
        except OSError: pass
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',default='/Volumes/Shared_ModelDrive/ModelDrive'); ap.add_argument('--include-comfyui',action='store_true'); ap.add_argument('--output-dir',default='artifacts/inventory'); a=ap.parse_args()
    base=Path(a.root).expanduser(); lib=base/'library' if (base/'library').exists() else base
    roots={'ollama':lib/'ollama','huggingface':lib/'huggingface','mlx':lib/'mlx','gguf':lib/'gguf','safetensors':lib/'safetensors','comfyui':lib/'comfyui'}
    models=[]
    models+=ollama(roots['ollama']); models+=hf(roots['huggingface']); models+=generic(roots['mlx'],'mlx'); models+=generic(roots['gguf'],'gguf'); models+=generic(roots['safetensors'],'safetensors')
    if a.include_comfyui: models+=generic(roots['comfyui'],'comfyui')
    dedup={m['id']:m for m in models}; models=sorted(dedup.values(),key=lambda x:(x['source'],x['name']))
    bys={}; byt={}
    for m in models: bys[m['source']]=bys.get(m['source'],0)+1; byt[m['state']]=byt.get(m['state'],0)+1
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    payload={'schema_version':2,'captured_at_utc':stamp,'inventory_kind':'cold_model_library','execution_policy':'stage_to_local_ssd_before_activation','root':str(base),'library_root':str(lib),'discovered_roots':{k:{'path':str(v),'exists':v.exists()} for k,v in roots.items()},'summary':{'total':len(models),'by_source':bys,'by_state':byt},'models':models}
    outdir=Path(a.output_dir); outdir.mkdir(parents=True,exist_ok=True); out=outdir/f'model-library-v2-{stamp}.json'; out.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n'); print(out)

if __name__=='__main__': main()
