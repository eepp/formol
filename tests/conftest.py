# Copyright (c) 2024 Philippe Proulx <eepp.ca>
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import re
import pytest
import formol


def pytest_collect_file(parent, file_path):
    ext = '.ft'

    if file_path.suffix != ext:
        # not a Formol test file: cancel
        return

    # create the file node
    return _FormolTestFile.from_parent(parent, path=file_path,
                                       name=f'test{file_path.name[4:].replace(ext, "")}')


def _split_ft_file(path):
    formol_lines = []
    expected_lines = []
    cur_lines = formol_lines

    with open(path) as f:
        for line in f:
            if line.rstrip() == '---' and len(expected_lines) == 0:
                cur_lines = expected_lines
                continue

            cur_lines.append(line)

    return ''.join(formol_lines), ''.join(expected_lines).rstrip()


class _FormolTestItem(pytest.Item):
    def runtest(self):
        formol_text, expected_text = _split_ft_file(self.path)
        assert formol.format(formol_text) == expected_text

    def reportinfo(self):
        return self.path, None, self.name


class _FormolTestFile(pytest.File):
    def __init__(self, name, **kwargs):
        super().__init__(**kwargs)
        self._name = name

    def collect(self):
        # yield a single item
        yield _FormolTestItem.from_parent(self, name=self._name)
