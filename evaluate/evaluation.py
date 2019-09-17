import logging
from io import StringIO
from pathlib import Path
from typing import Tuple, Dict, List, Iterable

import pysam

from .bwa import BWA
from .cli import cli
from .mummer import Nucmer, DeltaFilter, ShowSnps
from .query import Query
from .utils import strip_extensions
from evaluate.reporter import RecallReporter
from evaluate.classifier import RecallClassifier


class RecallEvaluation:
    @staticmethod
    def generate_truth_probesets(
        query1: Path,
        query2: Path,
        prefix: Path,
        temp: Path,
        truth_flank: int,
        indels: bool,
    ) -> Tuple[Path, Path]:
        logging.info("Making truth probesets.")
        mummer_snps: StringIO = RecallEvaluation._generate_mummer_snps(
            query1, query2, prefix, truth_flank, indels=indels
        )
        snps_df = ShowSnps.to_dataframe(mummer_snps)
        query1_truth_probes, query2_truth_probes = snps_df.get_probes()
        query1_truth_probes_filepath = RecallEvaluation._write_truth_probeset_to_temp_file(
            query1_truth_probes, query1, temp
        )
        query2_truth_probes_filepath = RecallEvaluation._write_truth_probeset_to_temp_file(
            query2_truth_probes, query2, temp
        )
        return query1_truth_probes_filepath, query2_truth_probes_filepath

    @staticmethod
    def _generate_mummer_snps(
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

    @staticmethod
    def _write_truth_probeset_to_temp_file(
        truth_probes: str, query: Path, temp_folder: Path
    ) -> Path:
        query_name: str = strip_extensions(query).name
        truth_probes_temp_filepath: Path = temp_folder / f"{query_name}.truth_probes.fa"
        truth_probes_temp_filepath.write_text(truth_probes)
        logging.info(
            f"{query_name} truth probes written to: {str(truth_probes_temp_filepath)}"
        )
        return truth_probes_temp_filepath

    @staticmethod
    def generate_pandora_probesets(
        vcf: Path, vcf_ref: Path, samples: Iterable[str], query_flank: int
    ):
        pass


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
    return BWA.map_query_to_ref(panel, probes, output, threads)


def is_mapping_invalid(record: pysam.AlignedSegment) -> bool:
    return any([record.is_unmapped, record.is_secondary, record.is_supplementary])


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
    query1_truth_probes, query2_truth_probes = snps_df.get_probes()

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

    logging.info("Running recall classification")
    classifiers = []
    for sample, sam in [(query1_name, query1_sam), (query2_name, query2_sam)]:
        classifiers.append(RecallClassifier(sam=sam, name=sample))

    reporter = RecallReporter(classifiers=classifiers)
    reporter.save(args.output)

    args.output.close()
    logging.info(f"Recall report written to {args.output.name}")


if __name__ == "__main__":
    main()
