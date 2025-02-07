# -*- coding: utf-8 -*-

"""
stitchrfunctions.py

Functions for stiTChR and its related scripts
"""

import collections as coll
import gzip
import os
import re
import sys
import textwrap
import datetime
import warnings

# Ensure correct importlib-resources function imported
if sys.version_info < (3, 9):
    import importlib_resources                              # PyPI
else:
    import importlib.resources as importlib_resources       # importlib.resources

__version__ = '1.2.2'
__author__ = 'Jamie Heather'
__email__ = 'jheather@mgh.harvard.edu'

sys.tracebacklimit = 0  # comment when debugging


data_files = importlib_resources.files("Data")
additional_genes_file = str(data_files / 'additional-genes.fasta')
linkers_file = str(data_files / 'linkers.tsv')
data_dir = os.path.dirname(additional_genes_file)
gui_examples_dir = os.path.join(data_dir, 'GUI-Examples')


def custom_formatwarning(warning_msg, *args, **kwargs):
    """
    Function to make warnings.warn output just the warning text, not the underlying code
    See https://stackoverflow.com/questions/2187269/print-only-the-message-on-warnings
    """
    return str(warning_msg) + '\n'


def read_fa(ff):
    """
    :param ff: opened fasta file
    read_fa(file):Heng Li's Python implementation of his readfq function (tweaked to only bother with fasta)
    https://github.com/lh3/readfq/blob/master/readfq.py
    """

    last = None                                 # this is a buffer keeping the last unprocessed line
    while True:                                 # mimic closure
        if not last:                            # the first record or a record following a fastq
            for l in ff:                        # search for the start of the next record
                if l[0] in '>':                 # fasta header line
                    last = l[:-1]               # save this line
                    break
        if not last:
            break
        name, seqs, last = last[1:], [], None
        for l in ff:                            # read the sequence
            if l[0] in '>':
                last = l[:-1]
                break
            seqs.append(l[:-1])
        if not last or last[0] != '+':          # this is a fasta record
            yield name, ''.join(seqs), None     # yield a fasta record
            if not last:
                break
        else:
            raise IOError("Input file does not appear to be a FASTA file - please check and try again")


def fastafy(gene, seq_line):
    """
    :param gene: Gene symbol, extracted from the read id
    :param seq_line: Total protein primary sequence, extracted from input FASTA/generated by in silico splicing
    :return: An output-compatible FASTA entry ready for writing to file
    """
    return ">" + gene + "\n" + textwrap.fill(seq_line, 60) + "\n"


def today():
    """
    :return: Today's day, in ISO format
    """
    return datetime.datetime.today().date().isoformat()


def nest():
    """
    Create nested defaultdicts
    """
    return coll.defaultdict(list)


def nest_counter():
    """
    Create nested counters
    """
    return coll.Counter()


def get_chain(v, j):
    """
    :param v: From input args
    :param j: From input args
    :return: TRA or TRB (the chain in use) or throw an error
    """

    if v.startswith('TRB') and j.startswith('TRB'):
        return 'TRB'
    elif (v.startswith('TRA') or v.startswith('TRD')) and j.startswith('TRA'):
        return 'TRA'
    elif v.startswith('TRG') and j.startswith('TRG'):
        return 'TRG'
    elif v.startswith('TRD') and j.startswith('TRD'):
        return 'TRD'

    elif v.startswith('IGH') and j.startswith('IGH'):
        return 'IGH'
    elif v.startswith('IGL') and j.startswith('IGL'):
        return 'IGL'
    elif v.startswith('IGK') and j.startswith('IGK'):
        return 'IGK'

    else:
        raise ValueError("Please ensure you're providing full IMGT gene names (allele number optional), " +
                         "both from the same chain (alpha or beta). Should start \'TR[ABGD]\'.")


def find_species_covered():
    """
    :return: list of data directories for different species available
    """
    species_list = [x for x in os.listdir(data_dir) if os.path.isdir(os.path.normpath(os.path.join(data_dir, x))) and
                    x != 'kazusa' and x != 'GUI-Examples' and '__' not in x]

    if not species_list:
        raise ValueError("No species data detected. Please run stitchrdl first, or otherwise install data in the Data"
                         " directory (" + data_dir + ").")
    species_list.sort()
    return species_list


def infer_species(path_to_file):
    """
    :param path_to_file: str of a path to an input file that may or may not contain
    :return: the species detected, if one found that fits the data available in the data directory
    """
    in_file_name = os.path.basename(path_to_file)
    species_search = [x for x in find_species_covered() if x in in_file_name.upper()]

    if len(species_search) == 1:
        return species_search[0]
    else:
        return ''


