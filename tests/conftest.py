# Copyright (c) 2024-2026 Philippe Proulx <eepp.ca>
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

import pytest
import formol


def pytest_collect_file(parent, file_path):
    ext = '.ft'
    prefix = 'test-'

    if file_path.suffix != ext or not file_path.stem.startswith(prefix):
        return None

    name = f'test-{file_path.stem[len(prefix):]}'
    return _FormolTestFile.from_parent(parent, path=file_path, name=name)


def _split_ft_file(path):
    formol_lines = []
    expected_lines = []
    in_expected = False

    with open(path, encoding='utf-8') as f:
        for line in f:
            if not in_expected and line.rstrip() == '---':
                in_expected = True
                continue

            (expected_lines if in_expected else formol_lines).append(line)

    return ''.join(formol_lines), ''.join(expected_lines).rstrip()


class _FormolTestItem(pytest.Item):
    def runtest(self):
        formol_text, expected_text = _split_ft_file(self.path)
        assert formol.format(formol_text) == expected_text

    def reportinfo(self):
        return self.path, None, self.name


class _FormolTestFile(pytest.File):
    def collect(self):
        yield _FormolTestItem.from_parent(self, name=self.name)
