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
#
# pyright: strict

__all__ = [
    'format',
    'format_c_block_comment',
    'format_prefixed_block_comment',
]
__version__ = '0.7.0'
__author__ = 'Philippe Proulx <eepp.ca>'


from typing import Dict, Any, Type, TypeVar, Callable, List, Sequence, Union, Pattern, Match, Optional
from dataclasses import dataclass
import re


# Element base.
class _Elem:
    pass

# Paragraph.
@dataclass(frozen=True)
class _P(_Elem):
    words: List[str]


# Simple list item.
@dataclass(frozen=True)
class _SimpleListItem:
    elems: List[_Elem]


# Simple list base.
@dataclass(frozen=True)
class _SimpleList(_Elem):
    items: List[_SimpleListItem]


# Unordered list.
class _Ul(_SimpleList):
    pass


# Ordered list.
class _Ol(_SimpleList):
    pass


# Definition list item.
@dataclass(frozen=True)
class _DlItem:
    terms: List[str]
    elems: List[_Elem]


# Definition list.
@dataclass(frozen=True)
class _Dl(_Elem):
    items: List[_DlItem]


# Preformatted text.
@dataclass(frozen=True)
class _Pre(_Elem):
    lines: List[str]


# Heading base.
@dataclass(frozen=True)
class _Heading(_Elem):
    text: str


# Level 1 heading.
class _H1(_Heading):
    pass


# Level 2 heading.
class _H2(_Heading):
    pass


# Break.
class _Hr(_Elem):
    pass


# Admonition box.
@dataclass(frozen=True)
class _AdmonBox(_Elem):
    elems: List[_Elem]


# Blockquote.
@dataclass(frozen=True)
class _Blockquote(_Elem):
    elems: List[_Elem]


# Verbatim.
@dataclass(frozen=True)
class _Verbatim(_Elem):
    lines: List[str]


# Returns `lines` without trailing empty lines.
#
# `lines` must not be empty.
def _remove_trailing_empty_lines(lines: List[str]):
    assert len(lines) >= 1
    new_lines = lines.copy()

    while True:
        if new_lines[-1] != '':
            break

        del new_lines[-1]

    return new_lines


# Returns the indentation string for `count` spaces.
def _indent_str(count: int):
    return ' ' * count


