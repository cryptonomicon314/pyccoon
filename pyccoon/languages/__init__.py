# -*- coding: utf-8 -*-

import re
import os

import pygments
from pygments import lexers, formatters

from markdown import markdown
from .. import markdown_extensions

from ..utils import cached_property
from .utils import Section, ParsingStrategy, iterate_sections,\
    split_section_by_regex, split_code_by_pos


default_markdown_extensions = [
    markdown_extensions.LinesConnector(),
    markdown_extensions.SaneDefList(),
    markdown_extensions.Todo(),
    markdown_extensions.Pydoc(),
    markdown_extensions.AutoLinkExtension(),
    markdown_extensions.MathExtension(),
    "markdown.extensions.def_list",
    "markdown.extensions.fenced_code",
    'markdown.extensions.codehilite',
    'markdown.extensions.tables'
  ]


class Language(object):
    """
    ## Pyccoon Language definition

    This class governs all source file parsing routines. Due to differences in programming \
    languages, an extensible parsing `strategy` is required \
    (see [[./utils.py#parsing-strategy]])
    """

    extensions = []
    scope_keywords = []
    filename_substitutes = {}
    markdown_extensions = default_markdown_extensions
    postprocessors = []
    preprocessors = []
  
    
    @property
    def name(self):
        return self.__class__.__name__

    @cached_property
    def lexer(self):
        """ Pygments lexer corresponding to the language """
        return lexers.get_lexer_by_name(self.name.lower())

    def highlight(self, code, formatter="html"):
        """ Use pygments to highlight the `code` """
        return pygments.highlight(
            code, self.lexer,
            formatters.get_formatter_by_name(formatter)
        )

    def markdown(self, docs):
        return markdown(docs, extensions=self.markdown_extensions)

    def transform_filename(self, filename):
        """
        Filename transformation according to language specifics. If `filename_substitutes` are \
        defined, the filename can be replaced accordingly. For example, `Python` module's\
        `__init__.py` corresponds to the index file of the folder and should be turned into\
        `index.html`

        If no `filename_substitutes` declared, the filename extension will be replaced by `.html`.
        """
        if filename in self.filename_substitutes:
            return self.filename_substitutes[filename]

        for extension in self.extensions:
            if filename.endswith(extension):
                return filename + ".html"

        return filename

    def strategy(self):
        """ Language parsing strategy - i.e., a list of methods to be applied to the code \
            to derive a properly formatter set of docs-code sections """
        return ParsingStrategy(self.set_sections_levels, self.strip_docs_indentation,
                               self.set_sections_levels, self.merge_up,
                               self.set_sections_levels, self.merge_down,
                               self.set_sections_levels, self.absorb)

    def parse(self, code, add_lineno=True):
        """ Apply `self.strategy()` to the `code` """
        sections = [Section(code_text=code)]

        for method in self.strategy():
            sections = method(sections)

        # Strip empty sections
        sections = [section for section in sections if section.has_code() or section.has_docs()]

        return sections

    @iterate_sections(start=0)
    def debug_docs(self, sections, i):
        print(sections[i]['docs_text'])

    @iterate_sections(start=0)
    def debug_code(self, sections, i):
        print(sections[i]['code_text'])

    @iterate_sections(start=0)
    def set_sections_levels(self, sections, i):
        if sections[i]["code_text"]:
            indent = re.match(r"^([ \t]*)", sections[i]["code_text"]).group(1)
            sections[i]["level"] = len(indent)
        elif i > 0:
            sections[i]["level"] = sections[i-1]['level']

    @iterate_sections(start=0)
    def strip_docs_indentation(self, sections, i):
        indent = re.match(r"^([ \t]*)", sections[i]["docs_text"], re.M).group(1)

        sections[i]["docs_text"] = re.compile(r"^{0}".format(indent), re.M)\
            .sub("", sections[i]["docs_text"])

    @iterate_sections()
    def merge_up(self, sections, i):
        """ Suck up the documentation added right under the scope-defining lines (e.g., class or \
            function definition) """
        if not sections[i].has_code() and not sections[i-1].has_docs() and sections[i-1].has_code():

            prev_line = sections[i-1]["code_text"].strip().split("\n")[-1].strip()
            # If previous line of code contains one of the `scope_keywords` - merge last 2 sections
            if any([re.match(x, prev_line) for x in self.scope_keywords]):
                sections[i-1]["docs_text"] = sections[i]["docs_text"]
                sections[i:i + 1] = []

    @iterate_sections()
    def merge_down(self, sections, i):
        """ Merge the documentation placed above the code (just like the next comment) """

        # if there was no code, but were docs - merge
        if not sections[i-1].has_code() and sections[i-1].has_docs()\
                and not sections[i].has_docs() and sections[i].has_code():
            sections[i-1]["code_text"] = sections[i]["code_text"]
            sections[i-1]["scope"] = sections[i]["scope"] or sections[i-1]["scope"]
            sections[i:i+1] = []

    @iterate_sections()
    def absorb(self, sections, i):
        """ Absorb next code-only section if it lies deeper than the current one (that has docs)"""
        if not sections[i].has_docs() and sections[i]['level'] > sections[i-1]['level']:
            sections[i-1]['code_text'] = sections[i-1]['code_text'].rstrip('\n') \
                + '\n\n' + sections[i]['code_text'].lstrip('\n')
            sections[i:i+1] = []
    
    def postprocess(self, sections):
        for processor in self.postprocessors:
            processor(sections)
    
    def preprocess(self, sections):
        for processor in self.preprocessors:
            processor(sections)


