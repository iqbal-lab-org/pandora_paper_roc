from io import StringIO
from pathlib import Path

import pandas as pd
import pysam
import pytest

from evaluate.evaluation import *
from evaluate.mummer import NucmerError, ShowSnps

REF = Path("tests/test_cases/ref.fa")
QUERY = Path("tests/test_cases/query.fa")
SNPS = Path("tests/test_cases/out.snps")


def create_sam_header(name: str, length: int) -> pysam.AlignmentHeader:
    return pysam.AlignmentHeader.from_text(
        f"@SQ	SN:{name}	LN:{length}\n@PG	ID:bwa	PN:bwa	VN:0.7.17-r1188	CL:bwa mem -t 1 panel.fa -"
    )


def test_getMummerSnps_invalidQueryFileRaisesNucmerError():
    reference = REF
    query = Path("foo")
    with pytest.raises(NucmerError):
        generate_mummer_snps(reference, query)


def test_getMummerSnps_validSequenceFilesProducesExpectedSnpsFile():
    reference = REF
    query = QUERY
    prefix = Path("/tmp/ref_query")
    context = 3

    actual = generate_mummer_snps(
        reference, query, prefix, flank_width=context, indels=True, print_header=False
    )
    expected = StringIO(
        """39\tG\t.\t38\t34\t38\t85\t84\tGTAGTAG\tGTA.TAG\t1\t1\tref\tquery
73\tT\tA\t72\t13\t13\t85\t84\tGGATTGA\tGGAATGA\t1\t1\tref\tquery
"""
    )

    assert actual.readlines() == expected.readlines()


def test_isMappingInvalid_unmappedEntry_returnTrue():
    header = create_sam_header("C15154T", 201)
    record = pysam.AlignedSegment.fromstring(
        "GC00004785_pos200_entry0	4	C15154T	124	48	69M	*	0	0	CAAATCGGAAGCTAACAGAGCCAATACGCGCCTTGACGCCCAGGACTATTTTGATTGCCTGCGCTGCTT	*	NM:i:0	MD:Z:69	AS:i:69	XS:i:53",
        header,
    )

    assert is_mapping_invalid(record)


def test_isMappingInvalid_mappedEntry_returnFalse():
    header = create_sam_header("C15154T", 201)
    record = pysam.AlignedSegment.fromstring(
        "GC00004785_pos200_entry0	0	C15154T	124	48	69M	*	0	0	CAAATCGGAAGCTAACAGAGCCAATACGCGCCTTGACGCCCAGGACTATTTTGATTGCCTGCGCTGCTT	*	NM:i:0	MD:Z:69	AS:i:69	XS:i:53",
        header,
    )
    is_mapping_valid = not is_mapping_invalid(record)

    assert is_mapping_valid


def test_isMappingInvalid_supplementaryEntry_returnTrue():
    header = create_sam_header("C15154T", 201)
    record = pysam.AlignedSegment.fromstring(
        "GC00004785_pos200_entry0	2048	C15154T	124	48	69M	*	0	0	CAAATCGGAAGCTAACAGAGCCAATACGCGCCTTGACGCCCAGGACTATTTTGATTGCCTGCGCTGCTT	*	NM:i:0	MD:Z:69	AS:i:69	XS:i:53",
        header,
    )

    assert is_mapping_invalid(record)


def test_isMappingInvalid_secondaryEntry_returnTrue():
    header = create_sam_header("C15154T", 201)
    record = pysam.AlignedSegment.fromstring(
        "GC00004785_pos200_entry0	256	C15154T	124	48	69M	*	0	0	CAAATCGGAAGCTAACAGAGCCAATACGCGCCTTGACGCCCAGGACTATTTTGATTGCCTGCGCTGCTT	*	NM:i:0	MD:Z:69	AS:i:69	XS:i:53",
        header,
    )

    assert is_mapping_invalid(record)


