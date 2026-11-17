# SPDX-FileCopyrightText: 2026 Philippe Proulx <eepp.ca>
# SPDX-License-Identifier: MIT

import pytest
import formol


# Returns the lines of the triple-quoted string `text` between its first
# line (empty) and its last line (the indentation of the closing
# delimiter), removing said indentation from each of them.
#
# Unlike textwrap.dedent(), this keeps any indentation common to all the
# content lines, for example a leading tab which is part of the
# tested comment.
def _dedent(text):
    lines = text.split('\n')
    assert lines[0] == ''
    indent = lines[-1]
    assert indent.strip(' ') == ''
    content_lines = lines[1:-1]
    assert all(line.startswith(indent) for line in content_lines)
    return '\n'.join(line[len(indent):] for line in content_lines)


@pytest.mark.parametrize('comment,start_col,max_line_len,expected', [
    # reflow within `max_line_len`, no indentation
    pytest.param(
        _dedent('''
            /*
             * Lorem ipsum dolor sit amet, consectetur adipiscing elit,
             * sed do eiusmod tempor.
             */
            '''),
        0, 40,
        _dedent('''
            /*
             * Lorem ipsum dolor sit amet,
             * consectetur adipiscing elit, sed do
             * eiusmod tempor.
             */
            '''),
        id='reflow-no-indent',
    ),

    # `start_col` shrinks the wrap budget and pads each output line
    # with spaces.
    pytest.param(
        _dedent('''
                /*
                 * Lorem ipsum dolor sit amet, consectetur adipiscing.
                 */
            '''),
        4, 30,
        _dedent('''
            /*
                 * Lorem ipsum dolor sit
                 * amet,
                 * consectetur adipiscing.
                 */
            '''),
        id='space-indent-start-col',
    ),

    # One leading tab in the input → one leading tab on every
    # output line.
    #
    # The visual tab width is inferred from `start_col`.
    pytest.param(
        _dedent('''
            \t/*
            \t * Lorem ipsum dolor sit amet, consectetur adipiscing elit.
            \t */
            '''),
        8, 40,
        _dedent('''
            /*
            \t * Lorem ipsum dolor sit amet,
            \t * consectetur adipiscing elit.
            \t */
            '''),
        id='tab-indent-one-tab',
    ),

    # Two leading tabs → tab width inferred as half of `start_col`; two
    # tabs appear on every output line.
    pytest.param(
        _dedent('''
            \t\t/*
            \t\t * Lorem ipsum dolor sit amet, consectetur adipiscing elit.
            \t\t */
            '''),
        8, 40,
        _dedent('''
            /*
            \t\t * Lorem ipsum dolor sit amet,
            \t\t * consectetur adipiscing elit.
            \t\t */
            '''),
        id='tab-indent-two-tabs',
    ),

    # Leading tab followed with spaces → same indentation on every
    # output line.
    #
    # The visual tab width is inferred from `start_col` minus the number
    # of spaces.
    pytest.param(
        _dedent('''
            \t  /*
            \t   * Lorem ipsum dolor sit amet, consectetur adipiscing elit.
            \t   */
            '''),
        10, 42,
        _dedent('''
            /*
            \t   * Lorem ipsum dolor sit amet,
            \t   * consectetur adipiscing elit.
            \t   */
            '''),
        id='tab-and-space-indent',
    ),

    # Empty content lines (` *` after strip) are preserved as
    # paragraph breaks.
    pytest.param(
        _dedent('''
            /*
             * First paragraph here.
             *
             * Second paragraph here.
             */
            '''),
        0, 72,
        _dedent('''
            /*
             * First paragraph here.
             *
             * Second paragraph here.
             */
            '''),
        id='blank-line-between-paragraphs',
    ),

    # Comment form is preserved: opening `/*`, leading ` * `,
    # closing ` */`.
    #
    # A single content line still gets wrapped in the proper block
    # comment shell.
    pytest.param(
        _dedent('''
            /*
             * Hi.
             */
            '''),
        0, 72,
        _dedent('''
            /*
             * Hi.
             */
            '''),
        id='minimal-roundtrip',
    ),

    # comment without any content
    pytest.param(
        _dedent('''
            /*
             *
             *
             */
            '''),
        4, 72,
        _dedent('''
            /*
                 */
            '''),
        id='empty',
    ),
])
def test_format_c_block_comment(comment, start_col, max_line_len, expected):
    assert formol.format_c_block_comment(comment, start_col=start_col,
                                         max_line_len=max_line_len) == expected