# Parses the raw lines on initialization; the `elems` property is then
# the resulting list of elements.
class _Parser:
    def __init__(self, lines: Sequence[str]):
        self._lines = lines
        self._at: int = 0
        self._last_line_index = len(lines) - 1
        self._elems : List[_Elem] = []
        self._parse()

    # Resulting list of elements.
    @property
    def elems(self):
        return self._elems

    # Current line to parse.
    @property
    def _cur_line(self):
        assert not self._is_done
        return self._lines[self._at]

    # `True` if the current line to parse is empty.
    @property
    def _cur_line_is_empty(self):
        return len(self._cur_line) == 0

    # Next line to parse or an empty line if not available.
    @property
    def _next_line(self):
        if len(self._lines) == 1:
            return ''

        return '' if self._at >= self._last_line_index else self._lines[self._at + 1]

    # Updates the state to make the next line (or more with `incr`) the
    # current one.
    def _goto_next_line(self, incr: int = 1):
        assert incr >= 1
        self._at += incr
        assert self._at <= len(self._lines)

    def _match_cur_line(self, pat: Union[str, Pattern[str]]) -> Optional[Match[str]]:
        return re.match(pat, self._cur_line)

    def _match_next_line(self, pat: Union[str, Pattern[str]]) -> Optional[Match[str]]:
        return re.match(pat, self._next_line)

    def _skip_empty_lines(self):
        while not self._is_done and self._cur_line_is_empty:
            self._goto_next_line()

    # `True` if we're done parsing.
    @property
    def _is_done(self):
        return self._at >= len(self._lines)

    _HeadingElemTV = TypeVar('_HeadingElemTV', bound=_Heading)

    # Tries to parse a heading having the prefix `prefix` and the
    # underscore character `underscore_ch`.
    #
    # Returns an element of type `elem_type` on success.
    def _try_parse_heading(self, elem_type: Type[_HeadingElemTV], prefix: str,
                           underscore_ch: str) -> Optional[_HeadingElemTV]:
        # with prefix?
        m = self._match_cur_line(rf'^{prefix} (\S.*)')

        if m and len(self._next_line) == 0:
            elem = elem_type(m.group(1))
            self._goto_next_line()
            return elem

        # with underline?
        if self._match_next_line(fr'^{underscore_ch}+\s*$'):
            elem = elem_type(self._cur_line)
            self._goto_next_line(2)
            return elem

    # Tries to parse a first level heading.
    #
    # Example 1:
    #
    #     = hello world
    #
    # Example 2:
    #
    #     HELLO WORLD
    #     ═══════════
    def _try_parse_h1(self):
        return self._try_parse_heading(_H1, '=', '━')

    # Tries to parse a level 2 heading.
    #
    # Example 1:
    #
    #     == How are you?
    #
    # Example 2:
    #
    #     How are you?
    #     ────────────
    def _try_parse_h2(self):
        return self._try_parse_heading(_H2, '==', '─')

    # Unindents the lines by `count` spaces when possible, keeping
    # unindentable lines as is.
    @staticmethod
    def _unindent_lines(lines: List[str], count: int = 4):
        def unindent_line(line: str):
            indent_str = _indent_str(count)

            if line.startswith(indent_str):
                # enough initial spaces to unindent
                return line[count:]

            # keep as is
            return line

        return list(map(unindent_line, lines))

    _single_line_dt_pat = re.compile(r'^(\S.*):: (\S.*)')

    # Tries to parse a single-line definition list item.
    #
    # Example:
    #
    #     Online:: Available on or performed using the internet.
    def _try_parse_single_line_dl_item(self):
        m = self._match_cur_line(self._single_line_dt_pat)

        if not m:
            return

        self._goto_next_line()
        return _DlItem([m.group(1)], _Parser([m.group(2)]).elems)

    _dt_pat = re.compile(r'^(\S.*):$')
    _indented_content_pat = re.compile(r'^    .')

    # Tries to parse a definition list item.
    #
    # Example 1:
    #
    #     Jackie Brown:
    #         When flight attendant Jackie Brown (Pam Grier) is busted
    #         smuggling money for her arms dealer boss, Ordell Robbie
    #         (Samuel L. Jackson), agent Ray Nicolette (Michael Keaton)
    #         and detective Mark Dargus (Michael Bowen) want her help to
    #         bring down Robbie.
    #
    # Example 2:
    #
    #     Apples:
    #     Oranges:
    #         Nice fruits to have.
    #
    # Example 3:
    #
    #     Online:: Available on or performed using the internet.
    def _try_parse_dl_item(self):
        # try a single-line item first
        elem = self._try_parse_single_line_dl_item()

        if elem is not None:
            return elem

        # check for one or more terms
        terms: List[str] = []
        begin_at = self._at

        while not self._is_done:
            dt_m = self._match_cur_line(self._dt_pat)

            if not dt_m:
                # no more terms
                break

            terms.append(dt_m.group(1))
            self._goto_next_line()

        if len(terms) == 0:
            # no terms
            self._at = begin_at
            return

        if self._is_done or not self._match_cur_line(r'^    \S'):
            # no definition
            self._at = begin_at
            return

        # parse definition lines
        def_lines: List[str] = []

        while not self._is_done:
            if self._cur_line_is_empty:
                # keep empty line
                def_lines.append('')
                self._goto_next_line()
                continue

            if self._match_cur_line(self._indented_content_pat):
                # indented content line
                def_lines.append(self._cur_line)
                self._goto_next_line()
                continue

            # end of definition
            break

        # remove trailing empty definition lines
        def_lines = _remove_trailing_empty_lines(def_lines)

        # create item from unindented definition lines
        return _DlItem(terms, _Parser(self._unindent_lines(def_lines)).elems)

    # Tries to parse a definition list.
    #
    # Example:
    #
    #     Jackie Brown:
    #         When flight attendant Jackie Brown (Pam Grier) is busted
    #         smuggling money for her arms dealer boss, Ordell Robbie
    #         (Samuel L. Jackson), agent Ray Nicolette (Michael Keaton)
    #         and detective Mark Dargus (Michael Bowen) want her help to
    #         bring down Robbie.
    #
    #     Apples:
    #     Oranges:
    #         Nice fruits to have.
    #     Online:: Available on or performed using the internet.
    def _try_parse_dl(self):
        items: List[_DlItem] = []

        while True:
            self._skip_empty_lines()

            if self._is_done:
                break

            item = self._try_parse_dl_item()

            if item is None:
                break

            items.append(item)

        if len(items) >= 1:
            return _Dl(items)

    # Tries to parse an indented preformatted text block.
    #
    # Example (paragraph and then preformatted text block):
    #
    #     Here's the code:
    #
    #         if (idx < vec.size() - 1) {
    #             vec[idx] = std::move(vec.back());
    #         }
    def _try_parse_pre_indented(self):
        if not re.match(r'^    \S', self._cur_line):
            # not an indented preformatted text block
            return

        lines: List[str] = []

        while not self._is_done:
            if self._cur_line_is_empty:
                # keep empty line
                lines.append('')
                self._goto_next_line()
                continue

            if self._match_cur_line(self._indented_content_pat):
                # content line
                lines.append(self._cur_line)
                self._goto_next_line()
                continue

            # end of block
            break

        # remove trailing empty lines
        lines = _remove_trailing_empty_lines(lines)

        # create element from unindented lines
        return _Pre(self._unindent_lines(lines))

    # Tries to parse a text block delimited with `delim`.
    #
    # Returns the parsed content lines or `None`.
    def _try_parse_delim_block(self, delim: str):
        # block start?
        if self._cur_line != delim:
            # not the expected text block
            return

        # skip block start
        self._goto_next_line()

        # parse content lines
        lines: List[str] = []

        while not self._is_done:
            # block end?
            if self._cur_line == delim:
                # skip block end and stop
                self._goto_next_line()
                break

            # append content line and go to next line
            lines.append(self._cur_line)
            self._goto_next_line()

        # remove trailing empty lines
        lines =  _remove_trailing_empty_lines(lines)

        # return if not empty
        if len(lines) >= 1:
            return lines

    # Tries to parse a preformatted text block delimited with "```".
    #
    # Example:
    #
    #     ```
    #     if (idx < vec.size() - 1) {
    #         vec[idx] = std::move(vec.back());
    #     }
    #     ```
    def _try_parse_pre_delim(self):
        lines = self._try_parse_delim_block('```')

        if lines is not None:
            # create element
            return _Pre(lines)

    _bullet_line_pat = re.compile(r'^[*•‣⁃] (\S.*)')
    _ul_cont_pat = re.compile(r'^  .')

    # Tries to parse an unordered list item.
    #
    # Example 1:
    #
    #     * Hello.
    #
    # Example 2:
    #
    #     • I'm baby whatever tumblr meditation fashion axe jawn. XOXO
    #       pork belly banh mi shoreditch woke.
    #
    #           #include <functional>
    #           #include <utility>
    #
    #       In that:
    #
    #       . Chia vinyl plaid.
    #       . Lo-fi skateboard pug messenger.
    def _try_parse_ul_item(self):
        # item start?
        bullet_m = self._match_cur_line(self._bullet_line_pat)

        if not bullet_m:
            # no item
            return

        # skip first line
        self._goto_next_line()

        # parse remaining content lines
        lines = [bullet_m.group(1)]

        while not self._is_done:
            if self._cur_line_is_empty:
                # keep empty line
                lines.append('')
                self._goto_next_line()
                continue

            if self._match_cur_line(self._ul_cont_pat):
                # indented content line
                lines.append(self._cur_line)
                self._goto_next_line()
                continue

            # end of item
            break

        # remove trailing empty lines
        lines = _remove_trailing_empty_lines(lines)

        # create item from unindented content lines
        return _SimpleListItem(_Parser(self._unindent_lines(lines, 2)).elems)

    _SimpleListElemTV = TypeVar('_SimpleListElemTV', bound=_SimpleList)

    # Tries to parse a simple list using `parse_item_func` to try to
    # parse individual items, and returns an instance of `elem_type`.
    def _try_parse_simple_list(self, elem_type: Type[_SimpleListElemTV],
                               parse_item_func: Callable[[], Optional[_SimpleListItem]]) -> Optional[_SimpleListElemTV]:
        items: List[_SimpleListItem] = []

        while True:
            # skip empty lines between
            self._skip_empty_lines()

            if self._is_done:
                break

            # new item?
            item = parse_item_func()

            if item is None:
                # no more items
                break

            # append new item
            items.append(item)

        if len(items) >= 1:
            return elem_type(items)

    # Tries to parse an unordered list.
    def _try_parse_ul(self):
        return self._try_parse_simple_list(_Ul, self._try_parse_ul_item)

    # Tries to parse an ordered list item.
    #
    # Example 1:
    #
    #     . Hello.
    #
    # Example 2:
    #
    #     1. I'm baby whatever tumblr meditation fashion axe jawn. XOXO
    #        pork belly banh mi shoreditch woke.
    #
    #            #include <functional>
    #            #include <utility>
    #
    #        In that:
    #
    #        * Chia vinyl plaid.
    #        * Lo-fi skateboard pug messenger.
    #
    # Example 3:
    #
    #     c) Meow Mix.
    def _try_parse_ol_item(self):
        # item start?
        num_m = self._match_cur_line(r'^((?: *\d+)?\. |[a-z]\) )(\S.*)')

        if not num_m:
            # no item
            return

        # skip first line
        self._goto_next_line()

        # parse remaining content lines
        lines: List[str] = [num_m.group(2)]
        prefix_len = len(num_m.group(1))
        cont_pat = re.compile(fr'^{" " * prefix_len}.')

        while not self._is_done:
            if self._cur_line_is_empty:
                # keep empty line
                lines.append('')
                self._goto_next_line()
                continue

            if self._match_cur_line(cont_pat):
                # indented content line
                lines.append(self._cur_line)
                self._goto_next_line()
                continue

            # end of item
            break

        # remove trailing empty lines
        lines = _remove_trailing_empty_lines(lines)

        # create item from unindented content lines
        return _SimpleListItem(_Parser(self._unindent_lines(lines, prefix_len)).elems)

    # Tries to parse an ordered list.
    def _try_parse_ol(self):
        return self._try_parse_simple_list(_Ol, self._try_parse_ol_item)

    _literal_pat = re.compile(r'[\([{]?`[^`]*`\S*')
    _word_pat = re.compile(r'(.+?)(?=[\([{]?`| |$)')

    # Converts a paragraph text to a paragraph element containing
    # individual words.
    @staticmethod
    def _p_elem_from_text(text: str):
        elems: List[str] = []
        i = 0

        # scan the text
        while i < len(text):
            # literal?
            m = _Parser._literal_pat.match(text, i)

            if m:
                # literal
                elems.append(m.group(0))
            else:
                # word?
                m = _Parser._word_pat.match(text, i)

                if m:
                    # word
                    word = m.group(1).strip()

                    if len(word) >= 1:
                        elems.append(word)

            if m:
                i += len(m.group(0))

        return _P(elems)

    # Tries to parse a paragraph.
    #
    # Example:
    #
    #     Cliche poutine prism, freegan fixie tilde kogi iceland
    #     meditation. Hammock succulents godard kogi air plant Brooklyn
    #     pickled. Tofu disrupt poke four loko cronut sus shaman hell of
    #     food truck praxis wolf paleo fam.
    def _try_parse_p(self):
        lines: List[str] = []

        while not self._is_done:
            if (self._cur_line_is_empty or self._match_cur_line(self._bullet_line_pat) or
                                           self._match_cur_line(r'^\. \S.*')):
                # empty line or list item beginning: end of paragraph
                break

            lines.append(self._cur_line)
            self._goto_next_line()

        if len(lines) >= 1:
            # join lines with a single space
            return self._p_elem_from_text(' '.join(lines))

    # Tries to parse a break.
    def _try_parse_hr(self):
        if self._cur_line == '***' or self._match_cur_line(r'^┄{3,}$'):
            self._goto_next_line()
            return _Hr()

    # Tries to parse a prefixed blockquote.
    #
    # Example:
    #
    #     > Nisi incididunt labore pariatur qui eiusmod ut esse aute
    #     > commodo aute elit ut aliqua non mollit fugiat anim labore.
    #     >
    #     > Adipisicing sed pariatur ad ut anim officia irure magna.
    def _try_parse_blockquote_prefixed(self):
        lines: List[str] = []

        while not self._is_done:
            if self._cur_line == '>':
                # keep empty line
                lines.append('')
                self._goto_next_line()
                continue

            if self._cur_line.startswith('> '):
                # content line
                lines.append(self._cur_line[2:])
                self._goto_next_line()
                continue

            break

        # create element from content lines
        if len(lines) >= 1:
            return _Blockquote(_Parser(lines).elems)

    # Tries to parse a blockquote delimited with `>>>`.
    #
    # Example:
    #
    #     >>>
    #     Lincoln was born into poverty in a log cabin in Kentucky and
    #     was raised on the frontier, mainly in Indiana.
    #
    #     He was self-educated and became a lawyer,
    #     Whig Party leader,
    #     Illinois state legislator,
    #     and U.S. representative from Illinois.
    #     >>>
    def _try_parse_blockquote_delim(self):
        lines = self._try_parse_delim_block('>>>')

        if lines is not None:
            return _Blockquote(_Parser(lines).elems)

    _verbatim_line_pat = re.compile(r'^(?: *\[\d+\]: [hf]|[│┃┆┇┊┋┌┍┎┏└┕┖┗├┝┞┟┠┡┢┣╎╏║╒╓╔╘╙╚╞╟╠╽╿]).+')

    # Tries to parse a verbatim block.
    def _try_parse_verbatim(self):
        lines: List[str] = []

        while not self._is_done and self._match_cur_line(self._verbatim_line_pat):
            lines.append(self._cur_line)
            self._goto_next_line()

        if len(lines) >= 1:
            return _Verbatim(lines)

    # Tries to parse an admonition box delimited with `!!!`.
    #
    # Example:
    #
    #     !!!
    #     IMPORTANT: Be aware of the changing tides and strong currents that
    #     can swiftly turn a peaceful day at
    #     the beach into a dangerous
    #     situation.
    #
    #     Before taking a dip,
    #     make sure to check the local tide
    #     schedules and swim
    #     in designated areas with lifeguards present.
    #     !!!
    def _try_parse_admon_box_delim(self):
        lines = self._try_parse_delim_block('!!!')

        if lines is not None:
            return _AdmonBox(_Parser(lines).elems)

    # Tries to parse an admonition box.
    #
    # Example:
    #
    #     ┌────────────────────────────────────────────────────────────────────┐
    #     │ IMPORTANT: Be aware of the changing tides and strong currents that │
    #     │ can swiftly turn a peaceful day at the beach into a dangerous      │
    #     │ situation.                                                         │
    #     │                                                                    │
    #     │ Before taking a dip, make sure to check the local tide             │
    #     │ schedules and swim in designated areas with lifeguards present.    │
    #     └────────────────────────────────────────────────────────────────────┘
    def _try_parse_admon_box(self):
        if not self._cur_line.startswith('┌'):
            return

        if not self._match_next_line(r'^│ (?:CAUTION|IMPORTANT|NOTE|TIP|WARNING): '):
            return

        self._goto_next_line()

        lines: List[str] = []

        while not self._is_done:
            if self._match_cur_line(r'^└'):
                # ignore and we're done
                self._goto_next_line()
                break

            if self._match_cur_line(r'^│?\s*$'):
                # keep empty line
                lines.append('')
                self._goto_next_line()
                continue

            m = self._match_cur_line(r'[│ ] ([^│]*)')

            if m:
                lines.append(m.group(1).rstrip())

            self._goto_next_line()

        return _AdmonBox(_Parser(lines).elems)

    # Parses the whole lines to produce the resulting
    # elements `self._elems`.
    def _parse(self):
        funcs = [
            self._try_parse_h1,
            self._try_parse_h2,
            self._try_parse_ul,
            self._try_parse_ol,
            self._try_parse_dl,
            self._try_parse_pre_delim,
            self._try_parse_pre_indented,
            self._try_parse_hr,
            self._try_parse_blockquote_delim,
            self._try_parse_blockquote_prefixed,
            self._try_parse_admon_box_delim,
            self._try_parse_admon_box,
            self._try_parse_verbatim,
            self._try_parse_p,
        ]

        while True:
            # skip initial empty lines
            self._skip_empty_lines()

            if self._is_done:
                break

            # try each parsing function
            for func in funcs:
                elem = func()

                if elem is not None:
                    self._elems.append(elem)
                    break


