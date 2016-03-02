
from __future__ import absolute_import, division, print_function

import os
import unittest
from cStringIO import StringIO
from argparse import Namespace

from tldptesttools import TestInventoryBase

# -- Test Data
import example

# -- SUT
import tldp.config
import tldp.driver

opj = os.path.join
opd = os.path.dirname
opa = os.path.abspath
extras = opa(opj(opd(opd(__file__)), 'extras'))

widths = Namespace(status=20, stem=50)


class TestDriverDetail(TestInventoryBase):

    def test_stale_detail_verbosity(self):
        c = self.config
        self.add_stale('Frobnitz-HOWTO', example.ex_docbook4xml)
        c.verbose=True,
        inv = tldp.inventory.Inventory(c.pubdir, c.sourcedir)
        docs = inv.all.values()
        stdout = StringIO()
        tldp.driver.detail(c, docs, file=stdout)
        stdout.seek(0)
        self.assertTrue('newer file' in stdout.read())

    def test_broken_detail_verbosity(self):
        c = self.config
        self.add_broken('Frobnitz-HOWTO', example.ex_docbook4xml)
        c.verbose=True,
        inv = tldp.inventory.Inventory(c.pubdir, c.sourcedir)
        docs = inv.all.values()
        stdout = StringIO()
        tldp.driver.detail(c, docs, file=stdout)
        stdout.seek(0)
        self.assertTrue('missing file' in stdout.read())


class TestDriverSummary(TestInventoryBase):

    def test_summary(self):
        c = self.config
        self.add_new('Frobnitz-DocBook-XML-4-HOWTO', example.ex_docbook4xml)
        stdout = StringIO()
        tldp.driver.summary(c, None, file=stdout)
        stdout.seek(0)
        parts = stdout.read().split()
        idx = parts.index('new')
        self.assertEqual(['new', '1'], parts[idx:idx+2])


class TestDriverRun(TestInventoryBase):

    def test_run(self):
        c = self.config
        ex = example.ex_linuxdoc
        self.add_published('Published-HOWTO', ex)
        self.add_new('New-HOWTO', ex)
        self.add_stale('Stale-HOWTO', ex)
        self.add_orphan('Orphan-HOWTO', ex)
        self.add_broken('Broken-HOWTO', ex)
        argv = ['--pubdir', c.pubdir, '--sourcedir', c.sourcedir[0]]
        fullpath = os.path.join(self.tempdir, 'sources', 'New-HOWTO.sgml')
        argv.extend(['--build', 'stale', 'Orphan-HOWTO', fullpath])
        tldp.driver.run(argv)
        inv = tldp.inventory.Inventory(c.pubdir, c.sourcedir)
        self.assertEquals(4, len(inv.published.keys()))
        self.assertEquals(1, len(inv.broken.keys()))

    def test_run_extra_args(self):
        c = self.config
        self.add_new('New-HOWTO', example.ex_linuxdoc)
        argv = ['--pubdir', c.pubdir, '--sourcedir', c.sourcedir[0]]
        fullpath = os.path.join(self.tempdir, 'sources', 'New-HOWTO.sgml')
        argv.extend(['--build', 'stale', 'Orphan-HOWTO', fullpath, 'extra'])
        val = tldp.driver.run(argv)
        self.assertTrue('Unknown arguments' in val)

    def test_run_no_action(self):
        c = self.config
        ex = example.ex_linuxdoc
        self.add_new('New-HOWTO', ex)
        argv = ['--pubdir', c.pubdir, '--sourcedir', c.sourcedir[0]]
        tldp.driver.run(argv)
        inv = tldp.inventory.Inventory(c.pubdir, c.sourcedir)
        self.assertEquals(1, len(inv.published.keys()))

    def test_run_oops_no_sourcedir(self):
        c = self.config
        ex = example.ex_linuxdoc
        self.add_new('New-HOWTO', ex)
        argv = ['--pubdir', c.pubdir]
        exit = tldp.driver.run(argv)
        self.assertTrue('required for inventory' in exit)

    def test_run_oops_no_pubdir(self):
        c = self.config
        ex = example.ex_linuxdoc
        self.add_new('New-HOWTO', ex)
        argv = ['--sourcedir', c.sourcedir[0]]
        exit = tldp.driver.run(argv)
        self.assertTrue('required for inventory' in exit)


