import unittest
import json
import logging

#logging.basicConfig(level="DEBUG")

import pygly2

from pygly2.structure import monosaccharide, constants, substituent, glycan, link, named_structures, structure_composition
from pygly2.io import glycoct
from pygly2.utils import enum, StringIO, identity, nullop, multimap
from pygly2.composition import Composition, composition_transform, composition


class GlycoCTParserTests(unittest.TestCase):
    _file_path = "./test_data/glycoct.txt"

    def test_parse_file(self):
        for g in glycoct.read(self._file_path):
            self.assertTrue(isinstance(g, glycan.Glycan))


# monosaccharide_masses = json.load(open("./test_data/monosaccharide_masses.json"))
monosaccharide_structures = json.load(open("./pygly2/structure/data/monosaccharides.json"))

wiki_masses = {
    "Iduronic Acid": 194.04,
    "Bacillosamine": 162.10,
    "Allose": 180.06,
}

#: Not common in any way other than
#: reused in many tests
common_glycan = '''
RES
1b:x-dglc-HEX-x:x
2b:b-dglc-HEX-1:5
3b:b-dglc-HEX-1:5
4b:b-dglc-HEX-1:5
5b:b-dglc-HEX-1:5
6b:b-dglc-HEX-1:5
7b:b-dglc-HEX-1:5
LIN
1:1o(6+1)2d
2:2o(3+1)3d
3:2o(6+1)4d
4:4o(6+1)5d
5:5o(3+1)6d'''


class MonosaccharideTests(unittest.TestCase):
    _file_path = "./test_data/glycoct.txt"
    glycan = iter(glycoct.read(_file_path)).next()

    def test_from_glycoct(self):
        s = self.glycan.root.to_glycoct()
        b = StringIO(s)
        g = iter(glycoct.read(b)).next()
        self.assertEqual(g.root.to_glycoct(), s)

    def test_named_structure_masses(self):
        for name, mass in wiki_masses.items():
            structure = named_structures.monosaccharides[name]
            self.assertAlmostEqual(mass, structure.mass(), 2)

    def test_named_structure_glycoct(self):
        for name, glycoct_str in monosaccharide_structures.items():
            structure = named_structures.monosaccharides[name]
            test, ref = (structure.to_glycoct(), glycoct_str)
            i = 0
            for j, k in zip(test, ref):
                if j != k:
                    test_loc = test.replace('\n', ' ')[i-10:i+10]
                    ref_loc = ref.replace('\n', ' ')[i-10:i+10]
                    raise AssertionError("{j} != {k} at {i} in {name}\n{test_loc}\n{ref_loc}".format(**locals()))
                i += 1

    def test_ring_limit_modification(self):
        structure = named_structures.monosaccharides['Hex']
        self.assertRaises(IndexError, lambda: structure.add_modification('d', 8))

    def test_occupancy_limit_modification(self):
        structure = named_structures.monosaccharides['Hex']
        structure.add_modification('d', 4)
        self.assertRaises(ValueError, lambda: structure.add_modification('d', 4))

    def test_ring_limit_substituent(self):
        structure = named_structures.monosaccharides['Hex']
        self.assertRaises(IndexError, lambda: structure.add_substituent('methyl', 8))

    def test_occupancy_limit_substituent(self):
        structure = named_structures.monosaccharides['Hex']
        structure.add_substituent('methyl', 4)
        self.assertRaises(ValueError, lambda: structure.add_substituent('methyl', 4))

    def test_add_remove_modifcations(self):
        for name, mass in wiki_masses.items():
            structure = named_structures.monosaccharides[name]
            ref = structure.clone()
            self.assertAlmostEqual(ref.mass(), structure.mass())
            open_sites, unknowns = structure.open_attachment_sites()
            n_sites = len(open_sites)
            comp_delta = n_sites * structure_composition.modification_compositions[constants.Modification.aldi]
            for site in open_sites:
                structure.add_modification(constants.Modification.aldi, site)
            self.assertEqual(structure.total_composition(), ref.total_composition() + comp_delta)
            self.assertEqual([], structure.open_attachment_sites()[0])
            for site in open_sites:
                structure.drop_modification(site, constants.Modification.aldi)
            self.assertEqual(structure.total_composition(), ref.total_composition())

    def test_add_remove_substituents(self):
        for name, mass in wiki_masses.items():
            structure = named_structures.monosaccharides[name]
            ref = structure.clone()
            self.assertAlmostEqual(ref.mass(), structure.mass())
            open_sites, unknowns = structure.open_attachment_sites()
            n_sites = len(open_sites)
            mass_delta = substituent.Substituent('methyl').mass() * n_sites - Composition("H2").mass * n_sites
            ping = True
            for site in open_sites:
                if ping:
                    structure.add_substituent(substituent.Substituent('methyl'), position=site)
                    ping = False
                else:
                    structure.add_substituent('methyl', position=site)
                    ping = True
            self.assertAlmostEqual(structure.mass(), ref.mass() + mass_delta)
            for site in open_sites:
                structure.drop_substiuent(site, substituent.Substituent('methyl'))
            self.assertAlmostEqual(structure.mass(), ref.mass())

    def test_add_remove_monosaccharides(self):
        for name, mass in wiki_masses.items():
            structure = named_structures.monosaccharides[name]
            ref = structure.clone()
            self.assertAlmostEqual(ref.mass(), glycan.Glycan(structure).mass())
            open_sites, unknowns = structure.open_attachment_sites()
            n_sites = len(open_sites)
            mass_delta = named_structures.monosaccharides["Hex"].mass() * n_sites - Composition("H2O").mass * n_sites
            for site in open_sites:
                structure.add_monosaccharide(named_structures.monosaccharides["Hex"], position=site, child_position=3)
            self.assertAlmostEqual(glycan.Glycan(structure).mass(), ref.mass() + mass_delta)
            for site in open_sites:
                structure.drop_monosaccharide(site)
            self.assertAlmostEqual(glycan.Glycan(structure).mass(), ref.mass())