@pytest.mark.parametrize('comment,start_col,max_line_len,prefix,expected', [
    # reflow with the default Python `# ` prefix
    pytest.param(
        _dedent('''
            # Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do
            # eiusmod tempor.
            '''),
        0, 40, '# ',
        _dedent('''
            # Lorem ipsum dolor sit amet,
            # consectetur adipiscing elit, sed do
            # eiusmod tempor.
            '''),
        id='reflow-hash-prefix',
    ),

    # Custom prefix (C++/JS `// `).
    #
    # Output uses the same prefix.
    pytest.param(
        _dedent('''
            // Lorem ipsum dolor sit amet, consectetur adipiscing elit.
            // Sed do eiusmod tempor incididunt.
            '''),
        0, 30, '// ',
        _dedent('''
            // Lorem ipsum dolor sit amet,
            // consectetur adipiscing
            // elit. Sed do eiusmod
            // tempor incididunt.
            '''),
        id='custom-slash-prefix',
    ),

    # Space-indented input: leading spaces appear on every output line,
    # sized by `start_col`.
    pytest.param(
        '    # Lorem ipsum dolor sit amet, consectetur adipiscing elit.',
        4, 30, '# ',
        _dedent('''
                # Lorem ipsum dolor sit
                # amet, consectetur
                # adipiscing elit.
            '''),
        id='space-indent-start-col',
    ),

    # tab indentation in input → tabs preserved on every output line
    pytest.param(
        '\t# Lorem ipsum dolor sit amet, consectetur adipiscing elit.',
        8, 40, '# ',
        _dedent('''
            \t# Lorem ipsum dolor sit amet,
            \t# consectetur adipiscing elit.
            '''),
        id='tab-indent-one-tab',
    ),

    # Two leading tabs → output uses two tabs per line (tab width
    # inferred as half of `start_col`).
    pytest.param(
        '\t\t# Lorem ipsum dolor sit amet, consectetur adipiscing elit.',
        8, 40, '# ',
        _dedent('''
            \t\t# Lorem ipsum dolor sit amet,
            \t\t# consectetur adipiscing elit.
            '''),
        id='tab-indent-two-tabs',
    ),

    # Leading tab followed with spaces → same indentation on every
    # output line (tab width inferred as `start_col` minus the
    # number of spaces).
    pytest.param(
        '\t  # Lorem ipsum dolor sit amet, consectetur adipiscing elit.',
        10, 42, '# ',
        _dedent('''
            \t  # Lorem ipsum dolor sit amet,
            \t  # consectetur adipiscing elit.
            '''),
        id='tab-and-space-indent',
    ),

    # prefix-only lines mark paragraph breaks and are preserved
    pytest.param(
        _dedent('''
            # First paragraph here.
            #
            # Second paragraph here.
            '''),
        0, 72, '# ',
        _dedent('''
            # First paragraph here.
            #
            # Second paragraph here.
            '''),
        id='blank-line-between-paragraphs',
    ),

    # Minimal round trip: a single-line prefixed comment comes
    # back unchanged.
    pytest.param(
        '# Hi.',
        0, 72, '# ',
        '# Hi.',
        id='minimal-roundtrip',
    ),

    # comment without any content → single empty comment line
    pytest.param(
        _dedent('''
                #
                #
            '''),
        4, 72, '# ',
        '    #',
        id='empty',
    ),
])
def test_format_prefixed_block_comment(comment, start_col, max_line_len,
                                       prefix, expected):
    assert formol.format_prefixed_block_comment(comment, start_col=start_col,
                                                max_line_len=max_line_len,
                                                prefix=prefix) == expected
