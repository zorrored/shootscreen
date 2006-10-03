#!/usr/bin/python
# pep8.py - Check Python source code formatting, according to PEP 8
# Copyright (C) 2006 Johann C. Rocholl <johann@browsershots.org>
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""
Check Python source code formatting, according to PEP 8:
http://www.python.org/dev/peps/pep-0008/

A tool to automatically check your Python code against some of the
coding conventions in PEP 8 (Style Guide for Python Code). The
architecture of pep8.py makes it very easy to add more checks. The
output is parseable to let your editor jump directly to the position
of each error.

This tool is not a complete implementation of all the recommendations
in PEP 8. Many parts of PEP 8 are impossible to check automatically.
Even of the possible parts, this early version of pep8.py checks only
a small subset.

For usage and a list of options, try this:
$ python pep8.py -h

Groups of errors and warnings:
E100 indentation
E200 whitespace
E300 blank lines
E400 imports
E500 line length

This program and its regression test suite live here:
http://svn.browsershots.org/trunk/devtools/pep8/
http://trac.browsershots.org/browser/trunk/devtools/pep8/

You can add checks to this program simply by adding a new check
function. All checks operate on single lines, either physical or
logical.

Physical line:
- Raw line of text from the input file.

Logical line:
- Multi-line statements converted to a single line.
- Stripped left and right.
- Contents of strings replaced with 'xxx' of same length.
- Comments removed.

The check function requests physical or logical lines by the name of
the first argument:

def maximum_line_length(physical_line)
def indentation(logical_line, state, indent_level)

The second example above demonstrates how check functions can request
additional information with extra arguments. All attributes of the
Checker instance are available. Some examples:

state: dictionary for passing information across lines
indent_level: indentation (with tabs expanded to the next multiple of 8)