# Formats a list of elements to lines of text considering some maximum
# line length to honor.
class _Formatter:
    def __init__(self, elems: List[_Elem], max_line_len: int,
                 cur_ul_level: int = -1, cur_ol_level: int = -1):
        self._max_line_len = max_line_len
        self._cur_ul_level = cur_ul_level
        self._cur_ol_level = cur_ol_level
        self._lines = self._elems_lines(elems)

    @property
    def lines(self):
        return self._lines

    # Formats the lines of the elements `elems` using the maximum line
    # length `max_line_len`.
    def _format_elems(self, elems: List[_Elem], max_line_len: int):
        return _Formatter(elems, max_line_len, self._cur_ul_level, self._cur_ol_level).lines

    # Formats the lines of the elements `elems`, indenting them with
    # `indent_len` spaces.
    def _format_elems_indented(self, elems: List[_Elem], indent_len: int):
        lines = self._format_elems(elems, self._max_line_len - indent_len)

        for i, line in enumerate(lines):
            if len(line) >= 1:
                lines[i] = f'{" " * indent_len}{line}'

        return lines

    @staticmethod
    def _p_line_list_len(lst: List[str]):
        return sum([len(t) for t in lst])

    # Returns the lines of the paragraph `p`.
    def _p_lines(self, p: _P):
        lines: List[List[str]] = [[]]

        # append each word, wrapping when necessary
        for word in p.words:
            to_append = f'{word} '

            if len(lines[-1]) == 0:
                # first word of the line, in case it doesn't fit
                lines[-1].append(to_append)
            elif self._p_line_list_len(lines[-1]) + len(word) > self._max_line_len:
                # new line
                lines.append([to_append])
            else:
                # append to current line
                lines[-1].append(to_append)

        # avoid runt: if there are at least two lines and the last line
        # contains a single word when two would fit, then just do it:
        # this is more readable than a single word on the last line
        if len(lines) >= 2 and len(lines[-1]) == 1 and len(lines[-2][-1]) + len(lines[-1][0]) - 1 <= self._max_line_len:
            lines[-1] = [lines[-2][-1], lines[-1][0]]
            del lines[-2][-1]

        # convert to real lines
        new_lines = list(map(lambda words: ''.join(words), lines))

        # remove trailing empty lines
        new_lines = _remove_trailing_empty_lines(new_lines)

        # append final empty line and return lines
        new_lines.append('')
        return new_lines

    # Returns the lines of the unordered list item `item`.
    def _ul_item_lines(self, item: _SimpleListItem):
        # get indented element lines
        lines = self._format_elems_indented(item.elems, 2)

        # insert bullet point
        bullet = ['•', '‣', '⁃'][self._cur_ul_level % 3]
        lines[0] = f'{bullet} {lines[0][2:]}'

        # remove trailing empty lines
        lines = _remove_trailing_empty_lines(lines)

        # append final empty line and return lines
        lines.append('')
        return lines

    # Returns a new list of lines, each line transformed with `func`.
    @staticmethod
    def _new_lines(lines: List[str], func: Callable[[str], str]) -> List[str]:
        return list(map(func, lines))

    # Removes empty lines from the simple list lines `lines`, except the
    # last one, to make the list compact if there are only single-line
    # items.
    #
    # Returns the result.
    @staticmethod
    def _compact_list(lst: _SimpleList, lines: List[str]):
        if len(lines) == 2 * len(lst.items):
            new_lines = list(filter(lambda line: len(line.strip()) >= 1, lines))

            # reappend final empty line and return result
            new_lines.append('')
            return new_lines

        return lines

    # Returns the lines of the unordered list `ul`.
    def _ul_lines(self, ul: _Ul):
        lines: List[str] = []
        self._cur_ul_level += 1

        for item in ul.items:
            lines += self._ul_item_lines(item)

        self._cur_ul_level -= 1

        # special case to make the list compact if there are only
        # single-line items
        lines = self._compact_list(ul, lines)

        # done
        return lines

    # Makes an ordered list item number based on the current ordered
    # list level.
    def _make_ol_item_num(self, ol: _Ol, index: int):
        if self._cur_ol_level % 2 == 0:
            max_num_width = len(f'{len(ol.items) - 1}')
            return f'{{:>{max_num_width}}}.'.format(index + 1)

        return f'{chr(ord("a") + (index % 26))})'

    # Returns the lines of the ordered list item `item`.
    def _ol_item_lines(self, ol: _Ol, index: int, item: _SimpleListItem):
        num = self._make_ol_item_num(ol, index)

        # get indented element lines
        indent_len = len(num) + 1
        lines = self._format_elems_indented(item.elems, indent_len)

        # insert number
        lines[0] = f'{num} {lines[0][indent_len:]}'

        # remove trailing empty lines
        lines = _remove_trailing_empty_lines(lines)

        # append final empty line and return lines
        lines.append('')
        return lines

    # Returns the lines of the ordered list `ol`.
    def _ol_lines(self, ol: _Ol):
        lines: List[str] = []
        self._cur_ol_level += 1

        for index, item in enumerate(ol.items):
            lines += self._ol_item_lines(ol, index, item)

        self._cur_ol_level -= 1

        # special case to make the list compact if there are only
        # single-line items
        lines = self._compact_list(ol, lines)

        # done
        return lines

    # Returns the lines of the definition list item `item`.
    def _dl_item_lines(self, item: _DlItem):
        # start with term lines
        lines = self._new_lines(item.terms, lambda line: f'{line}:')

        # get indented element lines
        lines += self._format_elems_indented(item.elems, 4)

        # remove trailing empty lines
        lines = _remove_trailing_empty_lines(lines)

        # append final empty line and return lines
        lines.append('')
        return lines

    # Returns the lines of the definition list `dl`.
    def _dl_lines(self, dl: _Dl):
        lines: List[str] = []

        for item in dl.items:
            lines += self._dl_item_lines(item)

        return lines

    # Returns the lines of the preformatted text block `pre`.
    def _pre_lines(self, pre: _Pre):
        return self._new_lines(pre.lines, lambda line: f'    {line}') + ['']

    # Returns the lines of the verbatim block `verbatim`.
    def _verbatim_lines(self, verbatim: _Verbatim):
        return verbatim.lines.copy()

    # Returns the lines of a break.
    def _hr_lines(self, _: _Hr):
        return ['┄' * (self._max_line_len), '']

    # Returns the lines of a blockquote.
    def _blockquote_lines(self, bq: _Blockquote):
        # get indented element lines
        lines = self._format_elems_indented(bq.elems, 2)

        # remove trailing empty lines
        lines = _remove_trailing_empty_lines(lines)

        # insert `>` prefix
        for index in range(len(lines)):
            lines[index] = f'> {lines[index][2:]}'

        # append final empty line and return lines
        lines.append('')
        return lines

    # Returns the lines of an admonition box.
    def _admon_box_lines(self, admon_box: _AdmonBox):
        # get element lines
        content_lines = self._format_elems(admon_box.elems, self._max_line_len - 4)

        # find longest line
        longest_content_line_len = len(max(content_lines,
                                           key=lambda line: len(line)))

        # build top of the box
        lines = [f'┌─{"─" * longest_content_line_len}─┐']

        # build body of the box
        for content_line in content_lines:
            lines.append(f'│ {content_line.ljust(longest_content_line_len)} │')

        # build bottom of the box
        lines.append(f'└─{"─" * longest_content_line_len}─┘')

        # append final empty line and return lines
        lines.append('')
        return lines

    # Returns the lines of the heading text `text` using the underlining
    # character `underline_ch`.
    @staticmethod
    def _heading_lines(text: str, underline_ch: str):
        assert len(underline_ch) == 1
        return [text, underline_ch * len(text)]

    # Returns the lines of the first level heading `h1`.
    def _h1_lines(self, h1: _H1):
        return self._heading_lines(h1.text.upper(), '━')

    # Returns the lines of the level 2 heading `h2`.
    def _h2_lines(self, h2: _H2):
        return self._heading_lines(h2.text, '─')

    # Returns the lines of the element `elem`.
    def _elem_lines(self, elem: _Elem) -> List[str]:
        funcs: Dict[Type[_Elem], Callable[[Any], List[str]]] = {
            _P: self._p_lines,
            _Ul: self._ul_lines,
            _Ol: self._ol_lines,
            _Dl: self._dl_lines,
            _H1: self._h1_lines,
            _H2: self._h2_lines,
            _Pre: self._pre_lines,
            _Hr: self._hr_lines,
            _Blockquote: self._blockquote_lines,
            _Verbatim: self._verbatim_lines,
            _AdmonBox: self._admon_box_lines,
        }

        return funcs[type(elem)](elem)

    # Returns the lines of the elements `elems`.
    def _elems_lines(self, elems: List[_Elem]):
        lines: List[str] = []

        for elem in elems:
            lines += self._elem_lines(elem)

        # right-strip all lines
        lines = self._new_lines(lines, lambda line: line.rstrip())

        # remove trailing empty lines and return them
        lines = _remove_trailing_empty_lines(lines)
        return lines