class GlycanTests(unittest.TestCase):
    _file_path = "./test_data/glycoct.txt"

    def test_from_glycoct(self):
        for glycan in glycoct.read(self._file_path):
            self.assertAlmostEqual(glycan.mass(), iter(glycoct.loads(glycan.to_glycoct())).next().mass())

    def test_fragments_preserve(self):
        for glycan in glycoct.read(self._file_path):
            dup = glycan.clone()
            self.assertEqual(glycan, dup)
            fragments = list(dup.fragments('ZCBY', 3))

            self.assertEqual(glycan, dup)

    def test_clone(self):
        glycan = glycoct.loads(common_glycan).next()
        ref = glycan.clone()
        glycan.reducing_end = 1        
        self.assertTrue(glycan != ref)


    def test_indexing(self):
        glycan = glycoct.loads(common_glycan).next()
        ref = glycan.clone()
        for i, node in enumerate(glycan.index):
            self.assertEqual(node.id, ref[i].id)
        glycan.deindex()
        for i, node in enumerate(glycan.index):
            self.assertNotEqual(node.id, ref[i].id)
        self.assertRaises(TypeError, lambda: node["1"])

    def test_traversal(self):
        glycan = glycoct.loads(common_glycan).next()
        glycan[-1].add_monosaccharide(named_structures.monosaccharides['NeuGc'])
        glycan.reindex(method='dfs')
        ref = glycan.clone()
        self.assertEqual(glycan[-1], ref[-1])
        glycan.reindex(method='bfs')
        self.assertNotEqual(glycan[-1], ref[-1])

    def test_leaves(self):
        glycan = glycoct.loads(common_glycan).next()
        leaves = list(glycan.leaves())
        for node in leaves:
            self.assertTrue(len(list(node.children())) == 0)

    def test_custom_traversal_method(self):
        def rev_sort_dfs(self, visited=None, from_node=None, *args, **kwargs):
            node_stack = list([self.root])
            visited = set()
            while len(node_stack) > 0:
                node = node_stack.pop()
                if node.id in visited:
                    continue
                visited.add(node.id)
                yield (node)
                node_stack.extend(reversed(list(terminal for pos, link in node.links.items()
                                  for terminal in link if terminal.id not in visited and
                                  len(link.child.substituent_links) < 1)))
        glycan = glycoct.loads(common_glycan).next()
        glycan[-3].add_monosaccharide(named_structures.monosaccharides['Hex'], 4).add_substituent('methyl', 5)
        glycan.reindex()
        ref = glycan.clone()
        self.assertEqual(glycan[-3], ref[-3])
        glycan.reindex(method=rev_sort_dfs)
        self.assertNotEqual(glycan[-3], ref[-3])