The docstring of each check function shall be the respective part of
text from PEP 8. It is printed if the user enables --show-pep8.
"""

import os
import sys
import inspect
import re
import tokenize
from optparse import OptionParser
from keyword import iskeyword
from fnmatch import fnmatch

__version__ = '0.2.0'
__revision__ = '$Rev$'

default_exclude = '.svn,CVS,*.pyc,*.pyo'

indent_match = re.compile(r'([ \t]*)').match
last_token_match = re.compile(r'(\w+|\S)\s*$').search

operators = """
+  -  *  /  %  ^  &  |  =  <  >  >>  <<
+= -= *= /= %= ^= &= |= == <= >= >>= <<=
!= <> :
in is or not and
""".split()

options = None


##############################################################################
# Various checks for physical lines
##############################################################################


def tabs_or_spaces(physical_line, state):
    """
    Never mix tabs and spaces.

    The most popular way of indenting Python is with spaces only.  The
    second-most popular way is with tabs only.  Code indented with a mixture
    of tabs and spaces should be converted to using spaces exclusively.  When
    invoking the Python command line interpreter with the -t option, it issues
    warnings about code that illegally mixes tabs and spaces.  When using -tt
    these warnings become errors.  These options are highly recommended!
    """
    indent = indent_match(physical_line).group(1)
    if not indent:
        return
    if 'indent_char' in state:
        indent_char = state['indent_char']
    else:
        indent_char = indent[0]
        state['indent_char'] = indent_char
    for offset, char in enumerate(indent):
        if char != indent_char:
            return offset, "E101 indentation contains mixed spaces and tabs"


def tabs_obsolete(physical_line):
    """
    For new projects, spaces-only are strongly recommended over tabs.  Most
    editors have features that make this easy to do.
    """
    indent = indent_match(physical_line).group(1)
    if indent.count('\t'):
        return indent.index('\t'), "W191 indentation contains tabs"


def trailing_whitespace(physical_line):
    """
    JCR: Trailing whitespace is superfluous.
    """
    physical_line = physical_line.rstrip('\n') # chr(10), newline
    physical_line = physical_line.rstrip('\r') # chr(13), carriage return
    physical_line = physical_line.rstrip('\x0c') # chr(12), form feed, ^L
    stripped = physical_line.rstrip()
    if physical_line != stripped:
        return len(stripped), "W291 trailing whitespace"


def maximum_line_length(physical_line):
    """
    Limit all lines to a maximum of 79 characters.

    There are still many devices around that are limited to 80 character
    lines; plus, limiting windows to 80 characters makes it possible to have
    several windows side-by-side.  The default wrapping on such devices looks
    ugly.  Therefore, please limit all lines to a maximum of 79 characters.
    For flowing long blocks of text (docstrings or comments), limiting the
    length to 72 characters is recommended.
    """
    length = len(physical_line.rstrip())
    if length > 79:
        return 79, "E501 line too long (%d characters)" % length


##############################################################################
# Various checks for logical lines
##############################################################################


def indentation(logical_line, state, indent_level):
    """
    Use 4 spaces per indentation level.

    For really old code that you don't want to mess up, you can continue to
    use 8-space tabs.
    """
    line = logical_line
    if line == '':
        return
    previous_level = state.get('indent_level', 0)
    indent_expect = state.get('indent_expect', False)
    state['indent_expect'] = line.rstrip('#').rstrip().endswith(':')
    indent_char = state.get('indent_char', ' ')
    state['indent_level'] = indent_level
    if indent_char == ' ' and indent_level % 4:
        return 0, "E111 indentation is not a multiple of four"
    if indent_expect and indent_level <= previous_level:
        return 0, "E112 expected an indented block"
    if not indent_expect and indent_level > previous_level:
        return 0, "E113 unexpected indentation"


def blank_lines(logical_line, state, indent_level):
    """
    Separate top-level function and class definitions with two blank lines.

    Method definitions inside a class are separated by a single blank line.

    Extra blank lines may be used (sparingly) to separate groups of related
    functions.  Blank lines may be omitted between a bunch of related
    one-liners (e.g. a set of dummy implementations).

    Use blank lines in functions, sparingly, to indicate logical sections.
    """
    line = logical_line
    first_line = 'blank_lines' not in state
    count = state.get('blank_lines', 0)
    if line == '':
        state['blank_lines'] = count + 1
    else:
        state['blank_lines'] = 0
    if line.startswith('def ') and not first_line:
        if indent_level > 0 and count != 1:
            return 0, "E301 expected 1 blank line, found %d" % count
        if indent_level == 0 and count != 2:
            return 0, "E302 expected 2 blank lines, found %d" % count
    if count > 2:
        return 0, "E303 too many blank lines (%d)" % count


def extraneous_whitespace(logical_line):
    """
    Avoid extraneous whitespace in the following situations:

    - Immediately inside parentheses, brackets or braces.

    - Immediately before a comma, semicolon, or colon.
    """
    line = logical_line
    for char in '([{':
        found = line.find(char + ' ')
        if found > -1:
            return found + 1, "E201 whitespace after '%s'" % char
    for char in '}])':
        found = line.find(' ' + char)
        if found > -1 and line[found - 1] != ',':
            return found, "E202 whitespace before '%s'" % char
    for char in ',;:':
        found = line.find(' ' + char)
        if found > -1:
            return found, "E203 whitespace before '%s'" % char


def whitespace_before_parameters(logical_line):
    """
    Avoid extraneous whitespace in the following situations:

    - Immediately before the open parenthesis that starts the argument
      list of a function call.

    - Immediately before the open parenthesis that starts an indexing or
      slicing.
    """
    line = logical_line
    for char in '([':
        found = -1
        while True:
            found = line.find(' ' + char, found + 1)
            if found == -1:
                break
            before = last_token_match(line[:found]).group(1)
            if (before in operators or
                before == ',' or
                iskeyword(before) or
                line.startswith('class')):
                continue
            return found, "E211 whitespace before '%s'" % char


def whitespace_around_operator(logical_line):
    """
    Avoid extraneous whitespace in the following situations:

    - More than one space around an assignment (or other) operator to
      align it with another.
    """
    line = logical_line
    for operator in operators:
        found = line.find('  ' + operator)
        if found > -1:
            return found, "E221 multiple spaces before operator"
        found = line.find('\t' + operator)
        if found > -1:
            return found, "E222 tab before operator"


def imports_on_separate_lines(logical_line):
    """
    Imports should usually be on separate lines.
    """
    line = logical_line
    if line.startswith('import '):
        found = line.find(',')
        if found > -1:
            return found, "E401 multiple imports on one line"


##############################################################################
# Helper functions
##############################################################################


def get_indent(line):
    """
    Return the amount of indentation.
    Tabs are expanded to the next multiple of 8.

    >>> get_indent('    abc')
    4
    >>> get_indent('\\tabc')
    8
    >>> get_indent('    \\tabc')
    8
    >>> get_indent('       \\tabc')
    8
    >>> get_indent('        \\tabc')
    16
    """
    result = 0
    for char in line:
        if char == '\t':
            result = result / 8 * 8 + 8
        elif char == ' ':
            result += 1
        else:
            break
    return result


##############################################################################
# Framework to run all checks
##############################################################################


def message(text):
    """Print a message."""
    # print >> sys.stderr, options.prog + ': ' + text
    # print >> sys.stderr, text
    print text


def find_checks(argument_name):
    """
    Find all globally visible functions where the first argument name
    starts with argument_name.
    """
    checks = []
    function_type = type(find_checks)
    for name, function in globals().iteritems():
        if type(function) is function_type:
            args = inspect.getargspec(function)[0]
            if len(args) >= 1 and args[0].startswith(argument_name):
                checks.append((name, function, args))
    checks.sort()
    return checks


def ignore_code(code):
    """
    Check if options.ignore contains a prefix of the error code.
    """
    for ignore in options.ignore:
        if code.startswith(ignore):
            return True


def mute_line(line, line_number, tokens):
    for token_type, token, token_start, token_end, token_line in tokens:
        if token_start[0] <= line_number <= token_end[0]:
            if token_type == tokenize.COMMENT:
                # Strip comments
                line = line[:token_start[1]].rstrip()
            elif token_type == tokenize.STRING:
                # Replace strings with 'xxx'
                string_start = token_start[1] + 1
                string_end = token_end[1] - 1
                if token.startswith('"""') or token.startswith("'''"):
                    string_start += 2
                    string_end -= 2
                if line_number > token_start[0]:
                    string_start = 0
                if line_number < token_end[0]:
                    string_end = len(line)
                line = (line[:string_start] +
                        'x' * (string_end - string_start) +
                        line[string_end:])
    return line


