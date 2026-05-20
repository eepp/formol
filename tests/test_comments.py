# SPDX-FileCopyrightText: 2026 Philippe Proulx <eepp.ca>
# SPDX-License-Identifier: MIT

import pytest
import formol


@pytest.mark.parametrize('comment,start_col,max_line_len,expected', [
    # reflow within `max_line_len`, no indentation
    pytest.param(
        '/*\n'
        ' * Lorem ipsum dolor sit amet, consectetur adipiscing elit,\n'
        ' * sed do eiusmod tempor.\n'
        ' */',
        0, 40,
        '/*\n'
        ' * Lorem ipsum dolor sit amet,\n'
        ' * consectetur adipiscing elit, sed do\n'
        ' * eiusmod tempor.\n'
        ' */',
        id='reflow-no-indent',
    ),

    # `start_col` shrinks the wrap budget and pads each output line
    # with spaces.
    pytest.param(
        '    /*\n'
        '     * Lorem ipsum dolor sit amet, consectetur adipiscing.\n'
        '     */',
        4, 30,
        '/*\n'
        '     * Lorem ipsum dolor sit\n'
        '     * amet,\n'
        '     * consectetur adipiscing.\n'
        '     */',
        id='space-indent-start-col',
    ),

    # One leading tab in the input → one leading tab on every output
    # line.
    #
    # The visual tab width is inferred from `start_col`.
    pytest.param(
        '\t/*\n'
        '\t * Lorem ipsum dolor sit amet, consectetur adipiscing elit.\n'
        '\t */',
        8, 40,
        '/*\n'
        '\t * Lorem ipsum dolor sit amet,\n'
        '\t * consectetur adipiscing elit.\n'
        '\t */',
        id='tab-indent-one-tab',
    ),

    # Two leading tabs → tab width inferred as half of `start_col`; two
    # tabs appear on every output line.
    pytest.param(
        '\t\t/*\n'
        '\t\t * Lorem ipsum dolor sit amet, consectetur adipiscing elit.\n'
        '\t\t */',
        8, 40,
        '/*\n'
        '\t\t * Lorem ipsum dolor sit amet,\n'
        '\t\t * consectetur adipiscing elit.\n'
        '\t\t */',
        id='tab-indent-two-tabs',
    ),

    # Empty content lines (` *` after strip) are preserved as
    # paragraph breaks.
    pytest.param(
        '/*\n'
        ' * First paragraph here.\n'
        ' *\n'
        ' * Second paragraph here.\n'
        ' */',
        0, 72,
        '/*\n'
        ' * First paragraph here.\n'
        ' *\n'
        ' * Second paragraph here.\n'
        ' */',
        id='blank-line-between-paragraphs',
    ),

    # Comment form is preserved: opening `/*`, leading ` * `,
    # closing ` */`.
    #
    # A single content line still gets wrapped in the proper
    # block comment shell.
    pytest.param(
        '/*\n'
        ' * Hi.\n'
        ' */',
        0, 72,
        '/*\n'
        ' * Hi.\n'
        ' */',
        id='minimal-roundtrip',
    ),
])
def test_format_c_block_comment(comment, start_col, max_line_len, expected):
    assert formol.format_c_block_comment(comment, start_col=start_col,
                                         max_line_len=max_line_len) == expected


@pytest.mark.parametrize('comment,start_col,max_line_len,prefix,expected', [
    # reflow with the default Python `# ` prefix
    pytest.param(
        '# Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do\n'
        '# eiusmod tempor.',
        0, 40, '# ',
        '# Lorem ipsum dolor sit amet,\n'
        '# consectetur adipiscing elit, sed do\n'
        '# eiusmod tempor.',
        id='reflow-hash-prefix',
    ),

    # Custom prefix (C++/JS `// `).
    #
    # Output uses the same prefix.
    pytest.param(
        '// Lorem ipsum dolor sit amet, consectetur adipiscing elit.\n'
        '// Sed do eiusmod tempor incididunt.',
        0, 30, '// ',
        '// Lorem ipsum dolor sit amet,\n'
        '// consectetur adipiscing\n'
        '// elit. Sed do eiusmod\n'
        '// tempor incididunt.',
        id='custom-slash-prefix',
    ),

    # Space-indented input: leading spaces appear on every output
    # line, sized by `start_col`.
    pytest.param(
        '    # Lorem ipsum dolor sit amet, consectetur adipiscing elit.',
        4, 30, '# ',
        '    # Lorem ipsum dolor sit\n'
        '    # amet, consectetur\n'
        '    # adipiscing elit.',
        id='space-indent-start-col',
    ),

    # tab indentation in input → tabs preserved on every output line
    pytest.param(
        '\t# Lorem ipsum dolor sit amet, consectetur adipiscing elit.',
        8, 40, '# ',
        '\t# Lorem ipsum dolor sit amet,\n'
        '\t# consectetur adipiscing elit.',
        id='tab-indent-one-tab',
    ),

    # Two leading tabs → output uses two tabs per line (tab width
    # inferred as half of `start_col`).
    pytest.param(
        '\t\t# Lorem ipsum dolor sit amet, consectetur adipiscing elit.',
        8, 40, '# ',
        '\t\t# Lorem ipsum dolor sit amet,\n'
        '\t\t# consectetur adipiscing elit.',
        id='tab-indent-two-tabs',
    ),

    # prefix-only lines mark paragraph breaks and are preserved
    pytest.param(
        '# First paragraph here.\n'
        '#\n'
        '# Second paragraph here.',
        0, 72, '# ',
        '# First paragraph here.\n'
        '#\n'
        '# Second paragraph here.',
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
])
def test_format_prefixed_block_comment(comment, start_col, max_line_len,
                                       prefix, expected):
    assert formol.format_prefixed_block_comment(comment, start_col=start_col,
                                                max_line_len=max_line_len,
                                                prefix=prefix) == expected
