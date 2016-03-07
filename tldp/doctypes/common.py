#! /usr/bin/python
# -*- coding: utf8 -*-

from __future__ import absolute_import, division, print_function

import os
import sys
import stat
import errno
import shutil
import logging
import inspect
from tempfile import NamedTemporaryFile as ntf
from functools import wraps
import networkx as nx

from tldp.utils import execute, logtimings

logger = logging.getLogger(__name__)

preamble = '''#! /bin/bash
set -x
set -e
set -o pipefail
'''

postamble = '''
# -- end of file
'''


def depends(*predecessors):
    '''decorator to be used for constructing build order graph'''
    def anon(f):
        @wraps(f)
        def method(self, *args, **kwargs):
            return f(self, *args, **kwargs)
        method.depends = [x.__name__ for x in predecessors]
        return method
    return anon


class SignatureChecker(object):

    @classmethod
    def signatureLocation(cls, f):
        f.seek(0)
        buf = f.read(1024)
        for sig in cls.signatures:
            try:
                sindex = buf.index(sig)
                logger.debug("YES FOUND signature %r in %s at %s; doctype %s.",
                             sig, f.name, sindex, cls)
                return sindex
            except ValueError:
                logger.debug("not found signature %r in %s for type %s",
                             sig, f.name, cls.__name__)
        return None