class PlainText(Language):
    extensions = ['.txt']
    filename_substitutes = {
        'index.txt': 'index.html'
    }
    divider_text = divider_html = ""
    lexer = None

    def highlight(self, code):
        return code

    def parse(self, code, add_lineno=True):
        return [Section(docs_text=code)]

    def lexer(self):
        return None


class Markdown(PlainText):
    extensions = ['.md']
    filename_substitutes = {
        'index.md': 'index.html'
    }


class InlineCommentLanguage(Language):
    """
    ## Inline commenting mixins

    Language mixin for separate inline comments and whole stacks of them.
    """

    # The delimiter for inline comments; separates documentation from code.
    inline_delimiter = "#"
    # Some languages might have comments that are parsed by the compiler/interpreter.
    # They can be used to activate or deactivate special options,
    # or for debugging purposes.
    #
    # Usually those comments have specific patterns to distinguish them from
    # ordinary comments, which are ignored by the compiler.
    #
    # Property `ignored_inline_patterns` is a list of *regexp*s that
    # match the ignored comments for that language.
    ignored_inline_patterns = []

    def strategy(self):
        base_strategy = super(InlineCommentLanguage, self).strategy()
        base_strategy.insert(0, self.parse_inline)
        return base_strategy

    @cached_property
    def inline_prefix(self):
        return re.compile(r"^[ \t]*{0}".format(self.inline_delimiter), re.M)

    @cached_property
    def inline_re(self):
        """
            ^\s*{0}\s*(.+$)
            (^[ \t]*{0}(.*)$)+
        """
        # Ignored comments, as defined above, are comments that are to be treated
        # the same way as source code instead of documentation.
        #
        # To treat them as normal code, we simply add a regular expression that
        # matches whenever **none** of those patterns matches.
        # This way, lines that match the pattern will be treated as code instead
        # of documentation.
        if self.ignored_inline_patterns:
            # Build a *regexp* that matches whenever **none** of the patterns matches.
            # Only lines for which this *regexp* matches will be treated as documentation.
            # Lines for which it doesn't match will be treated as code.
            dont_match = r"(?!({0}))".\
                format("|".join(pattern for pattern in self.ignored_inline_patterns))
        # If no ignored comment patterns have been defined for the current language,
        # treat all comments as documentation.
        else:
            dont_match = ""
        # Whenever the text after the `self.inline_delimiter` matches the `dont_match` *regexp*,
        # treat the comment as documentation.
        return re.compile(r"((?:^[ \t]*{0}{1}.*\n)+)".format(self.inline_delimiter,
                                                             dont_match),
                          flags=re.M)

    @property
    def divider_text(self):
        # The dividing token we feed into Pygments, to delimit the boundaries between sections.
        return "\n{0}DIVIDER\n".format(self.inline_delimiter)

    @property
    def divider_html(self):
        # The mirror of `divider_text` that we expect Pygments to return. We can split \
        # on this to recover the original sections.
        return re.compile(r'\n*<span class="c[1]?">{0}DIVIDER</span>\n*'
                          .format(self.inline_delimiter))

    @iterate_sections(start=0)
    def parse_inline(self, sections, i):
        new_sections = split_section_by_regex(sections[i], self.inline_re)
        for j, section in enumerate(new_sections):
            if section.get("meta") != "stripped":
                new_sections[j]["docs_text"] = self.inline_prefix.sub("",
                                                                      new_sections[j]["docs_text"])
                new_sections[j]["meta"] = "stripped"

        sections[i:i+1] = new_sections
    