class SubstituentTests(unittest.TestCase):
    pass


class MultiMapTests(unittest.TestCase):
    def test_iterators(self):
        from collections import Counter
        mm = multimap.MultiMap(a=1, b=3)
        mm['a'] = 3
        self.assertTrue(set(mm.keys()) == {'a', 'b'})
        self.assertTrue(set(mm.items()) == {('a', 1), ('a', 3), ('b', 3)})
        self.assertTrue(Counter(mm.values()) == Counter({1: 1, 3: 2}))




class CompositionTests(unittest.TestCase):

    def test_derivativize_bare(self):
        permethylated_reduced_mass = 1286.6718
        glycan = glycoct.loads(common_glycan).next()
        ref = glycan.clone()
        glycan.reducing_end = 1
        composition_transform.derivatize(glycan, 'methyl')
        self.assertAlmostEqual(glycan.mass(), permethylated_reduced_mass, 3)

    def test_composition_equality(self):
        self.assertEqual(Composition("H2O"), Composition("H2O"))

    def test_composition_substraction(self):
        self.assertEqual(Composition("NH2O") - Composition("N"), Composition("H2O"))

    def test_isotope_parsing(self):
        self.assertFalse(Composition("O[18]") == Composition("O"))
        self.assertAlmostEqual(Composition("O[18]").mass, 17.999, 3)

    def test_inits(self):
        composition.debug = True
        self.assertEqual(Composition(O=1, H=2), Composition(formula='H2O'))
        composition.debug = False

class ConstantTests(unittest.TestCase):
    def test_translate(self):
        self.assertTrue(constants.Modification.d == constants.Modification['d'])
        self.assertTrue(constants.Modification.d == constants.Modification['D'])
        self.assertTrue(constants.Modification.d == constants.Modification[constants.Modification.d.value])

    def test_compare(self):
        self.assertTrue(constants.Modification.d == 'd')
        self.assertTrue(constants.Modification.d == constants.Modification.d.value)
        self.assertNotEqual(constants.Modification.d, constants.Stem[constants.Modification.d.value])
        self.assertRaises(KeyError, lambda: constants.SuperClass[1])

class LinkTests(unittest.TestCase):
    def test_link_equality(self):
        parent = named_structures.monosaccharides['Hex']
        child = named_structures.monosaccharides['Hex']
        other = named_structures.monosaccharides['Hex']
        link_1 = link.Link(parent, child, parent_position=3, child_position=3, parent_loss='H', child_loss='OH')
        link_2 = link.Link(child, other, parent_position=6, child_position=3, parent_loss='H', child_loss='OH')
        self.assertEqual(link_1, link_1)
        self.assertNotEqual(link_1, link_2)
        self.assertFalse(link_1 == None)

    def test_loss_composition(self):
        parent = named_structures.monosaccharides['Hex']
        child = named_structures.monosaccharides['Hex']

        link_1 = link.Link(parent, child, parent_position=3, child_position=3, parent_loss='H', child_loss='OH')

        self.assertEqual(link_1.parent_loss, Composition(formula="H"))
        self.assertEqual(link_1.child_loss, Composition(formula="OH"))

    def test_break_and_reconnect(self):
        parent = named_structures.monosaccharides['Hex']
        child = named_structures.monosaccharides['Hex']

        link_1 = link.Link(parent, child, parent_position=3, child_position=3, parent_loss='H', child_loss='OH')
        link_1.break_link(refund=True, reorient_fn=identity)
        self.assertTrue(len(parent.links[3]) == 0)
        self.assertTrue(len(child.links[3]) == 0)

        link_1.reconnect(refund=True, reorient_fn=identity)
        self.assertTrue(len(parent.links[3]) == 1)
        self.assertTrue(len(child.links[3]) == 1)

    def test_traversal(self):
        parent = named_structures.monosaccharides['Hex']
        child = named_structures.monosaccharides['Hex']

        link_1 = link.Link(parent, child, parent_position=3, child_position=3, parent_loss='H', child_loss='OH')
        self.assertTrue(link_1.is_parent(parent))
        self.assertTrue(link_1.is_child(child))
        self.assertEqual(link_1.to(parent), child)
        self.assertEqual(link_1.to(child), parent)
        self.assertRaises(KeyError, lambda: link_1.to(1))


if __name__ == '__main__':
    unittest.main()
