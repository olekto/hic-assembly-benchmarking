import logging
from dataclasses import dataclass
import numpy as np
import bionumpy as bnp
from npstructures import HashTable, HashSet, Counter, RaggedArray
from bionumpy.kmers import fast_hash

@dataclass
class GfaKmerIndex:
    index: HashTable
    unique_kmers: HashSet

    @classmethod
    def from_gfa(cls, gfa_file_name, k=31):
        data = bnp.open(gfa_file_name).read_chunks(chunk_size=10000000)
        # first find all unique kmers
        kmers = np.concatenate(
            [fast_hash(bnp.as_encoded_array(chunk.sequence, encoding=bnp.DNAEncoding), k).ravel() for chunk in data]
        )
        logging.info("Counting kmers")
        unique_kmers = np.unique(kmers)
        logging.info("%d unique kmers" % len(unique_kmers))
        kmer_counter = Counter(unique_kmers)
        kmer_counter.count(kmers)

        kmers_with_frequency_1 = unique_kmers[kmer_counter[unique_kmers] == 1]
        logging.info("%d kmers have frequency 1" % len(kmers_with_frequency_1))

        # make a lookup from kmer to node segment
        kmer_index = HashTable(kmers_with_frequency_1, 0)
        data = bnp.open(gfa_file_name).read_chunks(chunk_size=10000000)
        sequence_id = 0
        for chunk in data:
            kmers = fast_hash(bnp.as_encoded_array(chunk.sequence, encoding=bnp.DNAEncoding), k)
            for sequence_kmers in kmers:
                print("Sequence %d has %d kmers and %d kmers with frequency 1" % (sequence_id, len(sequence_kmers), len(np.where(kmer_counter[sequence_kmers]==1)[0])))
                kmer_index[sequence_kmers[np.where(kmer_counter[sequence_kmers] == 1)[0]]] = sequence_id
                sequence_id += 1

        logging.info("Made hashmap from unique kmers to sequence ids")
        return cls(kmer_index, HashSet(kmers_with_frequency_1))

    def get(self, kmers):
        is_in_index = self.unique_kmers.contains(kmers)
        return self.index[kmers[is_in_index]]

    def get_as_ragged_array(self, ragged_kmers):
        kmers = ragged_kmers.ravel()
        is_in_index = self.unique_kmers.contains(kmers)
        is_in_index_as_ragged = RaggedArray(is_in_index, ragged_kmers.shape)
        result = self.index[kmers[is_in_index]]
        # get results as a ragged array (only the kmers that are in the index)
        row_lengths = np.sum(is_in_index_as_ragged, axis=-1)
        return RaggedArray(result, row_lengths)

    def get_most_common(self, ragged_kmers):
        hits = self.get_as_ragged_array(ragged_kmers)
        unique, counts = np.unique(hits, axis=-1, return_counts=True)
        return unique[np.arange(len(unique)), np.argmax(counts, axis=-1)]
