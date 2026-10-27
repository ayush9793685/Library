#!/usr/bin/env python3
"""
test_html_parser.py

A standalone experiment to see how Python's built-in html.parser reports HTML.
This is a learning/test script, not the PatchPlus html_broker.py implementation.

Usage:
    python test_html_parser.py
    python test_html_parser.py path/to/home.html
"""

from html.parser import HTMLParser
from pathlib import Path
import sys


SAMPLE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <title>StudentHub</title>
</head>
<body>
  <a href="/accounts/login/" class="rounded-lg bg-[#f25b2a]">LOGIN</a>
  <a href="mailto:contact@studenthub.local">CONTACT</a>
  <form action="/accounts/login/" method="post">
    <input name="username" type="text">
    <button>Log In</button>
  </form>
  <img src="/static/logo.png" alt="StudentHub logo">
</body>
</html>
"""


class DebugHTMLParser(HTMLParser):
    """Print the events that HTMLParser emits as it reads the document."""

    # These HTML elements do not have closing tags.
    VOID_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }

    def __init__(self):
        # convert_charrefs=True makes HTML character references in text easier
        # to read. It does not execute JavaScript or Django template code.
        super().__init__(convert_charrefs=True)
        self.stack = []

    def indent(self):
        return "  " * len(self.stack)

    def handle_decl(self, decl):
        print(f"DECLARATION: <!{decl}>")

    def handle_starttag(self, tag, attrs):
        print(f"{self.indent()}START TAG: <{tag}>")
        for name, value in attrs:
            print(f"{self.indent()}  ATTRIBUTE: {name}={value!r}")
        if tag not in self.VOID_TAGS:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        print(f"{self.indent()}SELF-CLOSING TAG: <{tag} />")
        for name, value in attrs:
            print(f"{self.indent()}  ATTRIBUTE: {name}={value!r}")

    def handle_endtag(self, tag):
        # Pop back to the matching open tag when possible. This is only for
        # readable debug indentation; HTMLParser does not build/validate a DOM.
        if tag in self.stack:
            while self.stack:
                opened = self.stack.pop()
                if opened == tag:
                    break
        print(f"{self.indent()}END TAG: </{tag}>")

    def handle_data(self, data):
        text = data.strip()
        if text:
            print(f"{self.indent()}TEXT: {text!r}")

    def handle_comment(self, data):
        print(f"{self.indent()}HTML COMMENT: {data!r}")

    def handle_entityref(self, name):
        print(f"{self.indent()}ENTITY REFERENCE: &{name};")

    def handle_charref(self, name):
        print(f"{self.indent()}CHARACTER REFERENCE: &#{name};")

    def unknown_decl(self, data):
        print(f"{self.indent()}UNKNOWN DECLARATION: {data!r}")


def main():
    if len(sys.argv) > 2:
        print("Usage: python test_html_parser.py [path/to/file.html]")
        raise SystemExit(2)

    if len(sys.argv) == 2:
        file_path = Path(sys.argv[1])
        try:
            html = file_path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"Could not read {file_path}: {exc}")
            raise SystemExit(1)
        print(f"Parsing file: {file_path}\n")
    else:
        html = SAMPLE_HTML
        print("No file supplied; parsing the built-in StudentHub sample.\n")

    parser = DebugHTMLParser()
    parser.feed(html)
    parser.close()
    print("\nFinished parsing.")
    print("Note: html.parser reports parsing events; it is not a strict HTML validator.")


if __name__ == "__main__":
    main()
#"C:/Users/ayush/Downloads/student-management-system-django/templates/home.html"