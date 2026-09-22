"""Synthetic, offline regressions for search contracts and failed API responses."""
import copy
import json
import os
import sys
import tempfile
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name, ROOT/'scripts'/f'{name}.py')
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
SEARCH=load('search_strategy'); IMPORTER=load('vocabulary_import')
def strategy():
    return {'question':'Synthetic question','concepts':[{'id':'a','free_text':['first concept']},{'id':'b','headings':{'mesh':[{'label':'second concept','status':'candidate'}]}}]}

class AuditRegressionTests(unittest.TestCase):
    def test_missing_concept_blocks_executable_query_and_preserves_exclusions(self):
        row=SEARCH.render_platform(strategy(),'pubmed')
        self.assertEqual(row['query'],''); self.assertEqual(row['missing_concepts'],['b'])
        self.assertTrue(row['excluded_unverified_headings']); self.assertEqual(row['status'],'incomplete')
    def test_rejected_heading_stays_excluded_in_draft_mode(self):
        value=strategy(); value['concepts'][1]['headings']['mesh'][0]['status']='rejected'
        row=SEARCH.render_platform(value,'pubmed',True)
        self.assertNotIn('second concept',row['draft_query']); self.assertEqual(row['query'],'')
    def test_verified_heading_without_provenance_is_rejected(self):
        value=strategy(); value['concepts'][1]['headings']['mesh'][0]['status']='verified_by_public_api'
        self.assertTrue(SEARCH.validate_strategy(value))
        with self.assertRaises(ValueError): SEARCH.render_platform(value,'pubmed')
    def test_string_false_is_not_boolean_false(self):
        value=strategy(); value['concepts'][1]['headings']['mesh'][0]['explode']='false'
        self.assertIn('explode must be boolean',';'.join(SEARCH.validate_strategy(value)))
    def test_wildcard_phrase_is_quoted_as_a_unit(self):
        self.assertEqual(SEARCH.render_free('pubmed','mobile app*'),'"mobile app*"[tiab]')
    def test_malformed_strategy_types_fail_closed(self):
        values=[None,[],{}, {'question':'x','concepts':'bad'}, {'question':'x','concepts':[None]},
                {'question':'x','concepts':[{'id':'a','headings':[]}]},
                {'question':'x','concepts':[{'id':'a','headings':{'mesh':[{'label':'x','status':[]}]}}]}]
        for value in values:
            with self.subTest(value=value): self.assertTrue(SEARCH.validate_strategy(value))
    def test_api_error_is_not_zero_hits(self):
        for data in ({'error':'limit'},{},{'esearchresult':{}},{'esearchresult':{'count':'-1'}},{'esearchresult':{'count':'0','errorlist':{'bad':'x'}}}):
            with self.subTest(data=data),patch.object(SEARCH,'http_json',return_value=data):
                with self.assertRaises(ValueError): SEARCH.pubmed_check('synthetic',1)
    def test_real_zero_hits_remains_valid(self):
        with patch.object(SEARCH,'http_json',return_value={'esearchresult':{'count':'0'}}):
            self.assertEqual(SEARCH.pubmed_check('synthetic',1)['count'],0)
    def test_unrelated_mesh_node_is_not_verified(self):
        responses=[[{'resource':'https://id.nlm.nih.gov/mesh/D001','label':'X'}],{}, {'@id':'https://id.nlm.nih.gov/mesh/D999'}]
        with patch.object(SEARCH,'http_json',side_effect=responses):
            with self.assertRaises(ValueError): SEARCH.mesh_lookup('X','exact',1,'current',1)
    def test_import_rejects_entire_batch_without_partial_merge(self):
        value=strategy(); original=copy.deepcopy(value)
        merged, report=IMPORTER.merge(value,[{'concept_id':'a','vocabulary':'mesh','label':'candidate'},None])
        self.assertEqual(merged,original); self.assertEqual(value,original)
        self.assertEqual(report['accepted'],0);self.assertEqual(report['rejected'],1)
    def test_verified_import_replaces_matching_candidate(self):
        value=strategy()
        record={'concept_id':'b','vocabulary':'mesh','label':'second concept','identifier':'D001','status':'user_confirmed','source':'synthetic','verified_at':'2026-09-19'}
        result,report=IMPORTER.merge(value,[record])
        self.assertEqual(len(result['concepts'][1]['headings']['mesh']),1);self.assertEqual(report['replaced'],1)
    def test_numeric_concept_id_fails_without_keyerror(self):
        _,report=IMPORTER.merge({'question':'x','concepts':[{'id':'1'}]},[{'concept_id':1,'vocabulary':'mesh','label':'x'}])
        self.assertEqual(report['rejected'],1)

    def test_input_and_output_aliases_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            first=Path(temp)/'input.json';second=Path(temp)/'alias.json';first.write_text('original');os.link(first,second)
            with self.assertRaises(ValueError):SEARCH.ensure_distinct_paths([first],[second])
            with self.assertRaises(ValueError):SEARCH.ensure_distinct_paths([first],[first])
            self.assertEqual(first.read_text(),'original')
    def test_empty_records_are_not_successful_imports(self):
        with self.assertRaises(ValueError):IMPORTER.merge(strategy(),[])
    def test_import_missing_records_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'strategy.json';records=root/'records.json';out=root/'result.json'
            source.write_text(json.dumps(strategy()));records.write_text('{}')
            with patch.object(sys,'argv',['importer','--strategy',str(source),'--records',str(records),'--output',str(out)]):
                self.assertEqual(IMPORTER.main(),2)
            self.assertFalse(out.exists())
    def test_render_cli_preserves_input_on_alias(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'strategy.json';original=json.dumps(strategy());path.write_text(original)
            with patch.object(sys,'argv',['renderer','render','--input',str(path),'--output',str(path)]):
                self.assertEqual(SEARCH.main(),2)
            self.assertEqual(path.read_text(),original)
    def test_pubmed_short_wildcard_prefix_has_warning(self):
        data={'question':'synthetic','concepts':[{'id':'a','free_text':['mobile app*']}]}
        self.assertTrue(SEARCH.render_platform(data,'pubmed')['warnings'])
    def test_query_syntax_is_not_treated_as_literal_term(self):
        data={'question':'synthetic','concepts':[{'id':'a','free_text':['x[tiab] OR y']}]}
        self.assertTrue(SEARCH.validate_strategy(data))

    def test_strict_json_rejects_duplicate_and_nonfinite_values(self):
        for raw in ['{"question":"a","question":"b"}', '{"x":NaN}', '{"x":Infinity}']:
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):SEARCH.strict_json(raw)

if __name__=='__main__':unittest.main()
