"""Basic example of hyperlinks -- show CNN news site with clickable URL's."""
# 3rd party
import requests
from bs4 import BeautifulSoup

# local imports
from blessed import Terminal


def embolden(phrase):
    # bold some phrases
    return phrase.isdigit() or phrase[:1].isupper()


def make_bold(term, text):
    # embolden text
    return ' '.join(term.color_hex('#ecc')(phrase) if embolden(phrase) else phrase
                    for phrase in text.split(' '))


def find_articles(soup):
    return (a_link for a_link in soup.find_all('a') if a_link.get('href').startswith('/')
            and a_link.text != 'CNN')


def main():
    term = Terminal()
    cnn_url = 'https://lite.cnn.com'
    soup = BeautifulSoup(requests.get(cnn_url).content, 'html.parser')
    textwrap_kwargs = {
        'width': term.width - (term.width // 4),
        'initial_indent': ' * ',
        'subsequent_indent': '   ',
    }
    print(term.center('CNN Headlines'))
    print(term.center('============='))
    print()
    line_num = 1
    for a_href in find_articles(soup):
        # create headlines with colors and placeholder for clickable hyperlink
        ansi_text = make_bold(term, a_href.text.strip() + ' [view]')
        for line in term.wrap(ansi_text, **textwrap_kwargs):
            # replace with a clickable hyperlink
            if '[view]' in line:
                text = term.bright_black('[view]')
                url = cnn_url + a_href.get('href')
                line = line.replace('[view]', term.link(url=url, text=text, url_id=line_num))
            print(' ' * (term.width//8) + line.rstrip())
            line_num += 1
        if line_num > term.height - 6:
            break
    print()


if __name__ == '__main__':
    main()
