# Copyright 2022 by Michiel de Hoon.  All rights reserved.
#
# This file is part of the Biopython distribution and governed by your
# choice of the "Biopython License Agreement" or the "BSD 3-Clause License".
# Please see the LICENSE file that should have been included as part of this
# package.
"""Bio.Align support for Exonerate output format.

This module provides support for Exonerate outputs. Exonerate is a generic
tool for pairwise sequence comparison that allows you to align sequences using
several different models.

Bio.Align.exonerate was tested on the following Exonerate versions and models:

    - version: 2.2
    - models:
      - affine:local                - cdna2genome
      - coding2coding               - est2genome
      - genome2genome               - ner
      - protein2dna                 - protein2genome
      - ungapped                    - ungapped:translated

Although model testing were not exhaustive, the parser should be able to cope
with all Exonerate models. Please file a bug report if you stumble upon an
unparsable file.

You are expected to use this module via the Bio.Align functions.
"""
import numpy


from Bio.Align import Alignment
from Bio.Align import interfaces
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio import BiopythonExperimentalWarning

import warnings

warnings.warn(
    "Bio.Align.exonerate is an experimental module which may undergo "
    "significant changes prior to its future official release.",
    BiopythonExperimentalWarning,
)


class AlignmentWriter(interfaces.AlignmentWriter):
    """Alignment file writer for the Exonerate cigar and vulgar file format."""

    def __init__(self, target, fmt="vulgar"):
        """Create an AlignmentWriter object.

        Arguments:
         - target    - output stream or file name
         - fmt       - write alignments in the vulgar (Verbose Useful Labelled
                       Gapped Alignment Report) format (fmt="vulgar") or in
                       the cigar (Compact Idiosyncratic Gapped Alignment Report)
                       format (fmt="cigar").
                       Default value is 'vulgar'.

        """
        super().__init__(target, mode="w")
        if fmt == "vulgar":
            self.format_alignment = self._format_alignment_vulgar
        elif fmt == "cigar":
            self.format_alignment = self._format_alignment_cigar
        else:
            raise ValueError(
                "argument fmt should be 'vulgar' or 'cigar' (received %s)" % fmt
            )

    def write_header(self, alignments):
        """Write the header."""
        try:
            commandline = alignments.commandline
        except AttributeError:
            commandline = ""
        try:
            hostname = alignments.hostname
        except AttributeError:
            hostname = ""
        self.stream.write(f"Command line: [{commandline}]\n")
        self.stream.write(f"Hostname: [{hostname}]\n")

    def write_footer(self):
        """Write the footer."""
        self.stream.write("-- completed exonerate analysis\n")

    def _format_alignment_cigar(self, alignment):
        """Return a string with a single alignment formatted as a cigar line."""
        if not isinstance(alignment, Alignment):
            raise TypeError("Expected an Alignment object")
        coordinates = alignment.coordinates
        target_start = coordinates[0, 0]
        target_end = coordinates[0, -1]
        query_start = coordinates[1, 0]
        query_end = coordinates[1, -1]
        steps = coordinates[:, 1:] - coordinates[:, :-1]
        query = alignment.query
        target = alignment.target
        try:
            query_id = query.id
        except AttributeError:
            query_id = "query"
        try:
            target_id = target.id
        except AttributeError:
            target_id = "target"
        try:
            target_molecule_type = target.annotations["molecule_type"]
        except (AttributeError, KeyError):
            target_molecule_type = None
        if target_molecule_type == "protein":
            target_strand = "."
        elif target_start <= target_end:
            target_strand = "+"
        elif target_start > target_end:
            target_strand = "-"
            steps[0, :] = -steps[0, :]
        try:
            query_molecule_type = query.annotations["molecule_type"]
        except (AttributeError, KeyError):
            query_molecule_type = None
        if query_molecule_type == "protein":
            query_strand = "."
        elif query_start <= query_end:
            query_strand = "+"
        elif query_start > query_end:
            query_strand = "-"
            steps[1, :] = -steps[1, :]
        score = alignment.score
        words = [
            "cigar:",
            query_id,
            str(query_start),
            str(query_end),
            query_strand,
            target_id,
            str(target_start),
            str(target_end),
            target_strand,
            str(score),
        ]
        try:
            operations = alignment.operations
        except AttributeError:
            for step in steps.transpose():
                target_step, query_step = step
                if target_step == query_step:
                    operation = "M"
                    step = target_step
                elif query_step == 0:
                    operation = "D"  # Deletion
                    step = target_step
                elif target_step == 0:
                    operation = "I"  # Insertion
                    step = query_step
                elif (
                    target_molecule_type != "protein"
                    and query_molecule_type == "protein"
                ):
                    operation = "M"
                    step = target_step
                elif (
                    target_molecule_type == "protein"
                    and query_molecule_type != "protein"
                ):
                    operation = "M"
                    step = query_step
                else:
                    raise ValueError(
                        "Unexpected step target %d, query %d for molecule type %s, %s"
                        % (
                            target_step,
                            query_step,
                            target_molecule_type,
                            query_molecule_type,
                        )
                    )
                words.append(operation)
                words.append(str(step))
        else:
            for step, operation in zip(steps.transpose(), operations.decode()):
                target_step, query_step = step
                if operation == "M":
                    if target_step == query_step:
                        step = target_step
                    elif target_step == 3 * query_step:
                        step = target_step
                        assert query_molecule_type == "protein"
                        assert target_molecule_type != "protein"
                    elif query_step == 3 * target_step:
                        step = query_step
                        assert query_molecule_type != "protein"
                        assert target_molecule_type == "protein"
                    else:
                        raise ValueError(
                            "Unexpected steps target %d, query %s for operation 'M'"
                        )
                elif operation == "5":  # 5' splice site
                    if query_step == 0:
                        step = target_step
                        operation = "D"
                    elif target_step == 0:
                        step = query_step
                        operation = "I"
                    else:
                        assert query_step == target_step
                        step = target_step
                        operation = "M"
                elif operation == "N":  # Intron
                    if query_step == 0:
                        step = target_step
                        operation = "D"
                    elif target_step == 0:
                        step = query_step
                        operation = "I"
                    else:
                        raise ValueError(
                            "Unexpected intron with steps target %d, query %d"
                            % (target_step, query_step)
                        )
                elif operation == "3":  # 3' splice site
                    if query_step == 0:
                        step = target_step
                        operation = "D"
                    elif target_step == 0:
                        step = query_step
                        operation = "I"
                    else:
                        assert query_step == target_step
                        step = target_step
                        operation = "M"
                elif operation == "C":  # Codon
                    assert target_step == query_step
                    step = target_step
                    operation = "M"
                elif operation == "D":  # Deletion
                    assert query_step == 0
                    step = target_step
                    operation = "D"
                elif operation == "I":  # Insertion
                    assert target_step == 0
                    step = query_step
                elif operation == "U":  # Non-equivalenced (unaligned) region
                    if target_step > 0:
                        operation = "D"
                        words.append(operation)
                        words.append(str(target_step))
                    if query_step > 0:
                        operation = "I"
                        words.append(operation)
                        words.append(str(query_step))
                    continue
                elif operation == "S":  # Split codon
                    if target_step > 0:
                        operation = "D"
                        words.append(operation)
                        words.append(str(target_step))
                    if query_step > 0:
                        operation = "I"
                        words.append(operation)
                        words.append(str(query_step))
                    continue
                elif operation == "F":  # Frame shift
                    if target_step == 0:
                        step = query_step
                        operation = "I"
                    elif query_step == 0:
                        step = target_step
                        operation = "D"
                    else:
                        raise ValueError("Expected target step or query step to be 0")
                else:
                    raise ValueError("Unknown operation %s" % operation)
                words.append(operation)
                words.append(str(step))
        line = " ".join(words) + "\n"
        return line

    def _format_alignment_vulgar(self, alignment):
        """Return a string with a single alignment formatted as one vulgar line."""
        if not isinstance(alignment, Alignment):
            raise TypeError("Expected an Alignment object")
        coordinates = alignment.coordinates
        target_start = coordinates[0, 0]
        target_end = coordinates[0, -1]
        query_start = coordinates[1, 0]
        query_end = coordinates[1, -1]
        steps = coordinates[:, 1:] - coordinates[:, :-1]
        query = alignment.query
        target = alignment.target
        try:
            query_id = query.id
        except AttributeError:
            query_id = "query"
        try:
            target_id = target.id
        except AttributeError:
            target_id = "target"
        try:
            target_molecule_type = target.annotations["molecule_type"]
        except (AttributeError, KeyError):
            target_molecule_type = None
        if target_molecule_type == "protein":
            target_strand = "."
        elif target_start <= target_end:
            target_strand = "+"
        elif target_start > target_end:
            target_strand = "-"
            steps[0, :] = -steps[0, :]
        try:
            query_molecule_type = query.annotations["molecule_type"]
        except (AttributeError, KeyError):
            query_molecule_type = None
        if query_molecule_type == "protein":
            query_strand = "."
        elif query_start <= query_end:
            query_strand = "+"
        elif query_start > query_end:
            query_strand = "-"
            steps[1, :] = -steps[1, :]
        score = alignment.score
        words = [
            "vulgar:",
            query_id,
            str(query_start),
            str(query_end),
            query_strand,
            target_id,
            str(target_start),
            str(target_end),
            target_strand,
            str(score),
        ]
        try:
            operations = alignment.operations
        except AttributeError:
            for step in steps.transpose():
                target_step, query_step = step
                if target_step == query_step:
                    operation = "M"
                elif query_step == 0:
                    operation = "G"  # Gap; exonerate definition
                elif target_step == 0:
                    operation = "G"  # Gap; exonerate definition
                elif (
                    query_molecule_type == "protein"
                    and target_molecule_type != "protein"
                ):
                    operation = "M"
                elif (
                    query_molecule_type != "protein"
                    and target_molecule_type == "protein"
                ):
                    operation = "M"
                else:
                    raise ValueError("Both target and query step are zero")
                words.append(operation)
                words.append(str(query_step))
                words.append(str(target_step))
        else:
            steps = steps.transpose()
            operations = operations.decode()
            n = len(operations)
            i = 0
            while i < n:
                target_step, query_step = steps[i]
                operation = operations[i]
                if operation == "M":
                    if target_step == query_step:
                        pass
                    elif target_step == 3 * query_step:
                        assert query_molecule_type == "protein"
                        assert target_molecule_type != "protein"
                    elif query_step == 3 * target_step:
                        assert query_molecule_type != "protein"
                        assert target_molecule_type == "protein"
                    else:
                        raise ValueError(
                            "Unexpected steps target %d, query %s for operation 'M'"
                        )
                elif operation == "5":  # 5' splice site
                    assert target_step == 2 or query_step == 2
                elif operation == "N":  # Intron
                    operation = "I"  # Intron; exonerate definition
                    assert query_step == 0 or target_step == 0
                elif operation == "3":  # 3' splice site
                    assert target_step == 2 or query_step == 2
                elif operation == "C":  # Codon
                    assert target_step == query_step
                elif operation == "D":  # Deletion
                    assert query_step == 0
                    operation = "G"  # Gap; exonerate definition
                elif operation == "I":  # Insertion
                    assert target_step == 0
                    operation = "G"  # Gap; exonerate definition
                elif operation == "U":  # Non-equivalenced (unaligned) region
                    if target_step == 0:
                        assert query_step > 0
                        i += 1
                        target_step, dummy = steps[i]
                        assert dummy == 0
                    if query_step == 0:
                        assert target_step > 0
                        i += 1
                        dummy, query_step = steps[i]
                        assert dummy == 0
                    operation = operations[i]
                    assert operation == "U"
                    operation = "N"  # Non-equivalenced region; exonerate definition
                elif operation == "S":  # Split codon
                    step = target_step
                elif operation == "F":  # Frame shift
                    step = target_step
                else:
                    raise ValueError("Unknown operation %s" % operation)
                words.append(operation)
                words.append(str(query_step))
                words.append(str(target_step))
                i += 1
        line = " ".join(words) + "\n"
        return line


