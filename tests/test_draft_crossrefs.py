"""Guards for two contradictions the round-9 review found in the wording.

Both are cheap to reintroduce by editing one section and forgetting the other, so
they are asserted on the text itself rather than trusted to memory.
"""
import io, re, pathlib

DRAFT = pathlib.Path(__file__).resolve().parent.parent / "drafts" / "draft-zhao-uibc-evidence-chain-01.md"


def text():
    return io.open(DRAFT, encoding="utf-8").read()


def sections(t):
    """Split on '## N.' headings so a claim cannot be satisfied by another section."""
    out, cur, name = {}, [], None
    for line in t.splitlines():
        m = re.match(r"## (\d+)\.", line)
        if m:
            if name:
                out[name] = "\n".join(cur)
            name, cur = m.group(1), []
        elif name:
            cur.append(line)
    if name:
        out[name] = "\n".join(cur)
    return out


def test_iana_and_vocabulary_policies_do_not_contradict():
    sec = sections(text())
    iana = sec["11"]
    assert "no IANA action" in iana
    assert "Section 15" in iana, "Section 11 must point at the vocabularies it declines to register"
    vocab = sec["15"]
    assert "Specification Required" in vocab
    assert "not" in vocab and "registry" in vocab
    assert "Section 11" in vocab, "Section 15 must point back at the section that says nothing is registered"


def test_head_is_defined_where_the_table_points():
    t = text()
    assert "| Head (Section 4.2;" in t
    assert "| Head (Appendix F) |" not in t
    # The definition must actually be in 4.2.
    assert "### 4.2 Merkle profile" in t


def test_no_bare_appendix_f_as_definition():
    t = text()
    assert "the head of Appendix F" not in t.lower()
    assert "only-grew property Section 4.2" in t