def test_assessSamRecord_unmappedRecordReturnsUnmapped():
    header = create_sam_header(
        "GC00000422_2_SAMPLE=CFT073_POS=603_CALL_INTERVAL=[25,32)_SVTYPE=PH_SNPs_MEAN_FWD_COVG=23_MEAN_REV_COVG=13_GT_CONF=89.5987",
        57,
    )
    record = pysam.AlignedSegment.fromstring(
        ""
        "3_POS=14788_CALL_INTERVAL=[21,22)\t4\t*\t0\t0\t*\t*\t0\t0\tCGCGAAAGCCCTGACCATCTGCACCGTGTCTGACCACATCCGC\t*\tAS:i:0\tXS:i:0",
        header,
    )

    actual = assess_sam_record(record)
    expected = "unmapped"

    assert actual == expected


def test_assessSamRecord_incorrectSecondayAlignmentMismatchReturnsIncorrect():
    flag = 256
    cigar = "43M"
    nm = "NM:i:1"
    md = "MD:Z:21T21"
    mapq = 0
    pos = 5
    query_header = ProbeHeader(chrom="3", pos=14788, interval=Interval(21, 22))
    ref_header = ProbeHeader(
        chrom="GC00000422_2",
        sample="CFT073",
        pos=603,
        interval=Interval(25, 32),
        svtype="PH_SNPs",
        mean_fwd_covg=23,
        mean_rev_covg=13,
        gt_conf=89.5987,
    )
    sequence = "CGCGAAAGCCCTGACCATCTGCACCGTGTCTGACCACATCCGC"
    header = create_sam_header(str(ref_header), 57)
    record = pysam.AlignedSegment.fromstring(
        f"{query_header}\t{flag}\t{ref_header}\t{pos}\t{mapq}\t{cigar}\t*\t0\t0\t{sequence}\t*\t{nm}\t{md}\tAS:i:43\tXS:i:32",
        header,
    )

    actual = assess_sam_record(record)
    expected = "secondary_incorrect"

    assert actual == expected


def test_assessSamRecord_correctSecondayAlignmentReturnsCorrect():
    flag = 256
    cigar = "43M"
    nm = "NM:i:0"
    md = "MD:Z:43"
    mapq = 0
    pos = 5
    query_name = "3_POS=14788_CALL_INTERVAL=[21,22)"
    ref_name = "GC00000422_2_SAMPLE=CFT073_POS=603_CALL_INTERVAL=[25,32)_SVTYPE=PH_SNPs_MEAN_FWD_COVG=23_MEAN_REV_COVG=13_GT_CONF=89.5987"
    sequence = "CGCGAAAGCCCTGACCATCTGCACCGTGTCTGACCACATCCGC"
    header = create_sam_header(ref_name, 57)
    record = pysam.AlignedSegment.fromstring(
        f"{query_name}\t{flag}\t{ref_name}\t{pos}\t{mapq}\t{cigar}\t*\t0\t0\t{sequence}\t*\t{nm}\t{md}\tAS:i:43\tXS:i:32",
        header,
    )

    actual = assess_sam_record(record)
    expected = "secondary_correct"

    assert actual == expected


def test_assessSamRecord_incorrectPrimaryAlignmentMismatchReturnsIncorrect():
    header = create_sam_header(
        "GC00000422_2_SAMPLE=CFT073_POS=603_CALL_INTERVAL=[25,32)_SVTYPE=PH_SNPs_MEAN_FWD_COVG=23_MEAN_REV_COVG=13_GT_CONF=89.5987",
        57,
    )
    record = pysam.AlignedSegment.fromstring(
        "3_POS=14788_CALL_INTERVAL=[21,22)\t0\tGC00000422_2_SAMPLE=CFT073_POS=603_CALL_INTERVAL=[25,32)_SVTYPE=PH_SNPs_MEAN_FWD_COVG=23_MEAN_REV_COVG=13_GT_CONF=89.5987\t5\t60\t43M\t*\t0\t0\tCGCGAAAGCCCTGACCATCTGCACCGTGTCTGACCACATCCGC\t*\tNM:i:1\tMD:Z:21T21\tAS:i:43\tXS:i:32",
        header,
    )

    # query_probe_seq = TTGGCGCGAAAGCCCTGACCATCTGTACCGTGTCTGACCACATCCGCACTCACGAGC
    # truth_probe_seq =     CGCGAAAGCCCTGACCATCTGCACCGTGTCTGACCACATCCGC

    actual = assess_sam_record(record)
    expected = "incorrect"

    assert actual == expected