def sort_input(cmd_line_args):
    """
    :param cmd_line_args: vars(args())
    :return: tidied/autofilled input arguments, plus the chain information
    """
    tidied_args = tidy_input(cmd_line_args)
    species_dirs = find_species_covered()

    # Check the species is an appropriate one
    if tidied_args['species'] not in species_dirs:
        raise ValueError("Invalid species option given. Current options in Data directory are: "
                         + ', '.join(species_dirs))

    # If additional optional 5'/3' sequences are provided, check they are valid DNA sequences
    for end in ['5', '3']:
        if cmd_line_args[end + '_prime_seq']:
            if not dna_check(cmd_line_args[end + '_prime_seq']):
                raise IOError("Provided " + end + "\' sequence contains non-DNA characters.")

            if len(cmd_line_args[end + '_prime_seq']) % 3 != 0:
                warnings.warn(
                    "Warning: length of " + end + "\' sequence provided is not divisible by 3. "
                                                  "Ensure sequence is padded properly if needed to be in frame.")

    chain = get_chain(tidied_args['v'], tidied_args['j'])
    finished_args = autofill_input(tidied_args, chain)
    return finished_args, chain


def tidy_input(cmd_line_args):
    """
    :param cmd_line_args: vars(args())
    :return: input arguments, with all keys made uppercase (unless it's a path)
    """

    out_args = {}
    for arg in cmd_line_args:

        if isinstance(cmd_line_args[arg], str):
            if 'path' in arg:
                out_args[arg] = cmd_line_args[arg]
            else:
                out_args[arg] = cmd_line_args[arg].upper()
        else:
            out_args[arg] = cmd_line_args[arg]

    if cmd_line_args['name']:
        out_args['name'] = cmd_line_args['name']
    else:
        out_args['name'] = ''

    return out_args


def autofill_input(cmd_line_args, chain):
    """
    :param cmd_line_args: Tidied input arguments
    :param chain: TCR chain, just determined
    :return: Autofilled input arguments (i.e. filling out the leader and constant region genes)
    """

    # Default constant regions for humans and mice
    if not cmd_line_args['c']:
        if cmd_line_args['species'] in ['HUMAN', 'MOUSE']:
            if chain == 'TRA':
                cmd_line_args['c'] = 'TRAC*01'
            elif chain == 'TRB':
                if 'TRBJ1' in cmd_line_args['j']:
                    cmd_line_args['c'] = 'TRBC1*01'
                elif 'TRBJ2' in cmd_line_args['j']:
                    cmd_line_args['c'] = 'TRBC2*01'
            elif chain == 'TRD':
                cmd_line_args['c'] = 'TRDC*01'
            elif chain == 'TRG':
                if cmd_line_args['species'] == 'HUMAN':
                    if 'TRGJ2' in cmd_line_args['j'] or 'TRGJP2' in cmd_line_args['j']:
                        cmd_line_args['c'] = 'TRGC2*02'
                    else:
                        cmd_line_args['c'] = 'TRGC1*01'
                elif cmd_line_args['species'] == 'MOUSE':
                    if 'TRGJ1' in cmd_line_args['j']:
                        cmd_line_args['c'] = 'TRGC1*01'
                    elif 'TRGJ2' in cmd_line_args['j']:
                        cmd_line_args['c'] = 'TRGC2*cmd_line01'
                    elif 'TRGJ3' in cmd_line_args['j']:
                        cmd_line_args['c'] = 'TRGC3*01'
                    elif 'TRGJ4' in cmd_line_args['j']:
                        cmd_line_args['c'] = 'TRGC4*01'

        else:
            raise IOError("Constant region cannot be automatically inferred for non-human/non-mouse TCRs - "
                          "please explicitly specify the relevant constant region.")

    # Leader region (assuming the proximal L for that V is used)
    if not cmd_line_args['l']:
        cmd_line_args['l'] = cmd_line_args['v']

    return cmd_line_args


