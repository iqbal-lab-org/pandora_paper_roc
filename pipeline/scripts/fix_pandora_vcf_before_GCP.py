from pathlib import Path
import sys
sys.path.append(str(Path().absolute()))
from typing import List, Deque
import copy
from collections import deque

if __name__=="__main__":
    from fix_vcf_common import FixVCF
else:
    from pipeline.scripts.fix_vcf_common import FixVCF


class FixPandoraVCF(FixVCF):
    def correct_sample_names(self, line: str, suffix: str) -> str:
        words = line.split("\t")
        corrected_words = [word.replace(suffix, "") for word in words]
        corrected_header = "\t".join(corrected_words)
        return corrected_header

    @staticmethod
    def _null_is_called(sample_info_split: List[str]) -> bool:
        called_gt = sample_info_split[0]
        called_null = called_gt == "."
        return called_null

    def get_gt_confs(self, record: str) -> Deque[float]:
        record_split = record.split("\t")
        all_gt_confs = deque()
        for index, word in enumerate(record_split):
            is_sample_info_field = index >= 9
            if is_sample_info_field:
                sample_info = word
                sample_info_split = sample_info.split(":")

                if FixPandoraVCF._null_is_called(sample_info_split):
                    continue

                gt_conf = float(sample_info_split[-1])
                all_gt_confs.append(gt_conf)
        return all_gt_confs


    def set_gt_confs(self, record: str, gt_confs: Deque[float]) -> str:
        record_split = record.split("\t")
        record_split_corrected = []
        for index, word in enumerate(record_split):
            is_sample_info_field = index >= 9
            if is_sample_info_field:
                # correction
                sample_info = word
                sample_info_split = sample_info.split(":")
                sample_info_split_corrected = copy.deepcopy(sample_info_split)

                if not FixPandoraVCF._null_is_called(sample_info_split_corrected):
                    sample_info_split_corrected[-1] = str(gt_confs.popleft())

                word = ":".join(sample_info_split_corrected)
            record_split_corrected.append(word)
        record_corrected = "\t".join(record_split_corrected)
        return record_corrected


    def process_vcf(self, original_vcf, corrected_vcf, technology, coverage, subsampling):
        suffix = f".{coverage}.{subsampling}.{technology}"
        with open(original_vcf) as original_vcf_filehandler,\
             open(corrected_vcf, "w") as corrected_vcf_filehandler:
            headers, records = self.get_header_and_record_lines(original_vcf_filehandler)
            corrected_headers = self.correct_headers(headers, suffix)
            corrected_records = self.correct_records(records)
            print("\n".join(corrected_headers), file=corrected_vcf_filehandler)
            print("\n".join(corrected_records), file=corrected_vcf_filehandler)


if __name__=="__main__":
    # setup
    pandora_original_vcf = snakemake.input.pandora_original_vcf
    pandora_vcf_corrected = snakemake.output.pandora_vcf_corrected
    technology = snakemake.wildcards.technology
    coverage = snakemake.wildcards.coverage
    subsampling = snakemake.wildcards.subsampling
    fixer = FixPandoraVCF()
    fixer.process_vcf(pandora_original_vcf, pandora_vcf_corrected, technology, coverage, subsampling)
