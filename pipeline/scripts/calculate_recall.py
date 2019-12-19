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

number_of_points_in_ROC_curve = float(snakemake.params.number_of_points_in_ROC_curve)

tool = snakemake.wildcards.tool
coverage = snakemake.wildcards.coverage
coverage_threshold = snakemake.wildcards.coverage_threshold
strand_bias_threshold = snakemake.wildcards.strand_bias_threshold
gaps_threshold = snakemake.wildcards.gaps_threshold


# API usage
logging.info(f"Creating calculator")
recall_calculator = RecallCalculator.from_files(
    recall_report_files_for_all_samples
)


min_gt = recall_calculator.get_minimum_gt_conf()
max_gt = recall_calculator.get_maximum_gt_conf()
step_gt = (max_gt - min_gt) / number_of_points_in_ROC_curve
logging.info(
    f"Calculating recall with min_gt = {min_gt}, step_gt = {step_gt}, and max_gt = {max_gt}"
)

gts = []
recalls = []
nb_of_truth_probes_found = []
nb_of_truth_probes_in_total = []
all_gts = list(np.arange(min_gt, max_gt, step_gt))
if len(all_gts) == number_of_points_in_ROC_curve:
    all_gts.append(max_gt)
assert(len(all_gts) == number_of_points_in_ROC_curve + 1)

for gt in all_gts:
    try:
        recall_info = recall_calculator.calculate_recall(gt)
        gts.append(gt)
        recalls.append(recall_info.recall)
        nb_of_truth_probes_found.append(recall_info.true_positives)
        nb_of_truth_probes_in_total.append(recall_info.total)
    except EmptyReportError:
        pass


recall_df = pd.DataFrame(
    data={
        "tool": [tool] * len(gts),
        "coverage": [coverage] * len(gts),
        "coverage_threshold": [coverage_threshold] * len(gts),
        "strand_bias_threshold": [strand_bias_threshold] * len(gts),
        "gaps_threshold": [gaps_threshold] * len(gts),
        "GT": gts,
        "step_GT": list(range(len(gts))),
        "recall": recalls,
        "nb_of_truth_probes_found": nb_of_truth_probes_found,
        "nb_of_truth_probes_in_total": nb_of_truth_probes_in_total
    }
)


# output
logging.info(f"Outputting recall file")
recall_df.to_csv(output, sep="\t")


logging.info(f"Done")