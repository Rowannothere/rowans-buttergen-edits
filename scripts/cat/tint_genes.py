"""BUTTERGEN: coat tints and white patch tints as genes.

Every cat has two copies of each, one from each parent, kept in genotype.tint_genes as
{"tint": [a, b], "white_tint": [a, b]}. A tint only shows on coat colors it fits (the lists in
sprites/dicts/tint.json and white_patches_tint.json). If both copies fit, one shows, and the cat
keeps that one for life (pelt.tint). If neither fits, the coat rolls a fitting tint like before,
but the cat still passes on the copies it carries.

Cats with no parents roll their shown tint as before, and carry a second one that fits their color.
"""
from random import choice

KINDS = ("tint", "white_tint")


def _name(tint):
    return tint if tint else "none"


def _genes_of(genes):
    found = getattr(genes, "tint_genes", None)
    return found if isinstance(found, dict) else {}


def copies_of(genes, kind):
    pair = _genes_of(genes).get(kind)
    return list(pair) if isinstance(pair, list) and len(pair) == 2 else []


def set_copies(genes, kind, pair):
    found = dict(_genes_of(genes))
    found[kind] = [_name(pair[0]), _name(pair[1])]
    genes.tint_genes = found


def kit_genes(par1, par2):
    """Each parent passes one of their two copies. A parent with none passes nothing, and the kit
    then rolls that copy when its coat is made."""
    found = {}
    for kind in KINDS:
        pair = [copies_of(par, kind) for par in (par1, par2)]
        if all(pair):
            found[kind] = [choice(pair[0]), choice(pair[1])]
    return found


def pick(genes, kind, fitting, roll):
    """The tint that shows. fitting is what fits the coat's color, roll makes a new one.
    Fills in missing copies, so a cat from before tints were genes gets them here."""
    pair = copies_of(genes, kind)
    if not pair:
        shown = roll()
        set_copies(genes, kind, [shown, choice(fitting) if fitting else shown])
        return shown
    shown_ok = [tint for tint in pair if tint in fitting]
    return choice(shown_ok) if shown_ok else roll()


def keep_shown(genes, pelt, only_missing=False):
    """A cat whose shown tint was set by hand (cat maker, editor) carries it in place of one
    of its copies, so the cat passes it on. only_missing: just fill in a cat from an older
    save, whose tint becomes both its copies."""
    for kind, shown in (("tint", pelt.tint), ("white_tint", pelt.white_patches_tint)):
        shown = _name(shown)
        pair = copies_of(genes, kind)
        if shown in pair or (only_missing and pair):
            continue
        set_copies(genes, kind, [shown, pair[0] if pair else shown])


def gene_list(genes):
    """For the genes list on the profile"""
    return ", ".join(
        f"{label}: {' / '.join(copies_of(genes, kind))}"
        for kind, label in (("tint", "Coat tint"), ("white_tint", "White patch tint"))
        if copies_of(genes, kind)
    )


def match_parents(kit_genes_, parent_genes):
    """Made up parents for your cat's birth get the copies your cat needed from them"""
    for kind in KINDS:
        kit_pair = copies_of(kit_genes_, kind)
        if not kit_pair:
            continue
        for tint, par in zip(kit_pair, parent_genes):
            pair = copies_of(par, kind)
            if tint not in pair:
                set_copies(par, kind, [tint, pair[1] if pair else tint])