class Checker:

    def __init__(self, filename):
        self.filename = filename
        self.lines = file(filename).readlines()
        self.physical_checks = find_checks('physical_line')
        self.logical_checks = find_checks('logical_line')

    def readline(self):
        self.line_number += 1
        if self.line_number > len(self.lines):
            return ''
        return self.lines[self.line_number - 1]

    def readline_check_physical(self):
        line = self.readline()
        self.check_physical(line)
        return line

        for start_offset, original_number, indent in location:
            if offset >= start_offset:
                subline_indent = indent
                subline_start = start_offset
                subline_offset = offset - start_offset + indent
                subline_number = original_number
        subline_end = len(line)
        for index in range(1, len(location)):
            if location[index - 1][0] == subline_start:
                subline_end = location[index][0]
        subline = ' ' * subline_indent + line[subline_start:subline_end]
        return subline_number, subline_offset, subline

    def run_check(self, check, argument_names):
        arguments = []
        for name in argument_names:
            arguments.append(getattr(self, name))
        return check(*arguments)

    def check_physical(self, line):
        self.physical_line = line
        for name, check, argument_names in self.physical_checks:
            result = self.run_check(check, argument_names)
            if result is not None:
                offset, text = result
                self.report_error(self.line_number, offset, text, check)

    def check_logical(self, start, end, tokens):
        # print start, '-', end
        mapping = []
        logical = ''
        for line_number in range(start[0], end[0] + 1):
            line = self.lines[line_number - 1].rstrip()
            line = mute_line(line, line_number, tokens)
            if line:
                before = len(line)
                line = line.lstrip()
                after = len(line)
                indent = before - after
                if line.endswith('\\'):
                    line = line[:-1]
                if logical.endswith(','):
                    logical += ' '
                mapping.append((len(logical), line_number, indent))
                logical += line
        self.indent_level = mapping[0][2]
        self.logical_line = logical
        for name, check, argument_names in self.logical_checks:
            result = self.run_check(check, argument_names)
            if result is not None:
                offset, text = result
                for map_offset, line_number, indent in mapping:
                    if offset >= map_offset:
                        original_number = line_number
                        original_indent = indent
                        original_offset = offset - map_offset
                self.report_error(original_number, original_offset,
                                  text, check)

    def check_all(self):
        start = None
        tokens = []
        parens = 0
        self.line_number = 0
        self.error_count = {}
        self.state = {}
        for token in tokenize.generate_tokens(self.readline_check_physical):
            # print tokenize.tok_name[token_type], repr(token)
            tokens.append(token)
            token_type, token_string, token_start, token_end, line = token
            if start is None:
                start = token_start
            if token_type == tokenize.OP and token_string in '([{':
                parens += 1
            if token_type == tokenize.OP and token_string in '}])':
                parens -= 1
            if token_type == tokenize.NEWLINE and not parens:
                end = token_end
                self.check_logical(start, end, tokens)
                start = None
                tokens = []
        return self.error_count

    def report_error(self, line_number, offset, text, check):
        """
        Report an error, according to options.
        """
        if options.quiet == 1 and not self.error_count:
            message(self.filename)
        code = text[:4]
        count_text = text
        if text.endswith(')'):
            # remove actual values, e.g. '(86 characters)'
            found = count_text.rfind('(')
            if found > -1:
                count_text = count_text[:found].rstrip()
        self.error_count[count_text] = self.error_count.get(count_text, 0) + 1
        if options.quiet:
            return
        if options.testsuite:
            base = os.path.basename(self.filename)[:4]
            if base == code:
                return
            if base[0] == 'E' and code[0] == 'W':
                return
        if ignore_code(code):
            return
        message("%s:%s:%d: %s" %
                (self.filename, line_number, offset + 1, text))
        if options.show_source:
            line = self.lines[line_number - 1]
            message(line)
            message(' ' * offset + '^')
        if options.show_pep8:
            message(check.__doc__.lstrip('\n').rstrip())


