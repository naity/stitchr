#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
thimble.py

Runs stiTChR in a high-throughput manner, on a tab separated input file.

No fancy backronym or contrived silent capitals - it just helps you stitch faster.

"""


import functions as fxn
import stitchr as st
import warnings
import argparse
import sys
import os
from time import time

__version__ = '0.5.1'
__author__ = 'Jamie Heather'
__email__ = 'jheather@mgh.harvard.edu'

sys.tracebacklimit = 0  # uncomment when debugging


def args():
    """
    args(): Obtains command line arguments which dictate the script's behaviour
    """

    # Help flag
    parser = argparse.ArgumentParser(description="thimble v" + str(__version__) + '\n' +
                                                 ": Run stiTChR on multiple and paired TCRs")

    # Input and output options
    parser.add_argument('-in', '--in_file', required=True, type=str,
                        help="Tab-separated input file. Must fit the format of the example file. Required.")

    parser.add_argument('-o', '--out_file', required=True, type=str,
                        help="Path/file name for output tsv file. Required.")

    parser.add_argument('-s', '--species', required=False, type=str,
                        help="Species. Optional. Default = 'HUMAN', options depend on directories in Data directory.")

    parser.add_argument('-xg', '--extra_genes', action='store_true', required=False, default=False,
                        help="Optional flag to use additional (non-database/-natural) sequences in "
                             "the \'additional-genes.fasta\' file.")

    parser.add_argument('-sl', '--seamless', action='store_true', required=False, default=False,
                        help="Optional flag to integrate known nucleotide sequences seamlessly. \nNB: "
                             "nucleotide sequences covering the CDR3 junction with additional V gene context required.")

    parser.add_argument('-r', '--receptor', required=False, type=str,
                        help="Receptor to stitch, alpha/beta or gamma/delta TCR. Optional. Give double or single digits"
                             " (e.g. 'ab', 'gd', 'd', 'b').")

    parser.add_argument('-p', '--preferred_alleles_path', required=False, type=str, default='',
                        help="Path to a file of preferred alleles to use when no allele specified (instead of *01). "
                             "Optional.")

    parser.add_argument('-cu', '--codon_usage', required=False, type=str,
                        help="Path to a file of Kazusa-formatted codon usage frequencies. Optional.")

    parser.add_argument('-jt', '--j_warning_threshold', required=False, type=int, default=3,
                        help="J gene substring length warning threshold. Default = 3. "
                             "Decrease to get fewer notes on short J matches. Optional.")

    return parser.parse_args()


def locus_to_trx(trx_str):
    """
    :param trx_str: str containing (a) reference to a specific locus/loci (e.g. TRA/TRB or TRG/TRD)
    :return: same string, but with those loci specific IDs replaced with generic TR1/TR2 strings
    """
    return trx_str.replace('TRA', 'TR1').replace('TRB', 'TR2').replace('TRG', 'TR1').replace('TRD', 'TR2')


in_headers = {'TRA/TRB': ['TCR_name', 'TRAV', 'TRAJ', 'TRA_CDR3', 'TRBV', 'TRBJ', 'TRB_CDR3',
                          'TRAC', 'TRBC', 'TRA_leader', 'TRB_leader', 'Linker', 'Link_order',
                          'TRA_5_prime_seq', 'TRA_3_prime_seq', 'TRB_5_prime_seq', 'TRB_3_prime_seq'],
              'TRG/TRD': ['TCR_name', 'TRGV', 'TRGJ', 'TRG_CDR3', 'TRDV', 'TRDJ', 'TRD_CDR3',
                          'TRGC', 'TRDC', 'TRG_leader', 'TRD_leader', 'Linker', 'Link_order',
                          'TRG_5_prime_seq', 'TRG_3_prime_seq', 'TRD_5_prime_seq', 'TRD_3_prime_seq']}

convert_fields = {'TRAV': 'v', 'TRAJ': 'j', 'TRA_CDR3': 'cdr3', 'TRBV': 'v', 'TRBJ': 'j', 'TRB_CDR3': 'cdr3',
                  'TRAC': 'c', 'TRBC': 'c', 'TRA_leader': 'l', 'TRB_leader': 'l', 'TCR_name': 'name',
                  'TRA_5_prime_seq': '5_prime_seq', 'TRA_3_prime_seq': '3_prime_seq',
                  'TRB_5_prime_seq': '5_prime_seq', 'TRB_3_prime_seq': '3_prime_seq',
                  'TRGV': 'v', 'TRGJ': 'j', 'TRG_CDR3': 'cdr3', 'TRDV': 'v', 'TRDJ': 'j', 'TRD_CDR3': 'cdr3',
                  'TRGC': 'c', 'TRDC': 'c', 'TRG_leader': 'l', 'TRD_leader': 'l',
                  'TRG_5_prime_seq': '5_prime_seq', 'TRG_3_prime_seq': '3_prime_seq',
                  'TRD_5_prime_seq': '5_prime_seq', 'TRD_3_prime_seq': '3_prime_seq'}

stitch_list_fields = ['_name', 'V', 'J', 'C', '_CDR3', '_leader', '_5_prime_seq', '_3_prime_seq']

out_headers = {'TRA/TRB': ['TCR_name', 'TRA_nt', 'TRB_nt', 'TRA_aa', 'TRB_aa',
                           'TRAV', 'TRAJ', 'TRA_CDR3', 'TRBV', 'TRBJ', 'TRB_CDR3',
                           'TRAC', 'TRBC', 'TRA_leader', 'TRB_leader', 'Linker', 'Link_order',
                           'TRA_5_prime_seq', 'TRA_3_prime_seq', 'TRB_5_prime_seq', 'TRB_3_prime_seq',
                           'Linked_nt', 'Linked_aa', 'Warnings/Errors'],
               'TRG/TRD': ['TCR_name', 'TRG_nt', 'TRD_nt', 'TRG_aa', 'TRD_aa',
                           'TRGV', 'TRGJ', 'TRG_CDR3', 'TRDV', 'TRDJ', 'TRD_CDR3',
                           'TRGC', 'TRDC', 'TRG_leader', 'TRD_leader', 'Linker', 'Link_order',
                           'TRG_5_prime_seq', 'TRG_3_prime_seq', 'TRD_5_prime_seq', 'TRD_3_prime_seq',
                           'Linked_nt', 'Linked_aa', 'Warnings/Errors']}

if __name__ == '__main__':

    # Get input arguments, get the required data read in
    fxn.check_scripts_dir()
    input_args = vars(args())
    start = time()

    # Get species, in order of command line arg > inferred from input file name > default human
    if input_args['species']:
        if input_args['species'].upper() in fxn.find_species_covered():
            species = input_args['species'].upper()
        else:
            raise IOError("No data available for requested species: " + input_args['species'])
    else:
        species_inference = fxn.infer_species(input_args['in_file'])
        if species_inference:
            species = species_inference
        else:
            species = 'HUMAN'

    codons = fxn.get_optimal_codons(input_args['codon_usage'], species)
    linker_dict = fxn.get_linker_dict()

    tcr_dat = {}
    tcr_functionality = {}
    preferences = {}

    # Figure out whether a/b or g/d
    if input_args['receptor']:
        input_receptor = input_args['receptor'].upper()
        if ('A' in input_receptor or 'B' in input_receptor) and not ('G' in input_receptor or 'D' in input_receptor):
            receptor = 'TRA/TRB'
        elif ('G' in input_receptor or 'D' in input_receptor) and not ('A' in input_receptor or 'B' in input_receptor):
            receptor = 'TRG/TRD'
        else:
            raise IOError("Unable to determine receptor from '-r' command string: " + input_receptor + ". ")

    else:  # If not explicitly provided, infer from input TSV headers
        with fxn.opener(input_args['in_file']) as in_file:
            for line in in_file:
                if 'TRAV' in line and 'TRGV' not in line:
                    receptor = 'TRA/TRB'
                elif 'TRGV' in line and 'TRAV' not in line:
                    receptor = 'TRG/TRD'
                else:
                    raise IOError("Unable to determine receptor from input file header, please check template. ")
                break

    # Define the individual receptors (chains or loci, i.e. TRA and TRB or TRG and TRD) in play
    r1, r2 = receptor.split('/')
    for c in [r1, r2]:

        tmp_tcr_dat, tmp_functionality, partial = fxn.get_imgt_data(c, st.gene_types, species)
        tcr_dat[c] = tmp_tcr_dat
        tcr_functionality[c] = tmp_functionality

        if 'extra_genes' in input_args:
            if input_args['extra_genes']:
                tcr_dat[c], tcr_functionality[c] = fxn.get_additional_genes(tcr_dat[c], tcr_functionality[c])
                input_args['skip_c_checks'] = True
            else:
                input_args['skip_c_checks'] = False

        # Allow for provision of preferred alleles
        if input_args['preferred_alleles_path']:
            preferences[c] = fxn.get_preferred_alleles(input_args['preferred_alleles_path'], list(fxn.regions.values()),
                                                       tcr_dat[c], partial, c)
        else:
            preferences[c] = ''

    # Then go through in file and stitch each TCR on each line
    if not os.path.isfile(input_args['in_file']):
        raise IOError(input_args['in_file'] + " not detected - please check and specify in file again.")

    with fxn.opener(input_args['in_file']) as in_file:

        line_count = 0
        out_data = ['\t'.join(out_headers[receptor])]

        for line in in_file:

            bits = line.replace('\n', '').replace('\r', '').replace('\"', '').split('\t')

            # Check there's the right number of columns (with the right headers)
            if line_count == 0:
                if bits != in_headers[receptor]:
                    raise ValueError("Headers in input file don't match the expectations - please check template.")

            else:
                # Generate a dict per line ...
                sorted_row_bits = {x: '' for x in out_headers[receptor]}

                if len(bits) != len(in_headers[receptor]):  # Pad entries from tsvs where whitespace on right is missing
                    bits += [''] * (len(in_headers[receptor]) - len(bits))

                for i in range(len(in_headers[receptor])):
                    sorted_row_bits[in_headers[receptor][i]] = bits[i]

                # ... along with chain-specific dicts which are then folded into
                for c in [r1, r2]:

                    with warnings.catch_warnings(record=True) as chain_warnings:
                        warnings.simplefilter("always")

                        tcr_bits = {'skip_c_checks': input_args['skip_c_checks'], 'species': species}
                        if 'seamless' in input_args:
                            if input_args['seamless']:
                                tcr_bits['seamless'] = True

                        # Convert naming to output formats
                        for field in [x for x in sorted_row_bits if c in x]:
                            # if sorted_row_bits[field]:
                            if field in convert_fields:
                                tcr_bits[convert_fields[field]] = sorted_row_bits[field]

                        # Determine whether there's supposed to be a TCR for this chain
                        if len(tcr_bits) > 1:

                            # At the very least we need the relevant TCR info (V/J/CDR3)
                            if not all(section in tcr_bits for section in ['v', 'j', 'cdr3']):
                                warnings.warn("Incomplete TCR information - need V/J/CDR3 as minimum.")

                            else:
                                tcr_bits = fxn.autofill_input(tcr_bits, c)
                                tcr_bits = fxn.tweak_thimble_input(tcr_bits)

                                try:
                                    out_list, stitched, offset = st.stitch(tcr_bits, tcr_dat[c], tcr_functionality[c],
                                                                           partial, codons,
                                                                           input_args['j_warning_threshold'],
                                                                           preferences[c])
                                    sorted_row_bits[c + '_nt'] = stitched
                                    sorted_row_bits[c + '_aa'] = fxn.translate_nt('N' * offset + stitched)
                                    sorted_row_bits.update(dict(list(zip([c + x for x in stitch_list_fields],
                                                                         out_list))))

                                except Exception as message:
                                    sorted_row_bits['Warnings/Errors'] += '(' + c + ') ' + str(message)
                                    sorted_row_bits['Warnings/Errors'] += 'Cannot stitch a sequence for ' + c + '. '

                        # Store all chain related warning messages too, in same field, ignoring irrelevant errors
                        sorted_row_bits['Warnings/Errors'] += ' '.join(
                            ['(' + c + ') ' + str(chain_warnings[x].message) for x in range(len(chain_warnings))
                             if 'DeprecationWarning' not in str(chain_warnings[x].category)])

                with warnings.catch_warnings(record=True) as link_warnings:
                    warnings.simplefilter("always")

                    # If sequences are to be linked, determine the appropriate linker sequence and join together
                    if sorted_row_bits['Linker']:

                        if sorted_row_bits['Link_order']:
                            sorted_row_bits['Link_order'] = sorted_row_bits['Link_order'].upper()

                            # Only allow valid orders
                            if sorted_row_bits['Link_order'] not in [r2[2]+r1[2], r1[2]+r2[2]]:
                                warnings.warn("Error: given link order not valid (not " + r1[2]+r2[2] + " or"
                                              " " + r2[2]+r1[2] + ") - defaulting to " + r2[2]+r1[2] + ".")
                                sorted_row_bits['Link_order'] = r2[2]+r1[2]

                        else:
                            # Default option is B
                            sorted_row_bits['Link_order'] = r2[2]+r1[2]

                        tr1, tr2 = sorted_row_bits['Link_order'][0], sorted_row_bits['Link_order'][1]

                        if sorted_row_bits[r1 + '_nt'] and sorted_row_bits[r2 + '_nt']:
                            try:
                                linker_seq = fxn.get_linker_seq(sorted_row_bits['Linker'], linker_dict)

                                linked = sorted_row_bits['TR' + tr1 + '_nt'] + linker_seq + \
                                         sorted_row_bits['TR' + tr2 + '_nt']
                                sorted_row_bits['Linked_nt'] = linked
                                sorted_row_bits['Linked_aa'] = fxn.translate_nt('N' * offset + linked)

                                # Add warnings if sequences applied at maybe the wrong ends of things
                                if (sorted_row_bits[r1 + '_5_prime_seq'] and ord == r2[2]+r1[2]) or \
                                        (sorted_row_bits[r2 + '_5_prime_seq'] and ord == r1[2]+r2[2]):
                                    warnings.warn("Warning: " + ord + " order specified, but "
                                                  "3' chain has an additional 5' sequence provided. ")

                                if (sorted_row_bits[r1 + '_3_prime_seq'] and ord == r1[2]+r2[2]) or \
                                        (sorted_row_bits[r2 + '_3_prime_seq'] and ord == r2[2]+r1[2]):
                                    warnings.warn("Warning: " + ord + " order specified, but "
                                                  "5' chain has an additional 3' sequence provided. ")

                            # Store any error messages
                            except Exception as message:
                                sorted_row_bits['Warnings/Errors'] += str(message)

                        else:
                            warnings.warn("Error: need both a TR" + r1 + " and TR" + r2 + " to link. ")

                    # And add any warnings/errors derived from the linkage
                    if sorted_row_bits['Warnings/Errors']:
                        sorted_row_bits['Warnings/Errors'] += ' '.join(
                            ['(Link) ' + str(link_warnings[x].message) for x in range(len(link_warnings))
                             if 'DeprecationWarning' not in str(link_warnings[x].category)])
                    else:
                        sorted_row_bits['Warnings/Errors'] = "[None]"

                # Store output as one long string, for a single write-out once input file is finished
                out_data.append('\t'.join([sorted_row_bits[x] for x in out_headers[receptor]]))

            line_count += 1

    time_taken = time() - start
    print("Took", str(round(time_taken, 2)), "seconds")

    # Write out data
    if not input_args['out_file'].lower().endswith('.tsv'):
        input_args['out_file'] += '.tsv'

    with open(input_args['out_file'], 'w') as out_file:
        out_string = '\n'.join(out_data)
        out_file.write(out_string)
