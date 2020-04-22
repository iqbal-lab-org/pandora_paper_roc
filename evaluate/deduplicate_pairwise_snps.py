import networkx as nx
from evaluate.mummer import ShowSNPsDataframe
from pathlib import Path
import re
import pickle
from typing import Tuple, Iterable, Set, List, Generator
import functools
import itertools
from collections import defaultdict


class DeduplicatePairwiseSNPsUtils:
    @staticmethod
    def _get_ref_and_query_from_ShowSNPsDataframe_filepath(ShowSNPsDataframe_filepath: str) -> Tuple[str, str]:
        ShowSNPsDataframe_filepath = Path(ShowSNPsDataframe_filepath)
        ShowSNPsDataframe_filename = ShowSNPsDataframe_filepath.name
        matches = re.match(r"(.*)_and_(.*).snps_df.pickle", ShowSNPsDataframe_filename)
        ref = matches.group(1)
        query = matches.group(2)
        return ref, query

    # Note: not tested (trivial method)
    @staticmethod
    def _load_pickled_ShowSNPsDataframe(df_filepath: str) -> ShowSNPsDataframe:
        with open(df_filepath, "rb") as df_fh:
            return pickle.load(df_fh)


class NotASNP(Exception):
    pass

@functools.total_ordering
class Allele:
    def __init__(self, genome: str, chrom: str, pos: int, sequence: str):
        self._genome = genome
        self._chrom = chrom
        self._pos = pos

        # sequence is just used to ensure this is a SNP, for now
        is_snp = len(sequence) == 1
        if not is_snp:
            raise NotASNP()

    @property
    def genome(self) -> str:
        return self._genome
    @property
    def chrom(self) -> str:
        return self._chrom
    @property
    def pos(self) -> int:
        return self._pos
    @property
    def data_tuple(self) -> Tuple[str,str,int]:
        """
        :return: a tuple with all the data in the allele
        """
        return self.genome, self.chrom, self.pos

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Allele):
            return  self.data_tuple==other.data_tuple
        else:
            return False

    def __hash__(self) -> int:
        return hash(self.data_tuple)

    def __lt__(self, other: object) -> bool:
        if isinstance(other, Allele):
            return self.data_tuple < other.data_tuple
        else:
            raise TypeError()

    # Note: tested through DeduplicationGraph._add_variants_from_ShowSNPsDataframe_core()
    @staticmethod
    def get_alleles_from_ShowSNPsDataframe(ref: str, query: str, snps_df: ShowSNPsDataframe) -> Generator[Tuple["Allele", "Allele"], None, None]:
        for ref_chrom, ref_pos, ref_sub, query_chrom, query_pos, query_sub in \
            zip(snps_df["ref_chrom"], snps_df["ref_pos"], snps_df["ref_sub"],
                snps_df["query_chrom"], snps_df["query_pos"], snps_df["query_sub"]):
            is_snp = len(ref_sub)==1 and len(query_sub)==1
            if not is_snp:
                continue  # we just deal with SNPs as of now

            ref_allele = Allele(ref, ref_chrom, ref_pos, ref_sub)
            query_allele = Allele(query, query_chrom, query_pos, query_sub)
            yield ref_allele, query_allele


class PairwiseVariation:
    def __init__(self, allele_1: Allele, allele_2: Allele):
        self._allele_1 = min(allele_1, allele_2)
        self._allele_2 = max(allele_1, allele_2)
    @property
    def allele_1(self) -> Allele:
        return self._allele_1
    @property
    def allele_2(self) -> Allele:
        return self._allele_2

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PairwiseVariation):
            return self.allele_1 == other.allele_1 and self.allele_2 == other.allele_2
        else:
            return False

    def __hash__(self) -> int:
        return hash((self.allele_1, self.allele_2))

    def share_allele(self, other: "PairwiseVariation") -> bool:
        return self.allele_1 == other.allele_1 or self.allele_1 == other.allele_2 or \
               self.allele_2 == other.allele_1 or self.allele_2 == other.allele_2

    # Note: tested through DeduplicationGraph._add_variants_from_ShowSNPsDataframe_core()
    @staticmethod
    def get_PairwiseVariation_from_ShowSNPsDataframe(ref: str, query: str, snps_df: ShowSNPsDataframe) -> Generator[
        "PairwiseVariation", None, None]:
        for ref_allele, query_allele in Allele.get_alleles_from_ShowSNPsDataframe(ref, query, snps_df):
            yield PairwiseVariation(ref_allele, query_allele)


class PangenomeVariation:
    # Note: trivial method, not tested
    def __init__(self, alleles: Iterable[Allele]):
        self._alleles = set(alleles)
    @property
    def alleles(self) -> Set[Allele]:
        return self._alleles

    # Note: trivial method, not tested
    def __eq__(self, other: object):
        if isinstance(other, PangenomeVariation):
            return self.alleles==other.alleles
        else:
            return False


    def is_consistent(self) -> bool:
        genomes_to_chrom_and_pos = defaultdict(set)
        for allele in self.alleles:
            genomes_to_chrom_and_pos[allele.genome].add((allele.chrom, allele.pos))
        genomes_to_have_consistent_alleles = {
            genome: len(chrom_and_pos)==1 for genome, chrom_and_pos in genomes_to_chrom_and_pos.items()
        }
        all_genomes_have_consistent_alleles = all(genomes_to_have_consistent_alleles.values())
        return all_genomes_have_consistent_alleles


