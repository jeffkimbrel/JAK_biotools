#!/usr/bin/env python

import argparse
import pandas as pd
from tqdm import tqdm
import os

from jakomics.fastq import FASTQ
from jakomics import colors
import jak_utils

# OPTIONS #####################################################################
parser = argparse.ArgumentParser(
    description='test')

parser.add_argument('-s', '--samples',
                    help="excel file with samples in S, F, R, I columns",
                    required=True)

parser.add_argument('-a', '--amplicons', '--amplicon',
                    action='store_true',
                    help='Run amplicon workflow instead of shotgun workflow')

parser.add_argument('-q', '--quiet',
                    action='store_false',
                    help='Print out commands')

parser.add_argument('-m', '--memory',
                    help="Memory to pass to bbtools",
                    required=False,
                    default="Xmx8g")

parser.add_argument('-t', '--threads',
                    help="Threads to pass to bbtools",
                    required=False,
                    default=8)

parser.add_argument('--out',
                    help="File to write results to",
                    default="fastq_filter_results.txt",
                    required=False)

args = parser.parse_args()


def format_stats(sample_series, filter_type, stats):

    d = {}
    for step in stats:
        for type in stats[step]:
            d[filter_type + '_' + type + '_' + step] = stats[step][type]

    new = pd.Series(name=sample_series.name,
                    data=d
                    )
    sample_series = sample_series.append(new)

    return sample_series


if __name__ == "__main__":
    jak_utils.header()
    files = pd.read_excel(args.samples, index_col=0, engine='openpyxl')

    contam_seqs = jak_utils.get_yaml("contams_db")
    pbar = tqdm(total=len(files.index), desc="Filtered", unit=" fastq files")

    df = pd.DataFrame(columns=['ORDER_VERIFIED'])
    for sample, row in files.iterrows():
        d = FASTQ(sample, row)

        d.verify_read_pairs(echo=args.quiet, run=True, verify=True)
        sample_series = pd.Series(name=d.sample, data={'ORDER_VERIFIED': d.ordered})

        if args.amplicons:
            cf = d.contaminant_filtering(contam_seqs,
                                         echo=args.quiet,
                                         mem=args.memory,
                                         threads=args.threads)
            sample_series = format_stats(sample_series, 'CF', cf)

        else:
            rt = d.adapter_trimming(contam_seqs,
                                    echo=args.quiet,
                                    mem=args.memory,
                                    threads=args.threads)
            sample_series = format_stats(sample_series, 'RT', rt)

            cf = d.contaminant_filtering(contam_seqs,
                                         echo=args.quiet,
                                         mem=args.memory,
                                         threads=args.threads)
            sample_series = format_stats(sample_series, 'CF', cf)

            qf = d.quality_filtering(echo=args.quiet,
                                     mem=args.memory,
                                     threads=args.threads)
            sample_series = format_stats(sample_series, 'QF', qf)

        df = df.append(sample_series, ignore_index=False)
        pbar.update(1)

    # write to file with comments
    if os.path.exists(args.out):
        os.remove(args.out)
    f = open(args.out, 'a')
    for c in jak_utils.header(r=True):
        print(f'# {c}', file=f)
    for arg in vars(args):
        print(f'# ARG {arg} = {getattr(args, arg)}', file=f)

    df.to_csv(f, sep="\t", index=True, index_label="SAMPLE")