class AlignmentIterator(interfaces.AlignmentIterator):
    """Alignment iterator for the Exonerate text, cigar, and vulgar formats.

    Each line in the file contains one pairwise alignment, which are loaded
    and returned incrementally.  Alignment score information such as the number
    of matches and mismatches are stored as attributes of each alignment.
    """

    def __init__(self, source):
        """Create an AlignmentIterator object.

        Arguments:
         - source   - input data or file name

        """
        super().__init__(source, mode="t", fmt="Exonerate")
        stream = self.stream
        self.program = "exonerate"
        line = next(stream)
        prefix = "Command line: "
        assert line.startswith(prefix)
        commandline = line[len(prefix) :].strip()
        assert commandline.startswith("[")
        assert commandline.endswith("]")
        self.commandline = commandline[1:-1]
        line = next(stream)
        prefix = "Hostname: "
        assert line.startswith(prefix)
        hostname = line[len(prefix) :].strip()
        assert hostname.startswith("[")
        assert hostname.endswith("]")
        self.hostname = hostname[1:-1]

    @staticmethod
    def _parse_cigar(words):
        query_id = words[0]
        query_start = int(words[1])
        query_end = int(words[2])
        query_strand = words[3]
        target_id = words[4]
        target_start = int(words[5])
        target_end = int(words[6])
        target_strand = words[7]
        score = int(words[8])
        target_seq = Seq(None, length=target_end)
        query_seq = Seq(None, length=query_end)
        target = SeqRecord(target_seq, id=target_id)
        query = SeqRecord(query_seq, id=query_id)
        qs = 0
        ts = 0
        n = (len(words) - 8) // 2
        coordinates = numpy.empty((2, n + 1), int)
        coordinates[0, 0] = ts
        coordinates[1, 0] = qs
        for i, (operation, step) in enumerate(zip(words[9::2], words[10::2])):
            step = int(step)
            if operation == "M":  # match or mismatch
                ts += step
                qs += step
            elif operation == "I":  # insertion
                if query_strand == "." and target_strand != ".":
                    qs += step * 3
                else:
                    qs += step
            elif operation == "D":  # deletion
                if target_strand == "." and query_strand != ".":
                    ts += step * 3
                else:
                    ts += step
            else:
                raise ValueError("Unknown operation %s in cigar string" % operation)
            coordinates[0, i + 1] = ts
            coordinates[1, i + 1] = qs
        if target_strand == "+":
            coordinates[0, :] += target_start
        elif target_strand == "-":
            coordinates[0, :] = target_start - coordinates[0, :]
        elif target_strand == ".":  # protein
            if query_strand != ".":
                # dna to protein alignment; integer division, but round up:
                coordinates[0, :] = (coordinates[0, :] + 2) // 3
            coordinates[0, :] += target_start
            target.annotations["molecule_type"] = "protein"
        if query_strand == "+":
            coordinates[1, :] += query_start
        elif query_strand == "-":
            coordinates[1, :] = query_start - coordinates[1, :]
        elif query_strand == ".":  # protein
            if target_strand != ".":
                # protein to dna alignment; integer division, but round up:
                coordinates[1, :] = (coordinates[1, :] + 2) // 3
            coordinates[1, :] += query_start
            query.annotations["molecule_type"] = "protein"
        alignment = Alignment([target, query], coordinates)
        alignment.score = score
        return alignment

    @staticmethod
    def _parse_vulgar(words):
        query_id = words[0]
        query_start = int(words[1])
        query_end = int(words[2])
        query_strand = words[3]
        target_id = words[4]
        target_start = int(words[5])
        target_end = int(words[6])
        target_strand = words[7]
        score = int(words[8])
        target_seq = Seq(None, length=target_end)
        query_seq = Seq(None, length=query_end)
        target = SeqRecord(target_seq, id=target_id)
        query = SeqRecord(query_seq, id=query_id)
        ops = words[9::3]
        qs = 0
        ts = 0
        n = (len(words) - 8) // 3 + ops.count("N")
        coordinates = numpy.empty((2, n + 1), int)
        coordinates[0, 0] = ts
        coordinates[1, 0] = qs
        operations = bytearray(n)
        i = 0
        for (operation, query_step, target_step) in zip(
            ops, words[10::3], words[11::3]
        ):
            query_step = int(query_step)
            target_step = int(target_step)
            if operation == "M":  # Match
                pass
            elif operation == "5":  # 5' splice site
                assert target_step == 2 or query_step == 2
            elif operation == "I":  # Intron
                # use SAM/BAM definitions of operations:
                operation = "N"
            elif operation == "3":  # 3' splice site
                assert target_step == 2 or query_step == 2
            elif operation == "C":  # Codon
                assert target_step % 3 == 0
                assert query_step % 3 == 0
            elif operation == "G":  # Gap
                # use SAM/BAM definitions of operations:
                if query_step == 0:
                    operation = "D"  # Deletion
                elif target_step == 0:
                    operation = "I"  # Insertion
                else:
                    raise ValueError(
                        "Unexpected gap operation with steps %d, %d in vulgar line"
                        % (query_step, target_step)
                    )
            elif operation == "N":  # Non-equivalenced (unaligned) region
                operation = "U"  # 'N' is alread used for introns in SAM/BAM
                if target_step > 0:
                    ts += target_step
                    coordinates[0, i + 1] = ts
                    coordinates[1, i + 1] = qs
                    operations[i] = ord(operation)
                    i += 1
                if query_step > 0:
                    qs += query_step
                    coordinates[0, i + 1] = ts
                    coordinates[1, i + 1] = qs
                    operations[i] = ord(operation)
                    i += 1
                continue
            elif operation == "S":  # Split codon
                pass
            elif operation == "F":  # Frame shift
                pass
            else:
                raise ValueError("Unknown operation %s in vulgar string" % operation)
            ts += target_step
            qs += query_step
            coordinates[0, i + 1] = ts
            coordinates[1, i + 1] = qs
            operations[i] = ord(operation)
            i += 1
        if target_strand == "+":
            coordinates[0, :] += target_start
        elif target_strand == "-":
            coordinates[0, :] = target_start - coordinates[0, :]
        elif target_strand == ".":  # protein
            coordinates[0, :] += target_start
            target.annotations["molecule_type"] = "protein"
        if query_strand == "+":
            coordinates[1, :] += query_start
        elif query_strand == "-":
            coordinates[1, :] = query_start - coordinates[1, :]
        elif query_strand == ".":  # protein
            coordinates[1, :] += query_start
            query.annotations["molecule_type"] = "protein"
        alignment = Alignment([target, query], coordinates)
        alignment.operations = operations
        alignment.score = score
        return alignment

    def parse(self, stream):
        """Parse the next alignment from the stream."""
        if stream is None:
            raise StopIteration

        for line in stream:
            line = line.strip()
            if line == "-- completed exonerate analysis":
                try:
                    next(stream)
                except StopIteration:
                    return
                raise ValueError(
                    "Found additional data after 'completed exonerate analysis'; corrupt file?"
                )
            elif line.startswith("vulgar: "):
                words = line[8:].split()
                alignment = self._parse_vulgar(words)
                yield alignment
            elif line.startswith("cigar: "):
                words = line[7:].split()
                alignment = self._parse_cigar(words)
                yield alignment
        raise ValueError(
            "Failed to find 'completed exonerate analysis'; truncated file?"
        )