# Note: trivial class, not tested
class PangenomeVariations:
    def __init__(self):
        self._pangenome_variations = []
    @property
    def pangenome_variations(self) -> List[PangenomeVariation]:
        return self._pangenome_variations

    def append(self, pangenome_variation: PangenomeVariation):
        self.pangenome_variations.append(pangenome_variation)

    def __eq__(self, other: object):
        if isinstance(other, PangenomeVariations):
            return self.pangenome_variations==other.pangenome_variations
        else:
            return False


class ConsistentPangenomeVariations(PangenomeVariations):
    """
    For the definition of consistent Pangenome Variations, see https://github.com/iqbal-lab/pandora1_paper/issues/144#issue-603283664
    """
    def __init__(self, pangenome_variations: PangenomeVariations):
        super().__init__()
        for pangenome_variation in pangenome_variations.pangenome_variations:
            if pangenome_variation.is_consistent():
                self.append(pangenome_variation)

        self._alleles_in_consistent_pangenome_variations = set()
        for consistent_pangenome_variations in self.pangenome_variations:
            self._alleles_in_consistent_pangenome_variations.update(consistent_pangenome_variations.alleles)

    @property
    def alleles_in_consistent_pangenome_variations(self) -> Set[Allele]:
        return self._alleles_in_consistent_pangenome_variations


    def __contains__(self, item: object) -> bool:
        if isinstance(item, PairwiseVariation):
            return item.allele_1 in self.alleles_in_consistent_pangenome_variations and \
                   item.allele_2 in self.alleles_in_consistent_pangenome_variations
        else:
            raise TypeError()

    def get_boolean_presence_vector_given_ShowSNPsDataframe_core(self, ref: str, query: str, snps_df: ShowSNPsDataframe) -> List[bool]:
        presence = [False]*len(snps_df)
        for index, pairwise_variation in enumerate(PairwiseVariation.get_PairwiseVariation_from_ShowSNPsDataframe(ref, query, snps_df)):
            presence[index] = pairwise_variation in self
        return presence




class DeduplicationGraph:
    def __init__(self):
        self._graph = nx.Graph()
    @property
    def graph(self):
        return self._graph
    @property
    def nodes(self):
        return self.graph.nodes
    @property
    def edges(self):
        return self.graph.edges

    # Note: not tested (trivial method)
    def _add_pairwise_variation(self, pairwise_variation: PairwiseVariation) -> None:
        self._graph.add_node(pairwise_variation)


    def _add_variants_from_ShowSNPsDataframe_core(self, ref: str, query: str, snps_df: ShowSNPsDataframe) -> None:
        for pairwise_variation in PairwiseVariation.get_PairwiseVariation_from_ShowSNPsDataframe(ref, query, snps_df):
            self._add_pairwise_variation(pairwise_variation)


    # Note: not tested (trivial method)
    def add_variants_from_ShowSNPsDataframe_filepath(self, ShowSNPsDataframe_filepath: str) -> None:
        ref, query = DeduplicatePairwiseSNPsUtils._get_ref_and_query_from_ShowSNPsDataframe_filepath(ShowSNPsDataframe_filepath)
        snps_df = DeduplicatePairwiseSNPsUtils._load_pickled_ShowSNPsDataframe(ShowSNPsDataframe_filepath)
        self._add_variants_from_ShowSNPsDataframe_core(ref, query, snps_df)


    def _add_edge(self, variant_1, variant_2) -> None:
        self._graph.add_edge(variant_1, variant_2)


    def build_edges(self) -> None:
        """
        Note: Should be called after all nodes are added.
        """
        #TODO: the runtime is quadratic on the number of variants. In the 24-way will be too much. We will have 24*23/2=276
        #TODO: pairwise comparisons. These comparisons have around 100k variants, so the code inside this for will be executed
        #TODO: (276 * 100000) ** 2 = ~761 trillion times... probably the bottleneck will be here.
        #TODO: implement an indexing of variants per (genome, chrom, position/10000)
        #TODO: a variant only needs to check the buckets belonging to its alleles
        for variant_1, variant_2 in itertools.product(self.nodes, self.nodes):
            if variant_1 != variant_2:
                if variant_1.share_allele(variant_2):
                    self._add_edge(variant_1, variant_2)


    # Note: not tested (trivial method)
    def _get_connected_components(self) -> Generator[Set[PairwiseVariation], None, None]:
        return nx.connected_components(self.graph)

    def get_pangenome_variations(self) -> PangenomeVariations:
        pangenome_variations = PangenomeVariations()

        connected_components = self._get_connected_components()
        for connected_component_index, connected_component in enumerate(connected_components):
            alleles_in_connected_component = []
            for pairwise_variation in connected_component:
                alleles_in_connected_component.append(pairwise_variation.allele_1)
                alleles_in_connected_component.append(pairwise_variation.allele_2)
            pangenome_variation = PangenomeVariation(alleles_in_connected_component)
            pangenome_variations.append(pangenome_variation)

        return pangenome_variations
