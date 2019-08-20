import logging
from io import StringIO
from pathlib import Path
from typing import Tuple, Dict, List

import pandas as pd
import pysam
from .bwa import BWA
from .cli import cli
from .mummer import Nucmer, DeltaFilter, ShowSnps
from .query import Query
from .utils import strip_extensions, arg_ranges


def generate_mummer_snps(
    reference: Path,
    query: Path,
    prefix: Path = Path("out"),
    flank_width: int = 0,
    indels: bool = False,
    print_header: bool = True,
) -> StringIO:
    logging.info("Generating MUMmer SNPs file.")

    nucmer_params = "--maxmatch"
    nucmer = Nucmer(reference, query, str(prefix), extra_params=nucmer_params)
    nucmer_result = nucmer.run()
    nucmer_result.check_returncode()

    deltafile = Path(str(prefix) + ".delta")
    deltafilter_params = "-1"
    deltafilter = DeltaFilter(deltafile, extra_params=deltafilter_params)
    deltafilter_result = deltafilter.run()
    deltafilter_result.check_returncode()

    filtered_deltafile = prefix.with_suffix(".delta1")
    _ = filtered_deltafile.write_text(deltafilter_result.stdout.decode())

    showsnps_params = "-rlTC"
    showsnps = ShowSnps(
        filtered_deltafile,
        context=flank_width,
        extra_params=showsnps_params,
        indels=indels,
        print_header=print_header,
    )
    showsnps_result = showsnps.run()
    showsnps_result.check_returncode()
    showsnps_content = showsnps_result.stdout.decode()

    snpsfile = prefix.with_suffix(".snps")
    _ = snpsfile.write_text(showsnps_content)

    logging.info("Finished generating MUMmer SNPs file.")

    return StringIO(showsnps_content)


def make_truth_panels(snps_df: pd.DataFrame) -> Tuple[str, str]:
    ref_probes = ""
    query_probes = ""

    idxs = arg_ranges(snps_df.ref_pos.tolist())

    for start, stop in idxs:
        consecutive_positions = snps_df.iloc[slice(start, stop)]
        ref_probe, query_probe = probes_from_consecutive_dataframe(
            consecutive_positions
        )
        ref_probes += ref_probe
        query_probes += query_probe

    return ref_probes, query_probes


def probes_from_consecutive_dataframe(df: pd.DataFrame) -> Tuple[str, str]:
    first_row = df.iloc[0]
    flank_width = int((len(first_row.ref_context) - 1) / 2)
    ref_sub = "".join(df.ref_sub).replace(".", "")
    ref_left_flank = first_row.ref_context[0:flank_width].replace("-", "")
    ref_right_flank = df.iloc[-1].ref_context[flank_width + 1 :].replace("-", "")
    call_start_idx = max(0, len(ref_left_flank))
    call_end_idx = call_start_idx + len(ref_sub)
    ref_name = (
        f">{first_row.ref_chrom}_POS={first_row.ref_pos}_"
        f"CALL_INTERVAL=[{call_start_idx},{call_end_idx})"
    )
    ref_probe = ref_left_flank + ref_sub + ref_right_flank
    ref_probe = f"{ref_name}\n{ref_probe}\n"

    query_sub = "".join(df.query_sub).replace(".", "")
    query_left_flank = first_row.query_context[0:flank_width].replace("-", "")
    query_right_flank = df.iloc[-1].query_context[flank_width + 1 :].replace("-", "")
    call_start_idx = max(0, len(query_left_flank))
    call_end_idx = call_start_idx + len(query_sub)
    query_name = (
        f">{first_row.query_chrom}_POS={first_row.query_pos}_"
        f"CALL_INTERVAL=[{call_start_idx},{call_end_idx})"
    )
    query_probe = query_left_flank + query_sub + query_right_flank
    query_probe = f"{query_name}\n{query_probe}\n"
    return ref_probe, query_probe


def write_vcf_probes_to_file(
    vcf_probes: Dict[str, str], query_name: str, tempdir: Path
) -> Path:
    query_vcf_probes = vcf_probes[query_name]
    query_vcf_probes_path: Path = tempdir / f"{query_name}.query_probes.fa"
    query_vcf_probes_path.write_text(query_vcf_probes)
    logging.info(f"VCF probes written to file: {query_vcf_probes_path}")
    return query_vcf_probes_path