def get_imgt_data(tcr_chain, gene_types, species):
    """
    :param tcr_chain: 3 digit str code, e.g. TRA or TRB
    :param gene_types: list of TYPES of genes to be expected in a final TCR mRNA, in their IMGT nomenclature
    :param species: upper case str, for use if a specific absolute path not specified
    :return: triply nested dict of TCR data: { region { gene { allele { seq } } }; a doubly nested dict with V/J
      functionalities, and a doubly nested dict of genes filtered out due to being partial in their 5' or 3' (or both)
    """

    # Run some basic sanity/input file checks
    if tcr_chain not in ['TRA', 'TRB', 'TRG', 'TRD', 'IGH', 'IGL', 'IGK']:
        raise ValueError("Incorrect chain detected (" + tcr_chain + "), cannot get IMGT data. ")

    in_file_path = os.path.join(data_dir, species, tcr_chain + '.fasta')
    if not os.path.isfile(in_file_path):
        raise IOError(tcr_chain + '.fasta not detected in the Data directory. '
                                  'Please check data exists for this species/locus combination. ')

    # Read in the data to a nested dict
    tcr_data = {}
    for gene_type in gene_types:
        tcr_data[gene_type] = coll.defaultdict(nest)

    functionality = coll.defaultdict(nest)
    partial_genes = coll.defaultdict(nest)

    with open(in_file_path, 'r') as in_file:
        for fasta_id, seq, blank in read_fa(in_file):
            bits = fasta_id.split('|')
            if len(bits) < 13:
                raise IOError("Input TCR FASTA file does not fit the IMGT header format. ")

            gene, allele = bits[1].split('*')
            functionality_call = bits[3]
            seq_type = fasta_id.split('~')[1]
            partial_flag = bits[13]

            functionality[gene][allele] = functionality_call

            if 'partial' in partial_flag:
                partial_genes[gene][allele] = partial_flag
            else:
                tcr_data[seq_type][gene][allele] = seq.upper()

    for gene_type in gene_types:
        if len(tcr_data[gene_type]) == 0:
            raise Exception("No entries for " + gene_type + " in IMGT data. ")

    return tcr_data, functionality, partial_genes


def strip_functionality(functionality_str):
    """
    :param functionality_str: functionality string as present in an IMGT FASTA header
    :return: the core functionality (F/ORF/P) minus any brackets
    """
    return functionality_str.replace('(', '').replace(')', '').replace('[', '').replace(']', '')


def get_additional_genes(imgt_data, imgt_functionality):
    """
    :param imgt_data: the nested dict produced by get_imgt_data containing V/J/C sequence data
    :param imgt_functionality: the nested dict with imgt_stated functionality
    :return: the same dicts supplemented with any genes found in the 'additional genes.fasta' file
    """

    with open(data_dir + 'additional-genes.fasta', 'r') as in_file:
        for fasta_id, seq, blank in read_fa(in_file):
            bits = fasta_id.split('|')

            if len(bits) < 5:
                raise IOError("Sequence in additional-genes.fasta doesn't have enough fields in header: " + fasta_id)

            if '*' in bits[1]:
                gene, allele = bits[1].upper().split('*')
            else:
                raise IOError("Sequence in additional-genes.fasta doesn't have correct gene name format ('" + bits[1]
                              + "'): " + fasta_id)

            if bits[3]:
                functionality_call = bits[3].replace('(', '').replace(')', '').replace('[', '').replace(']', '')
            else:
                functionality_call = 'F'

            if '~' in fasta_id:
                seq_type = fasta_id.split('~')[1]
                if seq_type not in regions.values():
                    raise IOError("Sequence in additional-genes.fasta doesn't have valid gene type ('" + seq_type + "')"
                                  ": " + fasta_id)
            else:
                raise IOError("Sequence in additional-genes.fasta doesn't have the required '~' character: " + fasta_id)

            imgt_data[seq_type][gene][allele] = seq
            imgt_functionality[gene][allele] = functionality_call

    return imgt_data, imgt_functionality


def get_preferred_alleles(path_to_pa_file, gene_types, imgt_data, partiality, locus):
    """
    :param path_to_pa_file: str path to file of preferred alleles
    :param gene_types: list of TYPES of genes to be expected in a final TCR mRNA, in their IMGT nomenclature
    :param imgt_data: double nested dict of tcr gene sequences, from get_imgt_data()
    :param partiality: double nested dict detailing partial genes, from get_imgt_data()
    :param locus: three character string detailing what locus is being stitched
    :return: a nested dict containing default alleles for the specified genes
    """

    if not os.path.isfile(path_to_pa_file):
        raise IOError("Could not find a preferred allele file at this path: " + path_to_pa_file
                      + ", despite the '-p' flag being used. Please check path. ")

    preferences = {}
    for gene_type in gene_types:
        preferences[gene_type] = coll.defaultdict(nest)

    line_count = 0
    with open(path_to_pa_file, 'r') as in_file:
        for line in in_file:
            bits = line.rstrip().split('\t')
            if line_count == 0:
                header = bits
            else:
                pref_gene, pref_allele, pref_region, pref_locus, pref_source = bits

                base_warning = "Requested preferred allele " + pref_gene + "*" + pref_allele + " cannot be used for " \
                               "the " + pref_region + " region, "

                # Only process those which are labelled as being involved in the locus under consideration
                covered_loci = pref_locus.replace(' ', '').split(',')
                if locus not in covered_loci:
                    # Silently ignore other loci's preferred alleles
                    continue

                # Check that provided preference is valid, present in the data, and not a partial gene
                if pref_region not in regions.values():
                    warnings.warn(base_warning +
                                  "as this is not a valid option. ")
                elif pref_gene not in imgt_data[pref_region]:
                    warnings.warn(base_warning +
                                  "as this gene is not present in the input FASTA data for this species. ")
                elif pref_allele not in imgt_data[pref_region][pref_gene]:
                    warnings.warn(base_warning +
                                  "as this allele is not present in the input FASTA data for this species. ")
                elif pref_allele in partiality[pref_gene][pref_allele]:
                    warnings.warn(base_warning +
                                  "as the sequence for this allele is in the input data is flagged as partial. ")
                else:
                    preferences[pref_region][pref_gene] = pref_allele

            line_count += 1

    return preferences


