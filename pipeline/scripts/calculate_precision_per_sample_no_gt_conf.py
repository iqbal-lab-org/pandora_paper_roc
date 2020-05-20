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



from evaluate.calculator import PrecisionCalculator, EmptyReportError
from evaluate.report import PrecisionReport
import pandas as pd


# setup
precision_report_files_for_one_sample = (
    snakemake.input.precision_report_files_for_one_sample
)
output = Path(snakemake.output.precision_file_for_one_sample)
sample = snakemake.wildcards.sample
tool = snakemake.wildcards.tool
coverage = snakemake.wildcards.coverage
coverage_threshold = snakemake.wildcards.coverage_threshold
strand_bias_threshold = snakemake.wildcards.strand_bias_threshold
gaps_threshold = snakemake.wildcards.gaps_threshold
gt_conf_percentiles = [0]

# API usage
logging.info(f"Loading report")
precision_report = PrecisionReport.from_files(precision_report_files_for_one_sample)

logging.info(f"Creating calculator")
precision_calculator = PrecisionCalculator(precision_report)

logging.info(f"Calculating precision")
precision_df = precision_calculator.get_precision_report(gt_conf_percentiles)

metadata_df = pd.DataFrame(
    data={
        "sample": [sample] * len(precision_df),
        "tool": [tool] * len(precision_df),
        "coverage": [coverage] * len(precision_df),
        "coverage_threshold": [coverage_threshold] * len(precision_df),
        "strand_bias_threshold": [strand_bias_threshold] * len(precision_df),
        "gaps_threshold": [gaps_threshold] * len(precision_df),
    }
)
output_df = pd.concat([precision_df, metadata_df], axis=1)


# output
logging.info(f"Outputting precision file")
output_df.to_csv(output, sep="\t", index=False)

logging.info(f"Done")