def test_assessSamRecord_correctPrimaryAlignmentMismatchInFlankReturnsCorrect():
    header = create_sam_header(
        "GC00000422_2_SAMPLE=CFT073_POS=603_CALL_INTERVAL=[25,32)_SVTYPE=PH_SNPs_MEAN_FWD_COVG=23_MEAN_REV_COVG=13_GT_CONF=89.5987",
        57,
    )
    record = pysam.AlignedSegment.fromstring(
        "3_POS=14788_CALL_INTERVAL=[21,22)\t0\tGC00000422_2_SAMPLE=CFT073_POS=603_CALL_INTERVAL=[25,32)_SVTYPE=PH_SNPs_MEAN_FWD_COVG=23_MEAN_REV_COVG=13_GT_CONF=89.5987\t5\t60\t43M\t*\t0\t0\tCGCGAAAGCCCTGACCATCTGCACCGTGTCTGACCACATCCGC\t*\tNM:i:1\tMD:Z:20T22\tAS:i:43\tXS:i:32",
        header,
    )

    # query_probe_seq = TTGGCGCGAAAGCCCTGACCATCTTCACCGTGTCTGACCACATCCGCACTCACGAGC
    # truth_probe_seq =     CGCGAAAGCCCTGACCATCTGCACCGTGTCTGACCACATCCGC

    actual = assess_sam_record(record)
    expected = "correct"

    assert actual == expected


def test_assessSamRecord_correctPrimaryAlignmentReturnsCorrect():
    header = create_sam_header(
        "GC00000422_2_SAMPLE=CFT073_POS=603_CALL_INTERVAL=[25,32)_SVTYPE=PH_SNPs_MEAN_FWD_COVG=23_MEAN_REV_COVG=13_GT_CONF=89.5987",
        57,
    )
    record = pysam.AlignedSegment.fromstring(
        "3_POS=14788_CALL_INTERVAL=[21,22)\t0\tGC00000422_2_SAMPLE=CFT073_POS=603_CALL_INTERVAL=[25,32)_SVTYPE=PH_SNPs_MEAN_FWD_COVG=23_MEAN_REV_COVG=13_GT_CONF=89.5987\t5\t60\t43M\t*\t0\t0\tCGCGAAAGCCCTGACCATCTGCACCGTGTCTGACCACATCCGC\t*\tNM:i:0\tMD:Z:43\tAS:i:43\tXS:i:32",
        header,
    )

    # query_probe_seq = TTGGCGCGAAAGCCCTGACCATCTGCACCGTGTCTGACCACATCCGCACTCACGAGC
    # truth_probe_seq =     CGCGAAAGCCCTGACCATCTGCACCGTGTCTGACCACATCCGC

    actual = assess_sam_record(record)
    expected = "correct"

    assert actual == expected