def tidy_n_term(n_term_nt):
    """
    Tidy up the germline N-terminal half (i.e. pre-CDR3, L+V) of the nt seq so that it's nicely divisible by 3
    :param n_term_nt: done['l'] + done['v']
    :return: n_term_nt trimmed to no hanging fragments
    """

    modulo = len(n_term_nt) % 3
    if modulo == 0:
        trimmed = n_term_nt
    else:
        trimmed = n_term_nt[:-modulo]

    return trimmed, translate_nt(trimmed)


def find_stop(seq):
    """
    :param seq: a translated amino acid sequence
    :return: the position of the first stop codon (*) inside - if none, return length of whole sequence
    """
    if '*' in seq:
        return seq.index('*')
    else:
        return len(seq)


def tidy_c_term(c_term_nt, skip, c_region_motifs, c_gene):
    """
    Tidy up the germline C-terminal half (i.e. post-CDR3, J+C) of the nt seq so that it's the right frame/trimmed
    :param c_term_nt: done['j'] + done['c']
    :param skip: boolean, whether or not to skip the C region checks
    :param c_region_motifs: nested dict of details of motifs required for finding the right translation frame
    :param c_gene: str of actual C gene used
    :return: c_term_nt trimmed/in right frame
    """

    translations = {}  # key = frame (0, 1, or 2)
    best = -1
    position = -1

    # Try every frame, look for the frame that contains the appropriate sequence
    for f in range(4):

        translated = translate_nt(c_term_nt[f:])
        translations[f] = translated

        # If C gene check skips is selected, OR if the constant region isn't listed in the C-region-motifs...
        if skip or c_gene not in c_region_motifs['start']:
            # Try to figure out the best translation frame, by picking the one with the longest pre-stop sequence
            for frame in translations:
                stop = find_stop(translations[frame])
                if stop > position:
                    best = frame
                    position = stop

            if f == 3:
                if best == 2:
                    warnings.warn("Note: expected reading frame " + str(best) + " used for translating C terminus. ")
                else:
                    warnings.warn("Warning: reading frame " + str(best) + " used for translating C terminus, "
                                  "instead of the expected reading frame 2 - "
                                  "double check your input/output sequences are correct. ")

                return c_term_nt[best:], translations[best]

        # ... otherwise if C gene check skips not selected, OR if the constant region is listed in the motifs
        if not skip or c_gene in c_region_motifs['start']:
            # Use the defined constant region motif
            if c_region_motifs['start'][c_gene] in translated:

                # Account for late EX4UTR stop codons
                if c_gene in c_region_motifs['stop']:
                    stop_index_aa = translated.index(c_region_motifs['stop'][c_gene])
                    c_term_nt = c_term_nt[:(stop_index_aa * 3) + f]  # And offset by the frame to prevent trailing nt
                    translated = translate_nt(c_term_nt[f:])

                    if 'UTR' not in c_region_motifs['exons'][c_gene]:
                        warnings.warn("Warning: the constant region '" + c_gene + "' being used contains a stop codon, "
                                      "yet its exon label (" + c_region_motifs['exons'][c_gene] + ") doesn't suggest "
                                      "there should be one - this could indicate incorrect exon annotations, "
                                      "potentially resulting in an out of frame constant region. ")

                break

    return c_term_nt[f:], translated


