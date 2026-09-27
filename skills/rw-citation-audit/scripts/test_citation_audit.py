import tempfile
import unittest
from pathlib import Path
import citation_audit as ca

class CitationAuditRegression(unittest.TestCase):
    def audit_text(self,text,style='apa7'):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'m.md';path.write_text(text)
            return ca.audit(path,style)

    def test_syntactic_match_is_not_final_verified_pass(self):
        result=self.audit_text('Smith (2020) reported a finding.\n\n# References\n\nSmith, A. (2020). Synthetic title.')
        self.assertEqual(result['status'],'REVIEW')

    def test_two_author_citation_maps_to_first_author(self):
        result=self.audit_text('A result (Smith & Jones, 2020).\n\n# References\n\nSmith, A., & Jones, B. (2020). Synthetic title.')
        self.assertNotIn('CITATION_WITHOUT_REFERENCE',[i['code'] for i in result['issues']])

    def test_same_surname_single_author_disambiguation(self):
        result=self.audit_text('Smith (2020) and Smith (2021).\n\n# References\n\nSmith, A. (2020). One.\n\nSmith, B. (2021). Two.')
        self.assertIn('APA_SAME_SURNAME_INITIAL',[i['code'] for i in result['issues']])

    def test_balanced_doi_parentheses_preserved(self):
        result=ca.parse_references('Smith, A. (2020). Synthetic. https://doi.org/10.1000/item(one)')
        self.assertEqual(result[0]['doi'],'10.1000/item(one)')

    def test_reference_section_whitespace_not_pass(self):
        result=self.audit_text('A report.\n\n# References\n\n  \n')
        self.assertNotEqual(result['status'],'PASS')

    def test_cli_does_not_overwrite_input(self):
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'m.md';path.write_text('Original manuscript')
            result=subprocess.run([sys.executable,str(Path(ca.__file__)),str(path),'--output',str(path)],capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            self.assertEqual(path.read_text(),'Original manuscript')

if __name__=='__main__':unittest.main()
