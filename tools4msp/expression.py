import re

p = re.compile('{?(\w+\:\w+(.\w+)?)}?')


class Expression(object):
    def __init__(self, exp, read_function):
        self.exp = exp
        self.read_function = read_function

    def parse(self):
        return p.sub(r"{}('\1')".format(self.read_function),
                     self.exp)

    def list(self):
        return p.findall(self.exp)