def determine_v_interface(cdr3aa, n_term_nuc, n_term_amino):
    """
    Determine germline V contribution, and subtract from the the CDR3 (to leave just non-templated residues)
    :param cdr3aa: CDR3 region (protein sequence as provided)
    :param n_term_nuc: DNA encoding the germline N terminal portion (i.e. L1+2 + V gene), with no untranslated bp
    :param n_term_amino: translation of n_term_nuc
    :return: appropriately trimmed n_term_nuc, plus the number of AA residues the CDR3's N term can be trimmed by
    """

    for c in reversed(list(range(1, 5))):
        n_term_cdr3_chunk = cdr3aa[:c]
        for v in range(10):
            aa_l = len(n_term_amino)
            v_match = n_term_amino[aa_l - (c + v):aa_l - v]
            if n_term_cdr3_chunk == v_match:
                n_term_nt_trimmed = n_term_nuc[:(aa_l * 3) - (v * 3)]
                cdr3_n_offset = c
                return n_term_nt_trimmed, cdr3_n_offset

    # Shouldn't be able to throw an error, as the presence of an N terminal cysteine should be established, but in case
    raise Exception("Unable to locate N terminus of CDR3 in V gene correctly. Please ensure sequence plausibility. ")


def find_cdr3_c_term(cdr3_chunk, j_seq, strict):
    """
    Take a C terminal section of a CDR3 and find its germline contribution from the J (using the  pattern)
    :param cdr3_chunk: a portion of the CDR3 junction, having had V germline contributions removed
    :param j_seq: the sequence of the germline J gene in which should lie the cdr3_chunk (or a subsequent substring)
    :param strict: boolean flag determining whether strict (GXG) or non-strict (G..|..G) pattern is used
    :yield: the index of all hits of cdr3_chunk followed by G or XXG in j_seq (i.e. nesting it at the conserved spot)
    """
    i = j_seq.find(cdr3_chunk)
    while i != -1:

        if strict:
            if j_seq[i + len(cdr3_chunk)] == 'G' and j_seq[i + len(cdr3_chunk) + 2] == 'G':
                yield i

        else:
            if j_seq[i + len(cdr3_chunk)] == 'G':
                yield i
            elif j_seq[i + len(cdr3_chunk) + 2] == 'G':
                yield i

        i = j_seq.find(cdr3_chunk, i+1)


def determine_j_interface(cdr3_cterm_aa, c_term_nuc, c_term_amino, gl_nt_j_len, j_warning_threshold):
    """
    Determine germline J contribution, and subtract from the the CDR3 (to leave just non-templated residues)
    Starts with the whole CDR3 (that isn't contributed by V) and looks for successively N-terminal truncated
    regions in the germline J-REGION.
    :param cdr3_cterm_aa: CDR3 region (protein sequence), minus the N-terminal V gene germline contributions
    :param c_term_nuc: DNA encoding the germline C terminal portion (i.e. J + C genes), with no untranslated bp
    :param c_term_amino: translation of c_term_nuc (everything downstream of recognisable end of the V)
    :param gl_nt_j_len: length of germline nucleotide J gene used (to only search for CDR3 C terminal in J)
    :param j_warning_threshold: int threshold value, if a J substring length match is shorter it will throw a warning
    :return: the nt seq of the C-terminal section of the TCR and number of bases into CDR3 that are non-templated
    """

    # Figure out how long into the C terminus we need to look, i.e. as far as the J gene stretches
    search_len = int(gl_nt_j_len / 3)

    # Determine germline J contribution - going for longest possible, starting with whole CDR3
    # 'c' here is effectively the number of CDR3 AA not contributed to from J (and V, from prior steps)
    for c in reversed(list(range(1, len(cdr3_cterm_aa)))):
        c_term_cdr3_chunk = cdr3_cterm_aa[-c:]

        # Look for the decreasing chunks of the CDR3 in the theoretical translation of this J gene as germline
        search = [x for x in find_cdr3_c_term(c_term_cdr3_chunk, c_term_amino[:search_len], False)]

        if search:
            if len(search) == 1:
                cdr3_c_end = search[0]

                c_term_nt_trimmed = c_term_nuc[cdr3_c_end * 3:]

                # Add a warning if the detected J match is too far or too shore
                if cdr3_c_end > 22:
                    warnings.warn("Warning: germline match \'" + c_term_cdr3_chunk + "\' was found " +
                                  str(search.start()) + " residues past the start of the J, "
                                  "which is an extremely unlikely TCR. ")

                if c <= j_warning_threshold:
                    warnings.warn("Note: while a C-terminal CDR3:J germline match has been found, it was only the "
                                  "string \"" + c_term_cdr3_chunk + "\". ")

            # If no single match found using the non-strict conserved J motif pattern (G..|..G), use the strict GXG
            elif len(search) > 1 and len(c_term_cdr3_chunk) == 1:
                warnings.warn("Note: while a C-terminal CDR3:J germline match has been found, it was only the string "
                              "\"" + c_term_cdr3_chunk + "\", which occurs in two positions. ")

                search2 = [x for x in find_cdr3_c_term(c_term_cdr3_chunk, c_term_amino[:search_len], True)]

                if len(search2) == 1:
                    cdr3_c_end = search2[0]
                    c_term_nt_trimmed = c_term_nuc[cdr3_c_end * 3:]

                else:
                    raise ValueError("CDR3 seemingly deleted up to/past conserved CDR3 junction terminating residue, "
                                     "but multiple motif hits found - unable to locate C terminus of CDR3. ")

            return c_term_nt_trimmed, len(cdr3_cterm_aa) - c

    # Shouldn't be able to get here to throw an error, but just in case
    raise ValueError("Unable to locate C terminus of CDR3 in J gene correctly. Please ensure sequence plausibility. ")


