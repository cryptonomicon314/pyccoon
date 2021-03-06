<p align="center">
<a href="http://ckald.github.io/pyccoon/">
<img src="https://www.dropbox.com/s/n6s0ngrjl69ct09/pyccoon.svg?dl=1" alt="Pyccoon" />
</a>
</p>

[![PyPi package](https://img.shields.io/pypi/v/pyccoon.svg)](https://pypi.python.org/pypi/pyccoon)
![Downloads](https://img.shields.io/pypi/dm/pyccoon.svg)
![Python versions](https://img.shields.io/pypi/pyversions/pyccoon.svg)
[![Build Status](https://travis-ci.org/ckald/pyccoon.svg?branch=master)](https://travis-ci.org/ckald/pyccoon)
[![Code Health](https://landscape.io/github/ckald/pyccoon/master/landscape.svg?style=flat)](https://landscape.io/github/ckald/pyccoon/master)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

Side-to-side documentation generator. Fork of the [Pycco](http://fitzgen.github.io/pycco/), grandfork of the [Docco](http://jashkenas.github.com/docco/). And an object-oriented one.

[See how it works](http://ckald.github.io/pyccoon/)

# Installation

Pyccoon is [available](https://pypi.python.org/pypi/pyccoon/) on PyPi package index. You can install it using pip:

```bash
pip install pyccoon
```

Another way to get the Pyccoon is

```bash
git clone https://github.com/ckald/pyccoon.git
cd pyccoon
python setup.py install
```

And you're done. Pyccoon is compatible with Python 2.6, 2.7, 3.3, 3.4 and PyPy. Latest test results can be seen on the [Travis CI project page](https://travis-ci.org/ckald/pyccoon).

# Usage

To generate the project documentation

```bash
pyccoon -s <source folder> -d <documentation folder>
```

For additional CLI options, see `pyccoon --help`

At the moment Pyccoon supports Python, Ruby, Javascript, PHP and C/C++ source files. Other project files will be simply copied to the documentation folder. For additional configuration, create a config file of the kind:

```yaml
# Items related to the project (currently only the name)
project:
   name: Your Project Name Goes Here
# How verbose we want Pycoon to be
verbosity: null 
# Items related to file handling
files:
   # Files Pyccoon will skip when generating the documentation.
   # Must be a list of regular expressions (not glob patterns!)
   skip:
       - "doc"
       - "\\.git*"
       - ".+\\.pyc"
   # Files that Pyccoon will copy literally
   copy:
       - "pyccoon.svg"
       - ".+\\css"
       - "\\.pyccoon.yaml"
# Items related to generation of HTML docs
documentation:
   mathjax: true
   # Can be either "pre-wrap" or "normal". Default is "normal"
   #  - "pre-wrap" respects line breaks
   linebreaking-behavior: normal
   # A path to a CSS file or 'null' (the default)
   css-path: null
   # A path to a HTML file or 'null' (the default)
   custom-html-template: null
```

# Supported languages

It is easy to add a language to Pyccoon (pull requests are welcome!), but it requires some testing on the real-life project. By now we have worked with:

  - Markdown
  - Python
  - Ruby (basic)
  - C/C++
  - Javascript
  - PHP
  - Fortran

Other languages are supported, but not well tested:

  - PHP
  - Haskell
  - Lua
  - Erlang
  - Tcl
  - CofeeScript
  - Perl
  - SQL
  - Scheme
  - Clojure

# Development roadmap

  - Enhancements:
      - [ ] Use `glob`: replace config file regular expressions with more natural wildcards (also support matching against the whole path, not only filename)
      - [ ] Add line numbers feature
      - [ ] Incremental regeneration
      - [ ] Object retrieval and cross-linking ("jump to definition" for classes, functions)
      - [ ] Search
      - [ ] Extended docblocks parsing (capturing shortcuts and aliases for cross-linking)
      - [ ] Mixed documents parsing: HTML/JS/CSS, HTML/PHP, etc.

-------

# Acknowledgements

  * [Cryptonomicon314](https://github.com/cryptonomicon314) as a surprisingly enthusiastic contributor
  * [Nick Fitzgerald](http://github.com/fitzgen) as an author of [Pycco](https://github.com/fitzgen/pycco) that was a starting point of the development
  * [Jeremy Ashkenas](https://github.com/jashkenas) as an author of original idea - [Docco](https://github.com/jashkenas/docco)
  * Raccoon designed by [Christy Presler](http://www.thenounproject.com/cnpresler) from the [Noun Project](http://www.thenounproject.com/)
