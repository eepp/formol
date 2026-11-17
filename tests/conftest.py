# SPDX-FileCopyrightText: 2024-2026 Philippe Proulx <eepp.ca>
# SPDX-License-Identifier: MIT

import pytest
import formol


def pytest_collect_file(parent, file_path):
    ext = '.ft'
    prefix = 'test-'

    if file_path.suffix != ext or not file_path.stem.startswith(prefix):
        return None

    name = f'test-{file_path.stem[len(prefix):]}'
    return _FormolTestFile.from_parent(parent, path=file_path, name=name)


# Returns `line` with each `␣` of its trailing `␣` run, if any, replaced
# with a space.
#
# This makes it possible to write significant trailing spaces in a `.ft`
# file, which a text editor would otherwise remove.
def _replace_trailing_space_marks(line):
    content = line.rstrip('\n')
    without_marks = content.rstrip('␣')
    spaces = ' ' * (len(content) - len(without_marks))
    return f'{without_marks}{spaces}{line[len(content):]}'


def _split_ft_file(path):
    formol_lines = []
    expected_lines = []
    in_expected = False

    with open(path, encoding='utf-8') as f:
        for line in f:
            if not in_expected and line.rstrip() == '---':
                in_expected = True
                continue

            line = _replace_trailing_space_marks(line)
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