def map_panel_to_probes(
    panel: Path, probes: Path, output: Path = Path(), threads: int = 1
) -> Tuple[pysam.VariantHeader, List[pysam.AlignedSegment]]:
    bwa = BWA(threads)
    bwa.index(str(probes))
    stdout, stderr = bwa.align(panel.read_text())

    # write sam to file if output path given
    if output.name:
        output.write_text(stdout)

    return bwa.parse_sam_string(stdout)


def is_mapping_invalid(record: pysam.AlignedSegment) -> bool:
    return any([record.is_unmapped, record.is_secondary, record.is_supplementary])


def assess_sam_record(record: pysam.AlignedSegment) -> str:
    assessment = ""

    if record.is_unmapped:
        assessment = "unmapped"
    elif record.is_secondary:
        is_correct = do_probes_match(record)
        assessment = "seconday_correct" if is_correct else "secondary_incorrect"

    return assessment


def do_probes_match(record: pysam.AlignedSegment) -> bool:
    truth = record.query_name[-1]

    for query_pos, ref_pos, ref_base in record.get_aligned_pairs(with_seq=True):
        if query_pos == REF_PANEL_FLANK_WIDTH:
            return truth == ref_base

    return False


def main():
    args = cli()

    query1: Path = args.query1
    query1_name: str = strip_extensions(query1).name
    query2: Path = args.query2
    query2_name: str = strip_extensions(query2).name
    prefix: Path = args.temp / f"{query1_name}_{query2_name}"

    mummer_snps: StringIO = generate_mummer_snps(
        query1, query2, prefix, args.truth_flank, indels=args.indels
    )
    snps_df = ShowSnps.to_dataframe(mummer_snps)
    logging.info("Making truth probesets.")
    query1_truth_probes, query2_truth_probes = make_truth_panels(snps_df)

    query1_truth_probes_path: Path = args.temp / f"{query1_name}.truth_probes.fa"
    query2_truth_probes_path: Path = args.temp / f"{query2_name}.truth_probes.fa"
    query1_truth_probes_path.write_text(query1_truth_probes)
    logging.info(
        f"{query1_name} truth probes written to: {str(query1_truth_probes_path)}"
    )
    query2_truth_probes_path.write_text(query2_truth_probes)
    logging.info(
        f"{query2_name} truth probes written to: {str(query2_truth_probes_path)}"
    )

    logging.info("Making probes for VCF")
    samples = [query1_name, query2_name]
    query_vcf = Query(
        args.vcf, args.vcf_ref, samples=samples, flank_width=args.query_flank
    )
    vcf_probes: Dict[str, str] = query_vcf.make_probes()
    query1_vcf_probes_path: Path = write_vcf_probes_to_file(
        vcf_probes, query1_name, args.temp
    )
    query2_vcf_probes_path: Path = write_vcf_probes_to_file(
        vcf_probes, query2_name, args.temp
    )
    logging.info(f"Mapping probes for {query1_name}")
    query1_sam_file = args.temp / (query1_name + ".panel_to_probes.sam")
    query1_header, query1_sam = map_panel_to_probes(
        query1_truth_probes_path,
        query1_vcf_probes_path,
        output=query1_sam_file,
        threads=args.threads,
    )
    logging.info(f"Mapping probes for {query2_name}")
    query2_sam_file = args.temp / (query2_name + ".panel_to_probes.sam")
    query2_header, query2_sam = map_panel_to_probes(
        query2_truth_probes_path,
        query2_vcf_probes_path,
        output=query2_sam_file,
        threads=args.threads,
    )
    # todo: Assess each valid SAM record

    # todo: because of the multi-mapping, need to be careful when assessing records that I only assess mappings that cover the pandora call. Reason being is that if the truth probe maps to the flank of a pandora call, but not the actuall call part of the probe, then we will just get whatever the vcf ref is, which is an unfair comparison.
    # todo: when assessing deletions I think it makes sense to asses the bases either side of the deletion site
    # todo: Write results for each SAM record


if __name__ == "__main__":
    main()