class TestDriverProcessSkips(TestInventoryBase):

    def test_skipDocuments_status(self):
        c = self.config
        ex = example.ex_linuxdoc
        self.add_new('New-HOWTO', ex)
        self.add_stale('Stale-HOWTO', ex)
        c.skip = ['stale']
        inv = tldp.inventory.Inventory(c.pubdir, c.sourcedir)
        docs = inv.all.values()
        inc, exc = tldp.driver.processSkips(c, docs)
        self.assertTrue(1, len(exc))
        excluded = exc.pop()
        self.assertEquals(excluded.stem, 'Stale-HOWTO')
        self.assertEquals(len(inc) + 1, len(inv.all.keys()))

    def test_skipDocuments_stem(self):
        c = self.config
        ex = example.ex_linuxdoc
        self.add_published('Published-HOWTO', ex)
        self.add_new('New-HOWTO', ex)
        c.skip = ['Published-HOWTO']
        inv = tldp.inventory.Inventory(c.pubdir, c.sourcedir)
        docs = inv.all.values()
        inc, exc = tldp.driver.processSkips(c, docs)
        self.assertTrue(1, len(exc))
        excluded = exc.pop()
        self.assertEquals(excluded.stem, 'Published-HOWTO')
        self.assertEquals(len(inc) + 1, len(inv.all.keys()))

    def test_skipDocuments_doctype(self):
        c = self.config
        self.add_published('Linuxdoc-HOWTO', example.ex_linuxdoc)
        self.add_new('Docbook4XML-HOWTO', example.ex_docbook4xml)
        c.skip = ['Docbook4XML']
        inv = tldp.inventory.Inventory(c.pubdir, c.sourcedir)
        docs = inv.all.values()
        inc, exc = tldp.driver.processSkips(c, docs)
        self.assertTrue(1, len(exc))
        excluded = exc.pop()
        self.assertEquals(excluded.stem, 'Docbook4XML-HOWTO')
        self.assertEquals(len(inc) + 1, len(inv.all.keys()))

@unittest.skip("Except when you want to spend time....")
class TestDriverBuild(TestInventoryBase):

    def test_build_linuxdoc(self):
        c = self.config
        self.add_new('Frobnitz-Linuxdoc-HOWTO', example.ex_linuxdoc)
        inv = tldp.inventory.Inventory(c.pubdir, c.sourcedir)
        self.assertEquals(1, len(inv.all.keys()))
        docs = inv.all.values()
        c.skip = []
        tldp.driver.build(c, docs)
        doc = docs.pop(0)
        self.assertTrue(doc.output.iscomplete)

    def test_build_docbooksgml(self):
        c = self.config
        self.add_new('Frobnitz-DocBook-SGML-HOWTO', example.ex_docbooksgml)
        c.docbooksgml_collateindex = os.path.join(extras, 'collateindex.pl')
        c.docbooksgml_ldpdsl = os.path.join(extras, 'ldp.dsl')
        inv = tldp.inventory.Inventory(c.pubdir, c.sourcedir)
        self.assertEquals(1, len(inv.all.keys()))
        docs = inv.all.values()
        tldp.driver.build(c, docs)
        doc = docs.pop(0)
        self.assertTrue(doc.output.iscomplete)

    def test_build_docbook4xml(self):
        c = self.config
        self.add_new('Frobnitz-DocBook-XML-4-HOWTO', example.ex_docbook4xml)
        c.docbook4xml_xslsingle = os.path.join(extras, 'ldp-html.xsl')
        c.docbook4xml_xslprint = os.path.join(extras, 'ldp-print.xsl')
        c.docbook4xml_xslchunk = os.path.join(extras, 'ldp-html-chunk.xsl')
        inv = tldp.inventory.Inventory(c.pubdir, c.sourcedir)
        self.assertEquals(1, len(inv.all.keys()))
        docs = inv.all.values()
        tldp.driver.build(c, docs)
        doc = docs.pop(0)
        self.assertTrue(doc.output.iscomplete)

#
# -- end of file
