"""Basic example of hyperlinks -- show CNN news site with clickable URL's."""
# std imports
import random

# 3rd party
import requests

# local
# 3rd-party
from bs4 import BeautifulSoup
# local imports
from blessed import Terminal


def embolden(phrase):
    # bold some phrases
    return phrase.isdigit() or phrase[:1].isupper()


def make_bold(term, text):
    # embolden text
    return ' '.join(term.bold(phrase) if embolden(phrase) else phrase
                    for phrase in text.split(' '))


def whitespace_only(term, line):
    # return only left-hand whitespace of `line'.
    return line[:term.length(line) - term.length(line.lstrip())]


def find_articles(soup):
    return (a_link for a_link in soup.find_all('a') if '/article' in a_link.get('href'))


def main():
    term = Terminal()
    cnn_url = 'https://lite.cnn.io'
    soup = BeautifulSoup(requests.get(cnn_url).content, 'html.parser')
    textwrap_kwargs = {
        'width': term.width - (term.width // 4),
        'initial_indent': ' ' * (term.width // 6) + '* ',
        'subsequent_indent': (' ' * (term.width // 6)) + ' ' * 2,
    }
    for a_href in find_articles(soup):
        url_id = random.randrange(0, 1 << 24)
        for line in term.wrap(make_bold(term, a_href.text), **textwrap_kwargs):
            print(whitespace_only(term, line), end='')
            print(term.link(cnn_url + a_href.get('href'), line.lstrip(), url_id))


if __name__ == '__main__':
    main()
