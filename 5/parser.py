import sys
import subprocess

import stanza

class Colorcodes(object):
    """
    Provides ANSI terminal color codes which are gathered via the ``tput``
    utility. That way, they are portable. If there occurs any error with
    ``tput``, all codes are initialized as an empty string.
    The provides fields are listed below.
    Control:
    - bold
    - reset
    Colors:
    - blue
    - green
    - orange
    - red
    :license: MIT
    """
    def __init__(self):
        try:
            self.bold = subprocess.check_output("tput bold".split(), encoding="utf8")
            self.reset = subprocess.check_output("tput sgr0".split(), encoding="utf8")

            self.blue = subprocess.check_output("tput setaf 4".split(), encoding="utf8")
            self.green = subprocess.check_output("tput setaf 2".split(), encoding="utf8")
            self.orange = subprocess.check_output("tput setaf 3".split(), encoding="utf8")
            self.red = subprocess.check_output("tput setaf 1".split(), encoding="utf8")
        except subprocess.CalledProcessError as e:
            self.bold = ""
            self.reset = ""

            self.blue = ""
            self.green = ""
            self.orange = ""
            self.red = ""

colorcodes = Colorcodes()

stanza.download('en', processors="tokenize")
nlp = stanza.Pipeline(lang='en', processors='tokenize')

print("Enter English text. Ctrl-D to finish")

text = sys.stdin.read()
doc = nlp(text)

line_starts = []
current_start = 0
for p, c in enumerate(text):
    if c == "\n":
        current_start = p + 1

    line_starts.append(current_start)


sentence_starts = [0]
for sentence in doc.sentences:
    sentence_starts.append(sentence.tokens[-1].end_char + 1)

for i in range(len(sentence_starts) - 1):
    print('=' * 50 + f"  sentence #{i + 1}  " + "=" * 50)
    if i > 0:
        indent = sentence_starts[i - 1] - line_starts[sentence_starts[i - 1]]
        print(" " * indent + colorcodes.orange + text[sentence_starts[i - 1]:sentence_starts[i]] + colorcodes.reset, end="")
    

    print(text[sentence_starts[i]:sentence_starts[i + 1]], end="")

    if i < len(sentence_starts) - 2:
        print(colorcodes.orange + text[sentence_starts[i + 1]:sentence_starts[i + 2]] + colorcodes.reset)
    else:
        print()
