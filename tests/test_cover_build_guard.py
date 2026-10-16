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

    def test_extensionless_resource_is_canonicalized_and_symlink_escape_rejected(self):
        art=self.root/'art.pdf';art.write_bytes(b'SYNTHETIC PDF PATH CONTROL')
        self.source.write_text(r'\documentclass[pages=200]{kdpcover}\putPicture{art}')
        self.assertIn(str(art),guard.validate_source(self.source,self.root))
        external=self.root.parent/(self.root.name+'-outside.pdf');external.write_bytes(b'SYNTHETIC OUTSIDE')
        self.addCleanup(external.unlink);art.unlink();art.symlink_to(external)
        with self.assertRaises(ValueError):guard.validate_source(self.source,self.root)
    def test_extensionless_missing_and_ambiguous_graphics_are_rejected(self):
        self.source.write_text(r'\documentclass[pages=200]{kdpcover}\putPicture{art}')
        with self.assertRaises(ValueError):guard.validate_source(self.source,self.root)
        for suffix in ['.pdf','.png']:(self.root/('art'+suffix)).write_bytes(b'SYNTHETIC')
        with self.assertRaises(ValueError):guard.validate_source(self.source,self.root)
    def test_comment_cannot_supply_or_mask_active_page_option(self):
        for text in ['% stale pages=200\n'+r'\documentclass[pages=10]{kdpcover}',r'\documentclass{ kdpcover } pages=200',r'\documentclass{ kdpcover }'+'\n%pages=200']:
            self.source.write_text(text)
            with self.assertRaises(ValueError):guard.validate_source(self.source,self.root)
        self.source.write_text('% stale pages=10\n'+r'\documentclass[pages=200]{kdpcover}')
        self.assertIn('pages=200',guard.validate_source(self.source,self.root))
    def test_duplicate_mixed_and_dynamic_options_are_rejected(self):
        for option in ['pages=200,pages=10','pages=200,pdf=book.pdf',r'pages=\mycount','pages=-1','pages=20.5']:
            self.source.write_text(r'\documentclass['+option+r']{kdpcover}')
            with self.assertRaises(ValueError):guard.validate_source(self.source,self.root)
        self.source.write_text(r'\PassOptionsToClass{pages=10}{kdpcover}\documentclass[pages=200]{kdpcover}')
        with self.assertRaises(ValueError):guard.validate_source(self.source,self.root)
    def test_comment_joining_matches_tex_and_literal_percent_is_preserved(self):
        self.source.write_text('\\documentclass[pages=2% comment\n00]{kdpcover}\n\\putBack{Synthetic 50\\% text}')
        self.assertIn('pages=200',guard.validate_source(self.source,self.root))
        self.assertIn(r'50\%',guard.validate_source(self.source,self.root))
    def test_companion_symlinks_and_existing_records_are_preserved(self):
        for suffix in ['.build.log','.build.json']:
            folder=self.root/('case-'+suffix.rsplit('.',1)[1]);folder.mkdir()
            sentinel=self.root/('outside-'+suffix.rsplit('.',1)[1]);sentinel.write_text('SYNTHETIC SENTINEL')
            destination=folder/'cover.pdf';destination.with_suffix(suffix).symlink_to(sentinel)
            with self.assertRaises(ValueError):guard.reserve_artifacts(folder,destination)
            self.assertEqual(sentinel.read_text(),'SYNTHETIC SENTINEL');self.assertFalse(destination.exists())

    def test_dangling_in_root_companion_is_not_followed(self):
        for suffix in ['.build.log','.build.json']:
            folder=self.root/('dangling-'+suffix.rsplit('.',1)[1]);folder.mkdir()
            target=folder/'absent';destination=folder/'cover.pdf'
            destination.with_suffix(suffix).symlink_to(target)
            with self.assertRaises(ValueError):guard.reserve_artifacts(folder,destination)
            self.assertFalse(target.exists());self.assertFalse(destination.exists())
            self.assertTrue(destination.with_suffix(suffix).is_symlink())

if __name__=='__main__':unittest.main()