# Returns the beautified raw comment text `text` to fit on
# `max_line_len` columns.
#
# `text` is raw in that it must not contain special block comment
# characters, just raw text.
#
# Use format_c_block_comment() or format_prefixed_block_comment() to
# format a complete C/C++ or prefixed block comment.
def format(text: str, max_line_len: int = 72):
    return '\n'.join(_Formatter(_Parser(text.splitlines()).elems,
                                max_line_len).lines)


# Returns the beautified version of the C/C++ block comment text `text`
# to fit on `max_line_len` columns.
#
# The comment text is everything between `/*` and `*/`, where the column
# of `/*` within its original document is `start_col`.
#
# The whole `comment` string must have a format such as this:
#
#     /*
#      * Hello world.
#      * ===
#      *
#      * * Cupidatat in elit irure.
#      * * Qui sint.
#      *
#      * Sunt tempor cillum ut sint.
#      */
#
# The leading ` * ` strings (from `start_col` on each line) are
# important.
#
# Raises `ValueError` if `comment` doesn't contain a valid C/C++ block
# comment.
def format_c_block_comment(comment: str, start_col: int = 0,
                           max_line_len: int = 72):
    # extract content lines from comment string
    comment_lines = comment.splitlines()
    content_lines: List[str] = []
    line_pat = re.compile(r'\s*\* (.+)')

    for comment_line in comment_lines:
        comment_line = comment_line.strip()

        if comment_line in ('/*', '*/'):
            continue

        if comment_line == '*':
            # keep empty line
            content_lines.append('')
            continue

        m = line_pat.match(comment_line)

        if not m:
            raise ValueError(comment_line)

        content_lines.append(m.group(1))

    # format contents of comment
    new_content_lines = _Formatter(_Parser(content_lines).elems,
                                   max_line_len - start_col - 3).lines

    # create and return final comment
    new_comment_lines = ['/*']
    indent_str = _indent_str(start_col)
    new_comment_lines += list(map(lambda rline: f'{indent_str} * {rline}'.rstrip(),
                                  new_content_lines))
    new_comment_lines.append(f'{indent_str} */')
    return '\n'.join(new_comment_lines)