class MultilineCommentLanguage(Language):
    """
    ## Multiline commenting mixins

    Language mixin for multiline comments. Some languages also have another syntax entity\
    called "docblocks" - they probably should be treated separately, although they are usually\
    captured along with multiline comments.
    """

    multistart = '"""'
    multiend = '"""'
    multiline_ignore_start = None
    multiline_ignore_end = None

    @property
    def multiline_re(self):

        if self.multiline_ignore_start:
            dont_match_start = r"(?!{0})".format(self.multiline_ignore_start)
        else:
            dont_match_start = ""

        if self.multiline_ignore_end:
            dont_match_end = r"(?!{0})".format(self.multiline_ignore_end)
        else:
            dont_match_end = ""

        return re.compile(r'^(\s*{start}{dont_match_start}((?!{end})[\s\S])*){dont_match_end}{end}'\
                            .format(dont_match_start=dont_match_start,
                                    dont_match_end=dont_match_end,
                                    start=self.multistart,
                                    end=self.multiend),
                          flags=re.M)

    @property
    def multiline_delimiters(self):
        return [self.multistart, self.multiend]

    def strategy(self):
        base_strategy = super(MultilineCommentLanguage, self).strategy()
        base_strategy.insert(0, self.parse_multiline)
        return base_strategy

    @iterate_sections(start=0)
    def parse_multiline(self, sections, i):
        sections[i:i+1] = split_section_by_regex(sections[i], self.multiline_re,
                                                 meta="stripped")
        sections[i]["docs_text"] = re.sub(r"^\n*(\s*){0}".format(self.multistart),
                                          r"\1",
                                          sections[i]["docs_text"])


class DoubleQuoteDocstringLanguage(Language):
    """
    ## Docstring Base Language (Double Quotes)
    """

    @property
    def multiline_re(self):
        return re.compile(r'^(\s*"(?:[^"\\]|\\.)*)"(?=\n)', flags=re.M)

    def strategy(self):
        base_strategy = super(DoubleQuoteDocstringLanguage, self).strategy()
        base_strategy.insert(0, self.parse_multiline)
        return base_strategy


    @iterate_sections(start=0)
    def parse_multiline(self, sections, i):
        sections[i:i+1] = split_section_by_regex(sections[i], self.multiline_re,
                                                 meta="stripped")
        sections[i]["docs_text"] = re.sub(r'^\n*(\s*)"',
                                          r'\1',
                                          sections[i]["docs_text"])

        sections[i]["docs_text"] = re.sub(r'\\', '', sections[i]["docs_text"])



