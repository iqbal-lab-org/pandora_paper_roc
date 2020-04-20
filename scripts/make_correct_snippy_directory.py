# configs
technologies=["illumina"]
coverages=["100x"]
subsamplings=["random"]
samples=["063_STEC", "CFT073", "Escherichia_coli_MINF_1A", "Escherichia_coli_MINF_1D", "Escherichia_coli_MINF_2E", "Escherichia_coli_MINF_7C", "Escherichia_coli_MINF_8D", "Escherichia_coli_MINF_9A", "Escherichia_coli_MSB1_1A", "Escherichia_coli_MSB1_3B", "Escherichia_coli_MSB1_3I", "Escherichia_coli_MSB1_4E", "Escherichia_coli_MSB1_4I", "Escherichia_coli_MSB1_6C", "Escherichia_coli_MSB1_6J", "Escherichia_coli_MSB1_7A", "Escherichia_coli_MSB1_7C", "Escherichia_coli_MSB1_8B", "Escherichia_coli_MSB1_8G", "Escherichia_coli_MSB1_9D", "Escherichia_coli_MSB1_9I", "Escherichia_coli_MSB2_1A", "H131800734", "ST38"]
references=["CN928163.2", "CP010116.1", "CP010121.1", "CP010170.1", "CP010171.1", "CP010226.1", "CP010230.1", "CP018206.1", "NC_004431.1", "NC_007779.1", "NC_010498.1", "NC_011742.1", "NC_011993.1", "NC_017646.1", "NC_022648.1", "NZ_CP008697.1", "NZ_CP009859.1", "NZ_CP011134.1", "NZ_CP013483.1", "NZ_CP015228.1", "NZ_CP016007.1", "NZ_CP018109.1", "NZ_LN995446.1", "NZ_LT632320.1", "NZ_NG941718.1"]
input_dir="/hps/nobackup/iqbal/leandro/snippy_analysis_pipeline/unprocessed_data"
output_dir="/hps/nobackup/iqbal/leandro/snippy_analysis_pipeline/processed_data"



from itertools import product
from pathlib import Path
import os

def create_parent_dirs(vcf_to):
    parent_dir = Path(vcf_to).parent
    parent_dir.mkdir(parents=True, exist_ok=True)

def create_symbolic_links(from_path, to_path):
    vcf_from = from_path+".vcf"
    ref_from =  from_path+".ref.fa"
    vcf_to = to_path+".vcf"
    ref_to = to_path+".ref.fa"
    create_parent_dirs(vcf_to)
    os.symlink(vcf_from, vcf_to)
    os.symlink(ref_from, ref_to)


for technology, coverage, subsampling, sample, reference in \
        product(technologies, coverages, subsamplings, samples, references):
    from_path = f"{input_dir}/{technology}/{coverage}/{subsampling}/{sample}/snippy_{coverage}.{reference}"
    to_path =  f"{output_dir}/{technology}/{coverage}/{subsampling}/{sample}/snippy_{sample}_AND_{reference}"
    create_symbolic_links(from_path, to_path)