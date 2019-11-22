from pathlib import Path
import sys
sys.path.append(str(Path().absolute()))
import logging
log_level = "INFO"
logging.basicConfig(
    filename=str(snakemake.log),
    filemode="w",
    level=log_level,
    format="[%(asctime)s]:%(levelname)s: %(message)s",
    datefmt="%d/%m/%Y %I:%M:%S %p",
)



from typing import Dict
from evaluate.query import Query
from evaluate.filtered_vcf_file import FilteredVCFFile
from evaluate.vcf_filters import VCF_Filters
import pysam

# setup
sample_id = snakemake.wildcards.sample_id
vcf_filepath = snakemake.input.vcf
coverage_threshold = float(snakemake.wildcards.coverage_threshold)
strand_bias_threshold = float(snakemake.wildcards.strand_bias_threshold)
gaps_threshold = float(snakemake.wildcards.gaps_threshold)
vcf_ref = Path(snakemake.input.vcf_ref)
flank_width = int(snakemake.params.flank_length)
output = Path(snakemake.output.probeset)


# API usage
logging.info(f"Applying filters to {vcf_filepath}")
filters = VCF_Filters.get_all_VCF_Filters(
    coverage_threshold=coverage_threshold,
    strand_bias_threshold=strand_bias_threshold,
    gaps_threshold=gaps_threshold,
)
with pysam.VariantFile(vcf_filepath) as pysam_variant_file:
    filtered_vcf_file = FilteredVCFFile(pysam_variant_file=pysam_variant_file, filters=filters)

logging.info(f"Making probes")
query_vcf = Query(
    filtered_vcf_file,
    vcf_ref,
    samples=[sample_id],
    flank_width=flank_width,
)
vcf_probes: Dict[str, str] = query_vcf.make_probes()
sample_vcf_probes = vcf_probes[sample_id]


# output
logging.info(f"Writing probes")
output.write_text(sample_vcf_probes)

logging.info(f"Done")