class IndentBasedLanguage(Language):

    """
    ## Mixins for indent-based languages (Python, Ruby, etc.)

    In indent-based languages it is quite easy to find a proper place to split the code section: \
    basically, whenever an indent of the line becomes smaller, than the indent of the first line \
    of the section - split up.

    TODO: Consider using some preprocessor instead of literal matching of the indentation. For \
        example, https://github.com/sirthias/parboiled/wiki/Indentation-Based-Grammars, \
        https://github.com/Cirru/cirru-parser
    """

    @iterate_sections(start=0)
    def split_by_scopes(self, sections, i):
        indent = re.match(r"^(\s*)", sections[i]["code_text"].strip("\n")).group(1)

        regex = re.compile(r"^(\s{{0,{0}}}\S)".format(len(indent) - 1), flags=re.M)
        match = regex.search(sections[i]["code_text"], pos=len(indent) + 1)

        if match:
            sections = split_code_by_pos(i, match.start(), sections)
            sections[i]['level'] = len(indent)
            sections[i+1]['level'] = len(match.group(1).strip("\n"))

        regex = re.compile(r"({0})".format("|".join(self.scope_keywords)), flags=re.M)
        match = regex.search(sections[i]["code_text"])

        if match and match.start() == 0:
            sections[i]['scope'] = match.group(1).strip()
            match = regex.search(sections[i]["code_text"], pos=match.start() + 1)

        if match:
            sections = split_code_by_pos(i, match.start(), sections)
            sections[i+1]['code_text'] = sections[i+1]['code_text'].strip('\n')
            sections[i+1]['scope'] = match.group(1).strip()

    def strategy(self):
        base_strategy = super(IndentBasedLanguage, self).strategy()
        base_strategy.insert_before('merge_up', self.split_by_scopes)
        return base_strategy


class KeywordLinksMixin(Language):
    
    def __init__(self):
        super(KeywordLinksMixin, self).__init__()
        self.postprocessors.append(self.link_source_post)
        self.postprocessors.append(self.add_section_anchors)
        self.preprocessors.append(self.link_source_pre)
    

    @iterate_sections(start=0)
    def add_links(self, sections, i):
        for link_pattern, formatter in self.keyword_link_patterns:
            match = re.match(link_pattern, sections[i]['code_text'])
            if match:
                anchor = formatter(match)
                sections[i]['source_section_anchor'] = anchor

    def strategy(self):
        base_strategy = super(KeywordLinksMixin, self).strategy()
        base_strategy.insert_after('absorb', self.add_links)
        return base_strategy

    def add_section_anchors(self, sections):
        for i, section in enumerate(sections):
            try:
                sections[i]['code_html'] = sections[i]['source_section_anchor'] + \
                                           sections[i]['code_html']
            except:
                print "no anchor"


# ## Mixins for brace-based languages (C/C++, JavaScript, PHP, etc.)

class BraceBasedLanguage(Language):

    @iterate_sections(start=0)
    def split_by_scopes(self, sections, i):
        """ Split the code sections by `scope_keywords` of the language
            TODO: consider splitting also by braces interiors"""

        regex = re.compile(r"^({0})".format("|".join(self.scope_keywords)), flags=re.M)
        match = regex.search(sections[i]["code_text"])

        if match and match.start() == 0:
            match = regex.search(sections[i]["code_text"], pos=match.start() + 1)

        if match:
            split_code_by_pos(i, match.start(), sections)
            sections[i+1]['code_text'] = sections[i+1]['code_text'].strip('\n')
            sections[i+1]['scope'] = match.group(2)

    def strategy(self):
        base_strategy = super(BraceBasedLanguage, self).strategy()
        base_strategy.insert_before('merge_up', self.split_by_scopes)
        return base_strategy


# ## Specific languages definitions

class C(BraceBasedLanguage, InlineCommentLanguage, MultilineCommentLanguage):
    """
    ### C/C++

    Styling of the C/C++ code is largely historical and oriented on reading hopelessly long codes\
    on the old terminal screens.

    TODO: detect whole style docs blocks, for example, boxes:

    ```c
        ////////////////////////////
        ////// Nice comment! ///////
        ////////////////////////////

        /***************************
        **** We love ASCII-art! ****
        ***************************/
    ```

    """
    extensions = [".c", ".cpp", ".h", ".cc"]
    inline_delimiter = "//"
    multistart = r"/\*+"
    multiend = r"\*+/"

    scope_keywords = [r"\s*({0}) \w+".format(word) for word in
                      ["class", "function", "namespace",
                       "public", "private", "protected", "abstract", "inline", "virtual",
                       "void", "int", "double", "bool",  "float"]]

    # FIXME: this redefinition brakes the whole extension
    #
    # ```python
    # def __init__(self, *args, **kwargs):
    #     super(C, self).__init__(*args, **kwargs)
    #     for i, ext in enumerate(self.markdown_extensions):
    #         if isinstance(ext, markdown_extensions.LineConnector):
    #             self.markdown_extensions[i] = \
    #                 markdown_extensions.LineConnector(regex=r"([\w\.])[ \t]*\n[ \t]*(\w)")
    # ```

    @iterate_sections(start=0)
    def strip_commenting_design(self, sections, i):
        sections[i]["docs_text"] = re.compile(r"^[ \t]*(\/+|\*+)(.*)$", re.M)\
            .sub(r"\2", sections[i]["docs_text"])

    def strategy(self):
        base_strategy = super(C, self).strategy()
        base_strategy.insert_before('strip_docs_indentation', self.strip_commenting_design)
        base_strategy.insert_after('strip_docs_indentation', self.split_by_scopes)
        return base_strategy