# Returns the beautified version of the prefixed block comment text
# `text` to fit on `max_line_len` columns.
#
# `prefix` is the block comment prefix. For example, it's `# ` for
# Python.
#
# The whole `comment` string must have a format such as this (example
# with the Python prefix):
#
#     # Hello world.
#     # ===
#     #
#     # * Cupidatat in elit irure.
#     # * Qui sint.
#     #
#     # Sunt tempor cillum ut sint.
#
# Each line must start with `prefix` at the column `start_col`.
#
# Raises `ValueError` if `comment` doesn't contain a valid prefixed
# block comment.
def format_prefixed_block_comment(comment: str, start_col: int = 0,
                                  max_line_len: int = 72, prefix: str = '# '):
    # extract content lines from comment string
    comment_lines = comment.splitlines()
    content_lines: List[str] = []
    s_prefix = prefix.rstrip()
    line_pat = re.compile(fr'\s*{re.escape(prefix)}(.+)')

    for comment_line in comment_lines:
        comment_line = comment_line.strip()

        if comment_line == s_prefix:
            # keep empty line
            content_lines.append('')
            continue

        m = line_pat.match(comment_line)

        if not m:
            raise ValueError(comment_line)

        content_lines.append(m.group(1))

    # format contents of comment
    new_content_lines = _Formatter(_Parser(content_lines).elems,
                                   max_line_len - start_col - len(prefix)).lines

    # create and return final comment
    new_comment_lines: List[str] = []
    indent_str = _indent_str(start_col)
    new_comment_lines += list(map(lambda rline: f'{indent_str}{prefix}{rline}'.rstrip(),
                                  new_content_lines))
    return '\n'.join(new_comment_lines)
