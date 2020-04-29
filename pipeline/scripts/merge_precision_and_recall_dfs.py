import pandas as pd

# setup
precision_file = snakemake.input.precision_file
recall_file = snakemake.input.recall_file
output_file = snakemake.output.error_rate_and_recall_file

# read
precision_df = pd.read_csv(precision_file, sep="\t")
recall_df = pd.read_csv(recall_file, sep="\t")

# merge
error_rate_and_recall_df = pd.merge(precision_df, recall_df,
                    on=["tool", "coverage", "coverage_threshold", "strand_bias_threshold", "gaps_threshold", "step_GT"])[
    ["tool", "coverage", "coverage_threshold", "strand_bias_threshold", "gaps_threshold", "step_GT", "error_rate",
     "nb_of_correct_calls", "nb_of_total_calls",
     "recalls_wrt_truth_probes", "nbs_of_truth_probes_found", "nbs_of_truth_probes_in_total",
     "recalls_wrt_variants_where_all_allele_seqs_were_found", "recalls_wrt_variants_found_wrt_alleles",
     "nbs_variants_where_all_allele_seqs_were_found", "nbs_variants_found_wrt_alleles", "nbs_variants_total"]
]

# output
error_rate_and_recall_df.to_csv(output_file, sep="\t")
