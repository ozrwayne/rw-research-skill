#!/usr/bin/env python3
"""Validate packaged skill contracts, not model behavior or scientific truth."""
from __future__ import annotations
import argparse
import ast
import json
import re
from pathlib import Path

RESOURCE = re.compile(r'`((?:references|assets|scripts|agents|tests)/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+)`')

def nonempty(value):
    return isinstance(value, str) and bool(value.strip())

def parse_json(text):
    def reject_constant(value):
        raise ValueError(f'non-finite JSON constant: {value}')
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError(f'duplicate JSON key: {key}')
            result[key]=value
        return result
    value=json.loads(text, parse_constant=reject_constant, object_pairs_hook=pairs)
    json.dumps(value,allow_nan=False)
    return value

def read_json(path):
    return parse_json(path.read_text(encoding='utf-8'))

def validate_skill(root: Path) -> list[str]:
    failures=[]
    def error(message):failures.append(f'{root.name}: {message}')
    try:
        text=(root/'SKILL.md').read_text(encoding='utf-8')
        front=re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)',text,re.S)
        if not front:
            error('missing YAML frontmatter')
        else:
            keys=re.findall(r'^([A-Za-z_][A-Za-z0-9_-]*):',front[1],re.M)
            if len(keys)!=len(set(keys)):error('duplicate frontmatter key')
            name=re.search(r'^name:\s*([^\r\n]+)',front[1],re.M)
            if not name or name[1].strip().strip('\'"')!=root.name:error('frontmatter name differs from directory')
            if not re.search(r'^description:\s*\S',front[1],re.M):error('missing description')
        refs=root/'references'
        for required in ('atoms.jsonl','behavior-tests.json','axioms.md','acceptance.md','source-map.md'):
            if not (refs/required).is_file():error(f'missing references/{required}')
        if failures:return failures
        atoms=[]
        for number,line in enumerate((refs/'atoms.jsonl').read_text(encoding='utf-8').splitlines(),1):
            if not line.strip():continue
            try:
                row=parse_json(line)
                if not isinstance(row,dict) or any(not nonempty(row.get(key)) for key in ('id','knowledge','source')):
                    error(f'atoms.jsonl:{number} requires non-empty id, knowledge and source')
                else:atoms.append(row)
            except ValueError as exc:error(f'atoms.jsonl:{number}: {exc}')
        ids=[row['id'] for row in atoms]
        if len(ids)!=len(set(ids)):error('duplicate knowledge atom id')
        known=set(ids)
        for line in (refs/'axioms.md').read_text(encoding='utf-8').splitlines():
            if '来源原子' in line:
                for identifier in re.findall(r'`([^`]+)`',line):
                    if identifier not in known:error(f'axiom references missing atom: {identifier}')
        contracts=read_json(refs/'behavior-tests.json')
        if not isinstance(contracts,list) or not contracts:
            error('behavior contracts must be a non-empty array')
        else:
            contract_ids=set()
            for index,row in enumerate(contracts):
                if not isinstance(row,dict) or not nonempty(row.get('id')) or not nonempty(row.get('prompt')):
                    error(f'behavior contract {index}: id and prompt required');continue
                if row['id'] in contract_ids:error(f'duplicate behavior contract id: {row["id"]}')
                contract_ids.add(row['id'])
                if 'expect' in row:
                    if not isinstance(row['expect'],(list,dict)) or not row['expect']:error(f'{row["id"]}: empty or malformed expect')
                else:
                    for key in ('must_do','must_not','expected_next'):
                        value=row.get(key)
                        if not isinstance(value,list) or any(not isinstance(item,str) for item in value):error(f'{row["id"]}: {key} must be an array of strings')
                    if not row.get('must_do'):error(f'{row["id"]}: must_do must not be empty')
        for path in sorted(root.rglob('*')):
            if path.is_symlink():error(f'symlink not portable: {path.relative_to(root)}');continue
            if not path.is_file() or '__pycache__' in path.parts:continue
            if path.suffix=='.json':read_json(path)
            elif path.suffix=='.py':ast.parse(path.read_text(encoding='utf-8'),filename=str(path))
            elif path.suffix=='.md' and path.parent.name != 'agents':
                for relative in RESOURCE.findall(path.read_text(encoding='utf-8')):
                    target=root/relative
                    if '..' in Path(relative).parts or not target.is_file():error(f'{path.relative_to(root)} references missing resource: {relative}')
    except (OSError,ValueError,TypeError,SyntaxError) as exc:error(f'malformed or unreadable contract: {exc}')
    return failures

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skills-root',type=Path,default=Path(__file__).resolve().parents[1]/'skills')
    args=parser.parse_args()
    failures=[];skills=[]
    if not args.skills_root.is_dir():failures.append('skills root missing')
    else:
        skills=sorted(path for path in args.skills_root.iterdir() if path.is_dir() and not path.name.startswith('.'))
        if not skills:failures.append('no skills found')
        for root in skills:failures.extend(validate_skill(root))
    print(json.dumps({'skills':len(skills),'scope':'static_contracts_only','failures':failures},ensure_ascii=False,indent=2))
    return int(bool(failures))
if __name__=='__main__':raise SystemExit(main())
