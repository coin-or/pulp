import os
import importlib


def test_examples(examples_dir='../examples'):
    files = os.listdir(examples_dir)
    for f_name in files:
        if os.path.isdir(f_name):
            continue
        _f_name = 'examples.' + os.path.splitext(f_name)[0]

        importlib.import_module(_f_name)

if __name__ == '__main__':
    test_examples('../examples')