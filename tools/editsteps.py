"""Small helpers for editing data/steps files from patch scripts."""
import re


class Steps:
    def __init__(self, path):
        self.path = path
        self.s = open(path).read()

    def rep(self, a, b):
        assert self.s.count(a) == 1, (self.path, self.s.count(a), a)
        self.s = self.s.replace(a, b)

    def _quest_span(self, qid):
        m = re.search(r"^quest %s\s*$" % re.escape(qid), self.s, re.M)
        assert m, qid
        n = re.search(r"^quest \S+\s*$", self.s[m.end():], re.M)
        return m.start(), (m.end() + n.start()) if n else len(self.s)

    def fields(self, qid, **kw):
        """Add / replace quest-level fields (inserted after the 'kind' line)."""
        a, b = self._quest_span(qid)
        block = self.s[a:b]
        head, sep, rest = block.partition("\n  step ")
        for k, v in kw.items():
            pat = re.compile(r"^  %s\s+.*$\n" % k, re.M)
            line = "  %-6s %s\n" % (k, v)
            if pat.search(head):
                head = pat.sub(line.replace("\\", "\\\\"), head, count=1)
            else:
                km = re.search(r"^  kind .*$\n", head, re.M)
                head = head[:km.end()] + line + head[km.end():]
        self.s = self.s[:a] + head + sep + rest + self.s[b:]

    def step_block(self, qid, text):
        a, b = self._quest_span(qid)
        i = self.s.index("  step " + text + "\n", a, b)
        j = self.s.find("\n  step ", i + 1, b)
        j = b if j < 0 else j + 1
        return i, j

    def replace_step(self, qid, text, new):
        i, j = self.step_block(qid, text)
        self.s = self.s[:i] + new.rstrip("\n") + "\n\n" + self.s[j:].lstrip("\n")

    def insert_after_step(self, qid, text, new):
        i, j = self.step_block(qid, text)
        self.s = self.s[:j].rstrip("\n") + "\n\n" + new.rstrip("\n") + "\n\n" + self.s[j:].lstrip("\n")

    def append_step(self, qid, new):
        a, b = self._quest_span(qid)
        self.s = self.s[:b].rstrip("\n") + "\n\n" + new.rstrip("\n") + "\n\n" + self.s[b:].lstrip("\n")

    def save(self):
        open(self.path, "w").write(self.s)