def get_codon_frequencies(path_to_freq_file):
    """
    :param path_to_freq_file: Path to file containing Kazusa-formatted codon usage
    :return: nested counter containing the raw codon frequencies
    """

    codon_usage = coll.defaultdict(nest_counter)
    with open(path_to_freq_file) as in_file:
        for line in in_file:
            cleaned = [x for x in re.sub(r'\(.+?\)', '', line.rstrip()).upper().replace('U', 'T').split(' ') if x]
            if len(cleaned) % 2 != 0:
                raise ValueError("Error in codon usage file - unexpected format.")
            if len(cleaned) == 0:
                continue
            for pair in [x for x in range(len(cleaned)) if x % 2 == 0]:
                codon = cleaned[pair]
                val = cleaned[pair + 1]
                codon_usage[translate_nt(codon)][codon] = float(val)

    return codon_usage


def get_optimal_codons(specified_cu_file, species):
    """
    :param specified_cu_file: Path to file containing Kazusa-formatted codon usage (if specified)
    :param species: human or mouse, for use if a specific absolute path not specified
    :return: dict containing 'best' (most frequent) codon to use per residue
    """

    if specified_cu_file:
        path_to_cu_file = specified_cu_file
    else:
        path_to_cu_file = os.path.join(data_dir, 'kazusa', species + '.txt')

    if not os.path.isfile(path_to_cu_file):
        warnings.warn("Could not find a codon frequency file at this path: " + path_to_cu_file
                      + ". Defaulting to the human table file.")
        path_to_cu_file = os.path.join(data_dir, 'kazusa', 'HUMAN.txt')

    codon_usage = get_codon_frequencies(path_to_cu_file)
    if len(codon_usage) < 20:
        warnings.warn("Warning: incomplete codon usage file input - back translation may fail! ")

    out_dict = coll.defaultdict()
    for residue in codon_usage:
        out_dict[residue] = codon_usage[residue].most_common()[0][0]

    return out_dict


def get_j_motifs(species):
    """
    :param species: upper case string of common species name, referring to a directory in DATA/
    :return: dict of J genes which have a non-canonical (non-phenylalanine) CDR3 terminal residue, and a list of
             J genes whose terminal residue is low confidence (i.e. unable to find a clear FGXG-like motif at all)

    NB: Expects a file in the Data/[species]/ directory called 'J-region-motif.tsv'
    That file should contain a header, with the first 3 columns consisting of:
    J gene/Residue/Confident? (with two later fields of Motif/Position(
    """

    j_file = os.path.join(data_dir, species, 'J-region-motifs.tsv')

    residues = coll.defaultdict()
    low_confidence = []

    with open(j_file, 'r') as in_file:

        line_count = 0
        for line in in_file:
            bits = line.rstrip().split('\t')
            if line_count != 0:
                residues[bits[0]] = bits[1]
                if bits[2] != 'Y':
                    low_confidence.append(bits[0])
            line_count += 1

    return residues, low_confidence


def get_c_motifs(species):
    """
    :param species: upper case string of common species name, referring to a directory in DATA/
    :return: dict of J genes which have a non-canonical (non-phenylalanine) CDR3 terminal residue, and a list of
             J genes whose terminal residue is low confidence (i.e. unable to find a clear FGXG-like motif at all)

    NB: Expects a file in the Data/[species]/ directory called 'C-region-motif.tsv'
    That file should contain a header, with columns consisting of: C gene/Exons/Start motif/Stop codon motif
    """

    c_file = os.path.join(data_dir, species, 'C-region-motifs.tsv')

    constant_motifs = {'start': coll.defaultdict(), 'stop': coll.defaultdict(), 'exons': coll.defaultdict()}

    with open(c_file, 'r') as in_file:

        line_count = 0
        for line in in_file:
            bits = line.rstrip().split('\t')
            if line_count != 0:
                # Record exon configuration
                constant_motifs['exons'][bits[0]] = bits[1]
                # Define a 'start' motif (which gives the correct translation of the start of the C, for frame-finding)
                constant_motifs['start'][bits[0]] = bits[2]
                # If provided, also define a 'stop' motif, which gives a chunk of seq to find in-frame stop codons
                if len(bits) > 3:
                    constant_motifs['stop'][bits[0]] = bits[3]
            line_count += 1

    return constant_motifs