class TestWholeProbeMaps:
    def test_unmappedRecordReturnsFalse(self):
        ref_name = "reference"
        ref_length = 55
        header = create_sam_header(ref_name, ref_length)
        flag = 4
        cigar = "*"
        nm = ""
        md = ""
        mapq = 0
        pos = 0
        query_name = "INTERVAL=[11,21);"
        ref_name = "*"
        sequence = "AAAAAAAAAAACGGCTCGCATAGACACGACGACGACACGTACGATCGATCAGTCAT"
        sam_string = f"{query_name}\t{flag}\t{ref_name}\t{pos}\t{mapq}\t{cigar}\t*\t0\t0\t{sequence}\t*\tAS:i:0\tXS:i:0"
        record = pysam.AlignedSegment.fromstring(sam_string, header)

        assert not whole_probe_maps(record)

    def test_probeCompletelyMapsReturnsTrue(self):
        ref_name = "reference"
        ref_length = 55
        header = create_sam_header(ref_name, ref_length)
        flag = 0
        cigar = "9S47M"
        nm = "NM:i:0"
        md = "MD:Z:47"
        mapq = 60
        pos = 1
        query_name = "INTERVAL=[11,21);"
        sequence = "AAAAAAAAAAACGGCTCGCATAGACACGACGACGACACGTACGATCGATCAGTCAT"
        sam_string = f"{query_name}\t{flag}\t{ref_name}\t{pos}\t{mapq}\t{cigar}\t*\t0\t0\t{sequence}\t*\t{nm}\t{md}\tAS:i:0\tXS:i:0"
        record = pysam.AlignedSegment.fromstring(sam_string, header)

        assert whole_probe_maps(record)

    def test_probeStartsAtFirstAlignmentPositionMapsReturnsTrue(self):
        ref_name = "reference"
        ref_length = 55
        header = create_sam_header(ref_name, ref_length)
        flag = 0
        cigar = "11S45M"
        nm = "NM:i:0"
        md = "MD:Z:45"
        mapq = 60
        pos = 1
        query_name = "INTERVAL=[11,21);"
        sequence = "AAAAAAAAAAACGGCTCGCATAGACACGACGACGACACGTACGATCGATCAGTCAT"
        sam_string = f"{query_name}\t{flag}\t{ref_name}\t{pos}\t{mapq}\t{cigar}\t*\t0\t0\t{sequence}\t*\t{nm}\t{md}\tAS:i:0\tXS:i:0"
        record = pysam.AlignedSegment.fromstring(sam_string, header)

        assert whole_probe_maps(record)

    def test_probeStartOneBaseBeforeFirstAlignmentPositionMapsReturnsFalse(self):
        ref_name = "reference"
        ref_length = 55
        header = create_sam_header(ref_name, ref_length)
        flag = 0
        cigar = "12S44M"
        nm = "NM:i:0"
        md = "MD:Z:44"
        mapq = 60
        pos = 1
        query_name = "INTERVAL=[11,21);"
        sequence = "AAAAAAAAAAACGGCTCGCATAGACACGACGACGACACGTACGATCGATCAGTCAT"
        sam_string = f"{query_name}\t{flag}\t{ref_name}\t{pos}\t{mapq}\t{cigar}\t*\t0\t0\t{sequence}\t*\t{nm}\t{md}\tAS:i:0\tXS:i:0"
        record = pysam.AlignedSegment.fromstring(sam_string, header)

        assert not whole_probe_maps(record)

    def test_probeStartsThreeBaseBeforeFirstAlignmentPositionMapsReturnsFalse(self):
        ref_name = "reference"
        ref_length = 55
        header = create_sam_header(ref_name, ref_length)
        flag = 0
        cigar = "14S42M"
        nm = "NM:i:0"
        md = "MD:Z:42"
        mapq = 60
        pos = 1
        query_name = "INTERVAL=[11,21);"
        sequence = "AAAAAAAAAAACGGCTCGCATAGACACGACGACGACACGTACGATCGATCAGTCAT"
        sam_string = f"{query_name}\t{flag}\t{ref_name}\t{pos}\t{mapq}\t{cigar}\t*\t0\t0\t{sequence}\t*\t{nm}\t{md}\tAS:i:0\tXS:i:0"
        record = pysam.AlignedSegment.fromstring(sam_string, header)

        assert not whole_probe_maps(record)

    def test_ProbeEndsOneBaseBeforeAlignmentStartsReturnsFalse(self):
        ref_name = "reference"
        ref_length = 55
        header = create_sam_header(ref_name, ref_length)
        flag = 0
        cigar = "21S35M"
        nm = "NM:i:0"
        md = "MD:Z:35"
        mapq = 60
        pos = 1
        query_name = "INTERVAL=[11,21);"
        sequence = "AAAAAAAAAAACGGCTCGCATAGACACGACGACGACACGTACGATCGATCAGTCAT"
        sam_string = f"{query_name}\t{flag}\t{ref_name}\t{pos}\t{mapq}\t{cigar}\t*\t0\t0\t{sequence}\t*\t{nm}\t{md}\tAS:i:0\tXS:i:0"
        record = pysam.AlignedSegment.fromstring(sam_string, header)

        assert not whole_probe_maps(record)

    def test_probeEndsThreeBasesBeforeAlignmentStartsReturnsFalse(self):
        ref_name = "reference"
        ref_length = 55
        header = create_sam_header(ref_name, ref_length)
        flag = 0
        cigar = "23S33M"
        nm = "NM:i:0"
        md = "MD:Z:33"
        mapq = 60
        pos = 1
        query_name = "INTERVAL=[11,21);"
        sequence = "AAAAAAAAAAACGGCTCGCATAGACACGACGACGACACGTACGATCGATCAGTCAT"
        sam_string = f"{query_name}\t{flag}\t{ref_name}\t{pos}\t{mapq}\t{cigar}\t*\t0\t0\t{sequence}\t*\t{nm}\t{md}\tAS:i:0\tXS:i:0"
        record = pysam.AlignedSegment.fromstring(sam_string, header)

        assert not whole_probe_maps(record)

    def test_probeEndsOnLastBaseOfAlignmentReturnsTrue(self):
        ref_name = "reference"
        ref_length = 59
        header = create_sam_header(ref_name, ref_length)
        flag = 0
        cigar = "33M35S"
        nm = "NM:i:0"
        md = "MD:Z:33"
        mapq = 60
        pos = 6
        query_name = "INTERVAL=[23,33);"
        sequence = (
            "AAAAAAAAAAAAAAAAAAAAAAACGGCTCGCATAGACACGACGACGACACGTACGATCGATCAGTCAT"
        )
        sam_string = f"{query_name}\t{flag}\t{ref_name}\t{pos}\t{mapq}\t{cigar}\t*\t0\t0\t{sequence}\t*\t{nm}\t{md}\tAS:i:0\tXS:i:0"
        record = pysam.AlignedSegment.fromstring(sam_string, header)

        assert whole_probe_maps(record)

    def test_probeEndsOneBaseAfterLastBaseOfAlignmentReturnsFalse(self):
        ref_name = "reference"
        ref_length = 59
        header = create_sam_header(ref_name, ref_length)
        flag = 0
        cigar = "32M36S"
        nm = "NM:i:0"
        md = "MD:Z:32"
        mapq = 60
        pos = 6
        query_name = "INTERVAL=[23,33);"
        sequence = (
            "AAAAAAAAAAAAAAAAAAAAAAACGGCTCGCATAGACACGACGACGACACGTACGATCGATCAGTCAT"
        )
        sam_string = f"{query_name}\t{flag}\t{ref_name}\t{pos}\t{mapq}\t{cigar}\t*\t0\t0\t{sequence}\t*\t{nm}\t{md}\tAS:i:0\tXS:i:0"
        record = pysam.AlignedSegment.fromstring(sam_string, header)

        assert not whole_probe_maps(record)

    def test_probeEndsThreeBasesAfterLastBaseOfAlignmentReturnsFalse(self):
        ref_name = "reference"
        ref_length = 59
        header = create_sam_header(ref_name, ref_length)
        flag = 0
        cigar = "30M38S"
        nm = "NM:i:0"
        md = "MD:Z:30"
        mapq = 60
        pos = 6
        query_name = "INTERVAL=[23,33);"
        sequence = (
            "AAAAAAAAAAAAAAAAAAAAAAACGGCTCGCATAGACACGACGACGACACGTACGATCGATCAGTCAT"
        )
        sam_string = f"{query_name}\t{flag}\t{ref_name}\t{pos}\t{mapq}\t{cigar}\t*\t0\t0\t{sequence}\t*\t{nm}\t{md}\tAS:i:0\tXS:i:0"
        record = pysam.AlignedSegment.fromstring(sam_string, header)

        assert not whole_probe_maps(record)

    def test_probeStartsAfterLastBaseOfAlignmentReturnsFalse(self):
        ref_name = "reference"
        ref_length = 59
        header = create_sam_header(ref_name, ref_length)
        flag = 0
        cigar = "22M46S"
        nm = "NM:i:0"
        md = "MD:Z:22"
        mapq = 60
        pos = 6
        query_name = "INTERVAL=[23,33);"
        sequence = (
            "AAAAAAAAAAAAAAAAAAAAAAACGGCTCGCATAGACACGACGACGACACGTACGATCGATCAGTCAT"
        )
        sam_string = f"{query_name}\t{flag}\t{ref_name}\t{pos}\t{mapq}\t{cigar}\t*\t0\t0\t{sequence}\t*\t{nm}\t{md}\tAS:i:0\tXS:i:0"
        record = pysam.AlignedSegment.fromstring(sam_string, header)

        assert not whole_probe_maps(record)
