import os, sys
import unittest
import pulp
import shutil

class Examples_DocsTests(unittest.TestCase):

    @unittest.skipIf(sys.version_info <= (2, 6), "python 2.6 has no importlib")
    def test_examples(self, examples_dir='../examples'):
        import importlib
        files = os.listdir(examples_dir)
        TMP_dir = '_tmp/'
        if not os.path.exists(TMP_dir):
            os.mkdir(TMP_dir)
        for f_name in files:
            if os.path.isdir(f_name):
                continue
            _f_name = 'examples.' + os.path.splitext(f_name)[0]
            os.chdir(TMP_dir)
            importlib.import_module(_f_name)
            os.chdir('../')
        shutil.rmtree(TMP_dir)

    def test_doctest(self):
        """
        runs all doctests
        """
        import doctest
        doctest.testmod(pulp)

if __name__ == '__main__':
    unittest.main()