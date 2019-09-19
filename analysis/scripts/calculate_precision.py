from pathlib import Path
import sys

sys.path.append(str(Path().absolute()))
import logging

log_level = "DEBUG"
logging.basicConfig(
    filename=str(snakemake.log),
    filemode="w",
    level=log_level,
    format="[%(asctime)s]:%(levelname)s: %(message)s",
    datefmt="%d/%m/%Y %I:%M:%S %p",
)

from evaluate.calculator import PrecisionCalculator, EmptyReportError
import pandas as pd
import numpy as np

precision_report_files_for_tool_and_coverage = (
    snakemake.input.precision_report_files_for_tool_and_coverage
)
precision_calculator = PrecisionCalculator.from_files(
    precision_report_files_for_tool_and_coverage
)

output = Path(snakemake.output.precision_file_for_tool_and_coverage)

min_gt = float(snakemake.wildcards.min_gt)
step_gt = float(snakemake.wildcards.step_gt)
max_gt = float(snakemake.wildcards.max_gt)
max_gt = min(max_gt, precision_calculator.get_maximum_gt_conf())

logging.info(
    f"Generating precision file with min_gt = {min_gt}, step_gt = {step_gt}, and max_gt = {max_gt}"
)

gts = []
precisions = []
error_rates = []
all_gts = list(np.arange(min_gt, max_gt, step_gt)) + [max_gt]
for gt in all_gts:
    try:
        precision = precision_calculator.calculate_precision(gt)
        gts.append(gt)
        precisions.append(precision)
        error_rates.append(1 - precision)
    except EmptyReportError:
        pass

labels = [snakemake.wildcards.tool_and_coverage] * len(gts)
precision_df = pd.DataFrame(
    data={
        "GT": gts,
        "precision": precisions,
        "error_rate": error_rates,
        "label": labels,
    }
)
precision_df.to_csv(output, sep="\t")