def input_file(filename):
    """
    Run all checks on a Python source file.
    """
    if options.verbose:
        message('checking ' + filename)
    error_count = Checker(filename).check_all()
    if options.testsuite and not error_count:
        message("%s: %s" % (filename, "no errors found"))
    return error_count


def input_dir(dirname):
    """
    Check all Python source files in this directory and all subdirectories.
    """
    error_count = {}
    dirname = dirname.rstrip('/')
    if excluded(dirname):
        return
    for root, dirs, files in os.walk(dirname):
        if options.verbose:
            message('directory ' + root)
        dirs.sort()
        for subdir in dirs:
            if excluded(subdir):
                dirs.remove(subdir)
        files.sort()
        for filename in files:
            if not excluded(filename):
                file_errors = input_file(os.path.join(root, filename))
                add_error_count(error_count, file_errors)
    if options.statistics:
        codes = error_count.keys()
        codes.sort()
        for code in codes:
            print '%-7s %s' % (error_count[code], code)


def add_error_count(error_count, file_errors):
    for code in file_errors:
        error_count[code] = (error_count.get(code, 0) + file_errors[code])


def excluded(filename):
    for pattern in options.exclude:
        if fnmatch(filename, pattern):
            return True


def _main():
    """
    Parse command line options and run checks on Python source.
    """
    global options
    usage = "%prog [options] input ..."
    parser = OptionParser(usage)
    parser.add_option('-v', '--verbose', default=0, action='count',
                      help="print status messages, or debug with -vv")
    parser.add_option('-q', '--quiet', default=0, action='count',
                      help="report only file names, or nothing with -qq")
    parser.add_option('--exclude', metavar='dirs', default=default_exclude,
                      help="skip some entries (default %s)" % default_exclude)
    parser.add_option('--ignore', metavar='errors', default='',
                      help="e.g. E4,W for imports and all warnings")
    parser.add_option('--show-source', action='store_true',
                      help="show source code for each error")
    parser.add_option('--show-pep8', action='store_true',
                      help="show text of PEP 8 for each error")
    parser.add_option('--statistics', action='store_true',
                      help="show how often each error was found")
    parser.add_option('--testsuite', metavar='dir',
                      help="run regression tests from dir")
    parser.add_option('--doctest', action='store_true',
                      help="run doctest on myself")
    options, args = parser.parse_args()
    if options.doctest:
        import doctest
        return doctest.testmod()
    if options.testsuite:
        args.append(options.testsuite)
    if len(args) == 0:
        parser.error('input not specified')
    options.prog = os.path.basename(sys.argv[0])
    options.exclude = options.exclude.split(',')
    for index in range(len(options.exclude)):
        options.exclude[index] = options.exclude[index].rstrip('/')
    if options.ignore:
        options.ignore = options.ignore.split(',')
    else:
        options.ignore = []
    # print options.exclude, options.ignore
    for path in args:
        if os.path.isdir(path):
            input_dir(path)
        else:
            input_file(path)


if __name__ == '__main__':
    _main()