class JavaScript(C):
    """
    ### JavaScript
    JavaScript is largely identical to C/C++, although it has far less scope keywords and far more\
    flexibility in defining functions and objects.

    TODO: test function-defining scopes

    ```javascript
        function name(args) { ... }
        name = function(args) { ... }
    ```

    """

    extensions = [".js"]

    scope_keywords = [r"\s*(class)", r"^.*(function)[ \t]*\("]


class PHP(C):
    extensions = [".php"]

    def strategy(self):
        base_strategy = super(PHP, self).strategy()
        base_strategy.delete('merge_up')
        return base_strategy


class Python(IndentBasedLanguage, MultilineCommentLanguage, InlineCommentLanguage):
    """
    ### Python
    Obviously, Python language parsing is a best-developed part of Pyccoon.

    TODO: support also `'''` comment delimiters.
    """
    extensions = [".py", ".pyx"]
    inline_delimiter = "#"
    ignored_inline_patterns = [
        # Shebang patterns, e.g. `#!/usr/bin/python`
        r"(\!.+)",
        # File encoding, e.g. `# -*- coding: utf-8 -*-`
        r"((\s)*-\*-(\s)*coding:.+(\s*)-\*-)",
      ]

    multistart = '"""'
    multiend = '"""'

    # `__init__.py` files can perfectly serve as modules index files.
    filename_substitutes = {
        "__init__.py": "index.html"
    }

    scope_keywords = [r"^\s*(def) ", r"^\s*(class) ", r"^\s*(@)\w+"]

    def strategy(self):
        base_strategy = super(Python, self).strategy()
        base_strategy.insert_before('absorb', self.python_absorb)
        return base_strategy

    @iterate_sections()
    def python_absorb(self, sections, i):
        """
        Python decorators are the tricky part of proper parsing of the source file into \
        sections of docs and code.

        Whenever a decorator section occurs, it should be merged not into the previous sections,
        but into the next.
        """

        if '@' in sections[i-1]['scope']:
            sections[i]['docs_text'] = sections[i-1]['docs_text'] + sections[i]['docs_text']
            sections[i]['code_text'] = sections[i-1]['code_text'] + sections[i]['code_text']
            sections[i-1:i+1] = [sections[i]]
            return i


class Fortran(IndentBasedLanguage, MultilineCommentLanguage, InlineCommentLanguage):
    """
    ### Fortran
    """
    extensions = [".f", ".f90"]
    inline_delimiter = "!"
    multistart = r'^[Cc]'
    multiend = r'$'

    scope_keywords = [r"^\s*(subroutine) ", r"^\s*(function)", r"^\s*(module)", r"^\s*(program)"]


class Ruby(IndentBasedLanguage, InlineCommentLanguage, MultilineCommentLanguage):
    """
    ### Ruby
    Mostly identical to Python.

    TODO: Actually, Ruby is crazy and supports unbelievable variety of multiline comment syntaxes:

    ```python
        multistart = ["=begin", "<<-DOC", "\"", "__END__"]
        multiend = ["=end", "DOC", "\"", ""]
    ```
    will have to rethink multiline comments capturing to support them all
    """
    extensions = [".rb"]
    inline_delimiter = "#"
    multistart = "=begin"
    multiend = "=end"

    scope_keywords = [r"^\s*(module) ", r"^\s*(class) ", r"^\s*(def) "]

