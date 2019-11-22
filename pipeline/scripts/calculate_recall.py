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



from evaluate.calculator import RecallCalculator, EmptyReportError
import pandas as pd
import numpy as np


# setup
recall_report_files_for_all_samples = (
    snakemake.input.recall_report_files_for_all_samples
)
output = Path(snakemake.output.recall_file_for_all_samples)

min_gt = float(snakemake.wildcards.min_gt)
step_gt = float(snakemake.wildcards.step_gt)
max_gt = float(snakemake.wildcards.max_gt)

tool = snakemake.wildcards.tool
coverage = snakemake.wildcards.coverage
coverage_threshold = snakemake.wildcards.coverage_threshold
strand_bias_threshold = snakemake.wildcards.strand_bias_threshold
gaps_threshold = snakemake.wildcards.gaps_threshold
label = f"tool_{tool}_coverage_{coverage}_coverage_threshold_{coverage_threshold}_strand_bias_threshold_{strand_bias_threshold}_gaps_threshold_{gaps_threshold}"


# API usage
logging.info(f"Creating calculator")
recall_calculator = RecallCalculator.from_files(
    recall_report_files_for_all_samples
)


max_gt = min(max_gt, recall_calculator.get_maximum_gt_conf())
logging.info(
    f"Calculating recall with min_gt = {min_gt}, step_gt = {step_gt}, and max_gt = {max_gt}"
)

gts = []
recalls = []
all_gts = list(np.arange(min_gt, max_gt, step_gt)) + [max_gt]
for gt in all_gts:
    try:
        recall = recall_calculator.calculate_recall(gt)
        gts.append(gt)
        recalls.append(recall)
    except EmptyReportError:
        pass


labels = [label] * len(gts)
recall_df = pd.DataFrame(
    data={
        "GT": gts,
        "recall": recalls,
        "label": labels,
    }
)


# output
logging.info(f"Outputting recall file")
recall_df.to_csv(output, sep="\t")


logging.info(f"Done")