def rev_translate(amino_acid_seq, codon_usage_dict):
    """
    :param amino_acid_seq: An amino acid to convert into nucleotide sequence, using the most common codon
    :param codon_usage_dict: Dict of which codons to use for which amino acids (see get_optimal_codons)
    :return: Corresponding nucleotide sequence
    """

    return ''.join([codon_usage_dict[x] for x in amino_acid_seq])


def get_linker_dict():
    """
    :return: Dictionary of linkers contained in the Data/linkers.tsv file
    """

    if not os.path.isfile(linkers_file):
        raise IOError(linkers_file + " not detected - please check linker file is present and run again. ")

    else:
        linkers = coll.defaultdict()
        with open(linkers_file, 'r') as in_file:
            for line in in_file:
                bits = line.rstrip().split('\t')
                linkers[bits[0]] = bits[1]

        return linkers


def get_linker_seq(linker_text, linker_dict):
    """
    :param linker_text: The text from the Linker field of the input tsv file for bulk stitching (name or custom)
    :param linker_dict: Dict of the known provided linker sequences (from Data/linkers.tsv)
    :return: the corresponding linker sequence, or throw a warning if appropriate
    """

    if linker_text in linker_dict:
        return linker_dict[linker_text]

    # Allows users to input their own custom DNA sequences
    elif dna_check(linker_text):
        if len(linker_text) % 3 != 0:
            warnings.warn("Warning: length of linker sequence \'"
                          + linker_text + "\' is not divisible by 3; "
                          "if this was supposed to be a skip sequence the downstream gene will not be in frame. ")

        return linker_text

    else:
        raise ValueError("Error: " + linker_text +
                         " is not a recognised pre-coded linker sequence and does not seem to be DNA. ")


def dna_check(possible_dna):
    """
    :param possible_dna: A sequence that may or may not be a plausible DNA (translatable!) sequence
    :return: True/False
    """

    return set(possible_dna.upper()).issubset({'A', 'C', 'G', 'T', 'N'})


def tweak_thimble_input(stitch_dict):
    """
    :param stitch_dict: Dictionary produced by stitchr
    :return: Fixed stitchr dict (species capitalised, TCR names blanked)
    """

    stitch_dict['name'] = ''
    for region in ['v', 'j', 'cdr3', 'c']:
        stitch_dict[region] = stitch_dict[region].upper()

    return stitch_dict


def opener(in_file):
    """
    :param in_file: path to file to be opened
    :return: the appropriate file opening command (open or gzip.open)
    """
    if in_file.endswith('.gz'):
        return gzip.open(in_file, 'rt')
    else:
        return open(in_file, 'r')


def translate_nt(nt_seq):
    """
    :param nt_seq: Nucleotide sequence to be translated
    :return: corresponding amino acid sequence
    """

    aa_seq = ''
    for i in range(0, len(nt_seq), 3):
        codon = nt_seq[i:i+3].upper()
        if len(codon) == 3:
            try:
                aa_seq += codons[codon]
            except Exception:
                raise IOError("Cannot translate codon: " + codon + ". ")

    return aa_seq


def check_suffix_prefix(five_prime_seq, three_prime_seq):
    """
    :param five_prime_seq: the 5' (or upstream) sequence, in which to look for a suffix
    :param three_prime_seq: the 3' (or downstream) sequence, in which to look for a prefix
    :return: sequence corresponding to the overlap between the five_prime and three_prime seqs
    Based off code from Stack Overflow user 'Mad Physicist' - see https://stackoverflow.com/questions/58598805/
    """

    steps = range(min(len(five_prime_seq), len(three_prime_seq)) - 1, -1, -1)
    return next((three_prime_seq[:n] for n in steps if five_prime_seq[-n:] == three_prime_seq[:n]), '')