class BaseDoctype(object):

    def __repr__(self):
        return '<%s:%s>' % (self.__class__.__name__, self.source.stem,)

    def __init__(self, *args, **kwargs):
        self.source = kwargs.get('source', None)
        self.output = kwargs.get('output', None)
        self.config = kwargs.get('config', None)
        self.removals = list()
        assert self.source is not None
        assert self.output is not None
        assert self.config is not None

    def cleanup(self):
        if self.config.script:
            return
        stem = self.source.stem
        removals = getattr(self, 'removals', None)
        if removals:
            for fn in removals:
                logger.debug("%s cleaning up intermediate file %s", stem, fn)
                try:
                    os.unlink(fn)
                except OSError as e:
                    if e.errno is errno.ENOENT:
                        logger.error("%s missing file at cleanup %s", stem, fn)
                    else:
                        raise e

    def build_precheck(self):
        classname = self.__class__.__name__
        for tool, validator in self.required.items():
            thing = getattr(self.config, tool, None)
            logger.debug("%s, tool = %s, thing = %s", classname, tool, thing)
            if thing is None:
                logger.error("%s missing required tool %s, skipping...",
                             classname, tool)
                return False
            assert validator(thing)
        return True

    def clear_output(self):
        '''remove the entire output directory

        This method must be --script aware.  The method execute_shellscript()
        generates scripts into the directory that would be removed.  Thus, the
        behaviour is different depending on --script mode or --build mode.
        '''
        logger.debug("%s removing dir   %s.",
                     self.output.stem, self.output.dirname)
        if self.config.script:
            s = 'test -d "{output.dirname}" && rm -rf -- "{output.dirname}"'
            return self.shellscript(s)
        if os.path.exists(self.output.dirname):
            shutil.rmtree(self.output.dirname)
        return True

    def mkdir_output(self):
        '''create a new output directory

        This method must be --script aware.  The method execute_shellscript()
        generates scripts into the directory that would be removed.  Thus, the
        behaviour is different depending on --script mode or --build mode.
        '''
        logger.debug("%s creating dir   %s.",
                     self.output.stem, self.output.dirname)
        if self.config.script:
            s = 'mkdir -p -- "{output.logdir}"'
            return self.shellscript(s)
        for d in (self.output.dirname, self.output.logdir):
            if not os.path.isdir(d):
                os.mkdir(d)
        return True

    def chdir_output(self):
        '''chdir to the output directory (or write the script that would)'''
        logger.debug("%s chdir to dir   %s.",
                     self.output.stem, self.output.dirname)
        if self.config.script:
            s = 'cd -- "{output.dirname}"'
            return self.shellscript(s)
        os.chdir(self.output.dirname)
        return True

    def copy_static_resources(self):
        logger.debug("%s copy resources %s.",
                     self.output.stem, self.output.dirname)
        source = list()
        for d in self.config.resources:
            fullpath = os.path.join(self.source.dirname, d)
            fullpath = os.path.abspath(fullpath)
            if os.path.isdir(fullpath):
                source.append('"' + fullpath + '"')
        if not source:
            logger.debug("%s no images or resources to copy", self.source.stem)
            return True
        s = 'rsync --archive --verbose %s ./' % (' '.join(source))
        return self.shellscript(s)

    def hook_build_prepare(self):
        stem = self.source.stem
        classname = self.__class__.__name__
        order = ['build_precheck',
                 'clear_output',
                 'mkdir_output',
                 'chdir_output',
                 'copy_static_resources',
                 ]
        # -- perform build preparation steps:  clear
        #
        for methname in order:
            method = getattr(self, methname, None)
            assert method is not None
            if not method():
                logger.warning("%s %s failed (%s), skipping",
                               stem, methname, classname)
                return False
        return True

    def hook_build_success(self):
        stem = self.output.stem
        logdir = self.output.logdir
        dirname = self.output.dirname
        logger.info("%s build SUCCESS  %s.", stem, dirname)
        logger.debug("%s removing logs  %s)", stem, logdir)
        if os.path.isdir(logdir):
            shutil.rmtree(logdir)
        return True

    def hook_build_failure(self):
        pass

    def shellscript(self, script, **kwargs):
        if self.config.build:
            return self.execute_shellscript(script, **kwargs)
        elif self.config.script:
            return self.dump_shellscript(script, **kwargs)
        else:
            etext = '%s in shellscript, neither --build nor --script'
            raise Exception(etext % (self.source.stem,))

    @logtimings(logger.debug)
    def dump_shellscript(self, script, preamble=preamble, postamble=postamble):
        source = self.source
        output = self.output
        config = self.config
        s = script.format(output=output, source=source, config=config)
        print('', file=sys.stdout)
        print(s, file=sys.stdout)
        return True

    @logtimings(logger.debug)
    def execute_shellscript(self, script, preamble=preamble, 
                            postamble=postamble):
        source = self.source
        output = self.output
        config = self.config

        logdir = output.logdir
        prefix = source.doctype.__name__ + '-'

        s = script.format(output=output, source=source, config=config)
        tf = ntf(dir=logdir, prefix=prefix, suffix='.sh', delete=False)
        if preamble:
            tf.write(preamble)
        tf.write(s)
        if postamble:
            tf.write(postamble)
        tf.close()

        mode = stat.S_IXUSR | stat.S_IRUSR | stat.S_IWUSR
        os.chmod(tf.name, mode)

        cmd = [tf.name]
        result = execute(cmd, logdir=logdir)
        if result != 0:
            with open(tf.name) as f:
                for line in f:
                    logger.info("Script: %s", line.rstrip())
            return False
        return True

    def determinebuildorder(self):
        graph = nx.DiGraph()
        d = dict(inspect.getmembers(self, inspect.ismethod))
        for name, member in d.items():
            predecessors = getattr(member, 'depends', None)
            if predecessors:
                for pred in predecessors:
                    method = d.get(pred, None)
                    assert method is not None
                    graph.add_edge(method, member)
        order = nx.dag.topological_sort(graph)
        return order

    @logtimings(logger.debug)
    def buildall(self):
        stem = self.source.stem
        order = self.determinebuildorder()
        logger.debug("%s build order %r", self.source.stem, order)
        for method in order:
            classname = self.__class__.__name__
            logger.info("%s calling method %s.%s",
                        stem, classname, method.__name__)
            if not method():
                logger.error("%s called method  %s.%s failed, skipping...",
                             stem, classname, method.__name__)
                return False
        return True

    @logtimings(logger.info)
    def generate(self):
        # -- perform build preparation steps;
        #     - check for all executables and data files
        #     - clear output dir
        #     - make output dir
        #     - chdir to output dir
        #     - copy source images/resources to output dir
        #
        opwd = os.getcwd()
        if not self.hook_build_prepare():
            return False

        # -- build
        #
        result = self.buildall()

        # -- report on result and/or cleanup
        #
        if result:
            self.hook_build_success()
        else:
            self.hook_build_failure()

        os.chdir(opwd)

        return result

#
# -- end of file
