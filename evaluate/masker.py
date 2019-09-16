from intervaltree import IntervalTree, Interval
import math
from evaluate.classification import Classification
from typing import TextIO, Iterable, Type, Optional


class Masker:
    def __init__(self, tree: IntervalTree = None):
        if tree is None:
            tree = IntervalTree()
        self.tree = tree

    def __eq__(self, other: "Masker") -> bool:
        return self.tree == other.tree

    @staticmethod
    def from_bed(bed: TextIO) -> "Masker":
        tree = IntervalTree()
        for region in bed:
            chrom, start, end = region.strip().split("\t")
            tree.addi(int(start), int(end), chrom)
        return Masker(tree=tree)

    def filter_records(
        self, classifications: Iterable[Type[Classification]]
    ) -> Iterable[Type[Classification]]:
        return [
            classification
            for classification in classifications
            if not self.record_overlaps_mask(classification)
        ]

    def record_overlaps_mask(self, record: Type[Classification]) -> bool:
        interval = self.get_interval_where_probe_aligns_to_truth(record)
        if interval is None:
            return False

        overlaps = self.tree.overlap(interval)
        return any(interval.data == iv.data for iv in overlaps)

    @staticmethod
    def get_interval_where_probe_aligns_to_truth(record: Classification) -> Interval:
        raise NotImplementedError()


class PrecisionMasker(Masker):
    @staticmethod
    def get_interval_where_probe_aligns_to_truth(
        record: Classification
    ) -> Optional[Interval]:
        if record.is_unmapped:
            return None

        aligned_pairs = record.get_aligned_pairs(with_seq=True)
        query_interval = aligned_pairs.get_index_of_query_interval(
            Interval(*record.query_probe.interval)
        )
        ref_positions = aligned_pairs.get_ref_positions(
            transform_Nones_into_halfway_positions=True
        )
        ref_positions_query_aligns_to = ref_positions[slice(*query_interval)]
        ref_start, ref_end = (
            math.floor(ref_positions_query_aligns_to[0]),
            math.ceil(ref_positions_query_aligns_to[-1]),
        )
        chromosome = record.ref_probe.chrom

        return Interval(max(0, ref_start), ref_end + 1, chromosome)