def find_v_overlap(v_germline, nt_cdr3):
    """
    :param v_germline: nucleotide sequence of the 5' part of the germline TCR (i.e. L+V)
    :param nt_cdr3: user provided nucleotide sequences covering (and potentially exceeding) the CDR3 junction
    :return: v_germline sequence running up to (but not including) where it overlaps with the nt_cdr3 sequence,
             and the overlapped sequence (to be subtracted from the CDR3 junction nt before checking for J overlap)
    Note that this function allows for a very generous (supra-physiological) upper limit of 50 deletions from the V
    """

    longest_overlap = ''
    index_longest = 0
    # Have to count backwards from the the end of the V; only need to go as far as the provided nt_cdr3 length (although
    # some of that will contain J gene residues)
    # Note that the positive check is against the outside chance someone provides an inconsistently short V gene
    for i in [x for x in range(len(v_germline) - 1, len(v_germline) - len(nt_cdr3), -1) if x > 0]:

        tmp_fp = v_germline[:i]
        overlap = check_suffix_prefix(tmp_fp, nt_cdr3)
        if len(overlap) > len(longest_overlap):
            longest_overlap = overlap
            index_longest = i

    return v_germline[:index_longest - len(longest_overlap)], longest_overlap


def find_j_overlap(nt_cdr3, j_germline):
    """
    :param nt_cdr3: user provided nucleotide sequences covering (and potentially exceeding) the CDR3 junction
    :param j_germline: nucleotide sequence of the 3' part of the germline TCR (i.e. J+C)
    :return: j_germline sequence running from (but not including) where it overlaps with the nt_cdr3 sequence
    """

    longest_overlap = ''
    index_longest = 0
    for i in range(len(j_germline)):
        tmp_j = j_germline[i:]
        overlap = check_suffix_prefix(nt_cdr3, tmp_j)
        if len(overlap) > len(longest_overlap):
            longest_overlap = overlap
            index_longest = i

    return j_germline[index_longest + len(longest_overlap):]


def main():
    print("Please use the appropriate 'stitchr', 'thimble', 'gui_stitchr' or 'stitchrdl' command.")


codons = {'AAA': 'K', 'AAC': 'N', 'AAG': 'K', 'AAT': 'N',
          'ACA': 'T', 'ACC': 'T', 'ACG': 'T', 'ACT': 'T',
          'AGA': 'R', 'AGC': 'S', 'AGG': 'R', 'AGT': 'S',
          'ATA': 'I', 'ATC': 'I', 'ATG': 'M', 'ATT': 'I',
          'CAA': 'Q', 'CAC': 'H', 'CAG': 'Q', 'CAT': 'H',
          'CCA': 'P', 'CCC': 'P', 'CCG': 'P', 'CCT': 'P',
          'CGA': 'R', 'CGC': 'R', 'CGG': 'R', 'CGT': 'R',
          'CTA': 'L', 'CTC': 'L', 'CTG': 'L', 'CTT': 'L',
          'GAA': 'E', 'GAC': 'D', 'GAG': 'E', 'GAT': 'D',
          'GCA': 'A', 'GCC': 'A', 'GCG': 'A', 'GCT': 'A',
          'GGA': 'G', 'GGC': 'G', 'GGG': 'G', 'GGT': 'G',
          'GTA': 'V', 'GTC': 'V', 'GTG': 'V', 'GTT': 'V',
          'TAA': '*', 'TAC': 'Y', 'TAG': '*', 'TAT': 'Y',
          'TCA': 'S', 'TCC': 'S', 'TCG': 'S', 'TCT': 'S',
          'TGA': '*', 'TGC': 'C', 'TGG': 'W', 'TGT': 'C',
          'TTA': 'L', 'TTC': 'F', 'TTG': 'L', 'TTT': 'F',
          # Plus N-padded codons, to account for cases where someone stitched with a len(5' extension) % 3 != 0
          'NNA': '_', 'NNC': '_', 'NNG': '_', 'NNT': '_',
          'NAA': '_', 'NAC': '_', 'NAT': '_', 'NAG': '_',
          'NCA': '_', 'NCC': '_', 'NCT': '_', 'NCG': '_',
          'NTA': '_', 'NTC': '_', 'NTT': '_', 'NTG': '_',
          'NGA': '_', 'NGC': '_', 'NGT': '_', 'NGG': '_'}

regions = {'l': 'LEADER',
           'v': 'VARIABLE',
           'j': 'JOINING',
           'c': 'CONSTANT'
           }

citation = 'James M Heather, Matthew J Spindler, Marta Herrero Alonso, Yifang Ivana Shui, David G Millar, ' \
           'David S Johnson, Mark Cobbold, Aaron N Hata, Stitchr: stitching coding TCR nucleotide sequences from ' \
           'V/J/CDR3 information, Nucleic Acids Research, Volume 50, Issue 12, 8 July 2022, Page e68, ' \
           'https://doi.org/10.1093/nar/gkac190'
