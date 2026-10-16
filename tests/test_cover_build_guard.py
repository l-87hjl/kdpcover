"""No real assets: private-path and resource controls use synthetic temp files."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location('cover_build_guard',Path(__file__).resolve().parents[1]/'scripts/cover_build.py')
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)

class CoverBuildGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='synthetic-cover-guard-');self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve();self.source=self.root/'cover.tex'
    def test_external_output_escape_and_git_symlink_are_rejected(self):
        with self.assertRaises(ValueError):guard.private_path(self.root,self.root.parent/'escape.pdf')
        repo=self.root/'repo';repo.mkdir();(repo/'.git').mkdir();link=self.root/'link';link.symlink_to(repo)
        with self.assertRaises(ValueError):guard.private_path(self.root,link/'book.pdf')
    def test_remote_graphic_is_rejected_without_connection(self):
        self.source.write_text(r'\documentclass[pages=200]{kdpcover}\putPicture{https://example.invalid/a.pdf}')
        with self.assertRaises(ValueError):guard.validate_source(self.source,self.root)
    def test_remote_spine_graphic_is_rejected(self):
        self.source.write_text(r'\documentclass[pages=200]{kdpcover}\putSpine[https://example.invalid/a.pdf]{Synthetic}')
        with self.assertRaises(ValueError):guard.validate_source(self.source,self.root)
    def test_existing_output_is_preserved(self):
        self.source.write_text(r'\documentclass[pages=200]{kdpcover}\putTitle{Synthetic}')
        output=self.root/'finished.pdf';output.write_bytes(b'SYNTHETIC existing artifact')
        with self.assertRaises(ValueError):guard.build(self.root,self.source,output)
        self.assertEqual(output.read_bytes(),b'SYNTHETIC existing artifact')
    def test_raw_file_commands_are_rejected(self):
        self.source.write_text(r'\documentclass[pages=200]{kdpcover}\input{synthetic-other-file}')
        with self.assertRaises(ValueError):guard.validate_source(self.source,self.root)
    def test_production_minimum_is_checked(self):
        self.source.write_text(r'\documentclass[pages=10]{kdpcover}')
        with self.assertRaises(ValueError):guard.validate_source(self.source,self.root)
    def test_safe_explicit_count_passes(self):
        self.source.write_text(r'\documentclass[pages=200,paper=white]{kdpcover}\putTitle{Synthetic cover}')
        self.assertIn('pages=200',guard.validate_source(self.source,self.root))

if __name__=='__main__':unittest.main()
