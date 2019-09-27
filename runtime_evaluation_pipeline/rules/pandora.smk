rule copy_PRG_to_output_folder:
    input:
        PRG_original_path = data_folder / "{PRG_name}"
    output:
        PRG_output_path = "analysis/PRGs/{PRG_name}---threads_{threads}/{PRG_name}"
    threads: 1
    resources:
        mem_mb = 2000
    log:
        "analysis/logs/copy_PRG_to_output_folder/{PRG_name}---threads_{threads}.log"
    shell: "cp {input.PRG_original_path} {output.PRG_output_path} 2>{log}"


rule index_PRG:
    input:
         PRG = rules.copy_PRG_to_output_folder.output.PRG_output_path,
    output:
         index_done_flag = touch("analysis/index/{PRG_name}---threads_{threads}.index_done_flag")
    resources:
        mem_mb = mem_mb
    threads:
        lambda wildcards: int(wildcards.threads)
    log:
        "analysis/logs/index_PRG/{PRG_name}---threads_{threads}.log"
    singularity:
        singularity_image
    shell: f"/usr/bin/time --verbose pandora index -w {window_size} -k {kmer_size} -t {{wildcards.threads}} {{input.PRG}} >{{log}} 2>{{log}}"


rule map_reads_to_PRG:
    input:
         PRG = rules.copy_PRG_to_output_folder.output.PRG_output_path,
         index_done_flag = rules.index_PRG.output.index_done_flag,
         reads = data_folder / "{reads}",
    output:
         output_folder = directory("analysis/map/{PRG_name}---threads_{threads}---reads_{reads}"),
         map_done_flag = touch("analysis/map/{PRG_name}---threads_{threads}---reads_{reads}.map_reads_to_PRG.done"),
    resources:
        mem_mb = mem_mb
    threads:
        lambda wildcards: int(wildcards.threads)
    log:
        "analysis/logs/map_reads_to_PRG/{PRG_name}---threads_{threads}---reads_{reads}.log"
    singularity:
        singularity_image
    shell: f"/usr/bin/time --verbose pandora map -p {{input.PRG}} -r {{input.reads}} -o {{output.output_folder}} -w {window_size} -k {kmer_size} -t {{wildcards.threads}} --genotype --illumina >{{log}}  2>{{log}}"


rule compare_samples:
    input:
         PRG = rules.copy_PRG_to_output_folder.output.PRG_output_path,
         index_done_flag = rules.index_PRG.output.index_done_flag,
         samples = data_folder / "{samples}",
    output:
         output_folder = directory("analysis/compare/{PRG_name}---threads_{threads}---samples_{samples}"),
         compare_done_flag = touch("analysis/compare/{PRG_name}---threads_{threads}---samples_{samples}.compare_samples.done"),
    resources:
        mem_mb = mem_mb
    threads:
        lambda wildcards: int(wildcards.threads)
    log:
        "analysis/logs/compare_samples/{PRG_name}---threads_{threads}---samples_{samples}.log"
    singularity:
        singularity_image
    shell: f"/usr/bin/time --verbose pandora compare -p {{input.PRG}} -r {{input.samples}} -o {{output.output_folder}} -w {window_size} -k {kmer_size} -t {{wildcards.threads}} --genotype --illumina >{{log}}  2>{{log}}"
