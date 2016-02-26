#! /usr/bin/python
# -*- coding: utf8 -*-

import logging

from tldp.doctypes.common import BaseDoctype

logger = logging.getLogger(__name__)


class Asciidoc(BaseDoctype):
    formatname = 'AsciiDoc'
    extensions = ['.txt']
    signatures = []
    tools = ['asciidoc', 'a2x']

    def create_txt(self):
        logger.info("Creating txt for %s", self.source.stem)

    def create_pdf(self):
        logger.info("Creating PDF for %s", self.source.stem)

    def create_html(self):
        logger.info("Creating chunked HTML for %s", self.source.stem)

    def create_htmls(self):
        logger.info("Creating single page HTML for %s", self.source.stem)

#
# -- end of file