class Haskell(InlineCommentLanguage, MultilineCommentLanguage):
    """## Haskell

    Haskell is actually an indent-based language, but declaring it
    as such brings havoc into the Haddock documentation.
    We will have to rely on the user to break the source accordingly
    with comments.
    
    TODO: Does anyone still use literate haskell? It'd be intersing to support it.
    """
    extensions = [".hs"]
    inline_delimiter = "--"
    multistart = "{-"
    multiend = "-}"

    # [Chapters](https://www.haskell.org/haddock/doc/html/ch03s04.html)
    # in Haddock documentation.
    # It would be great if we could somehow format these as documentation,
    # but they would conflict with Markdown's syntax for lists...
    ignored_inline_patterns = [r"( (\*)* .*)"]

    # Pragmas: `{-# ... #--}`
    multiline_ignore_start = "#"
    multiline_ignore_end = "#"

    # Embed Haddock inside Markdown.
    # Actually, Haddock is crazy and almost impossible to parse
    # correctly by something other than itself.
    # The markup format, however, is easy, and that's what we
    # intend to support.
    # See the extension definition for details.
    markdown_extensions = \
        default_markdown_extensions + [markdown_extensions.Haddock()]


# ## Languages in development

class CoffeeScript(InlineCommentLanguage, MultilineCommentLanguage):
    """### Coffeescript"""
    extensions = [".coffee"]
    name = "Coffee-Script"
    inline_delimiter = "#"
    multistart = "###"
    multiend = "###"


class Perl(InlineCommentLanguage):
    """### Perl"""
    extensions = [".pl"]
    inline_delimiter = "#"


class SQL(InlineCommentLanguage):
    """### SQL"""
    extensions = [".sql"]
    inline_delimiter = "--"


class Scheme(InlineCommentLanguage, MultilineCommentLanguage):
    """### Scheme
    Can probably serve as a base to other LISP dialects,
    such as Common Lisp and Racket.
    """
    extensions = [".scm"]
    inline_delimiter = ";;"
    multistart = "#|"
    multiend = "|#"


class Clojure(IndentBasedLanguage,
              InlineCommentLanguage,
              DoubleQuoteDocstringLanguage):
             
    """### Clojure and Clojurescript
    """
    extensions = [".cljs", ".clj"]
    inline_delimiter = ";;"

    nsLinksExt = markdown_extensions.NsLinks()
    nsLinksExt.namespace_re = "\S+/"
    anchor_prefix = '_'

    markdown_extensions = default_markdown_extensions + [nsLinksExt]

    scope_keywords = [r"^\s*\((def\S*)((\s+\^:\S*)*)\s+([^\s\)]*)",
                      r"^\s*\((ns)\s+([^\s\)]*)"]


class Lua(InlineCommentLanguage, MultilineCommentLanguage):
    """### Lua"""
    extensions = [".lua"]
    inline_delimiter = "--"
    multistart = "--[["
    multiend = "--]]"


class Erlang(InlineCommentLanguage):
    """### Erlang"""
    extensions = [".erl"]
    inline_delimiter = "%%"


class Tcl(InlineCommentLanguage):
    """### Tcl"""
    extensions = [".tcl"]
    inline_delimiter = "#"

    
# ## Gathering all languages

extensions_mapping = {}


languages = [Markdown, Python, Fortran, PHP, C,
    JavaScript, Ruby, Haskell, Lua, Erlang, Tcl,
    CoffeeScript, Perl, SQL, Scheme, Clojure]

for language in languages:
    instance = language()
    for extension in instance.extensions:
        extensions_mapping[extension] = instance


def get_language(source, code, language=None):
    """Get the current language we're documenting, based on the extension."""

    if language is not None:
        for l in extensions_mapping.values():
            if l.name == language:
                return l
        else:
            raise ValueError("Unknown forced language: " + language)

    m = re.match(r'.*(\..+)', os.path.basename(source))

    if m and m.group(1) in extensions_mapping:
        return extensions_mapping[m.group(1)]
    else:
        try:
            lang = lexers.guess_lexer(code).name.lower()
        except Exception:
            return None
        for l in extensions_mapping.values():
            if l.name == lang:
                return l
        else:
            return None
