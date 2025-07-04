import os
from tqdm import tqdm
import numpy as np
import tiktoken
from datasets import load_dataset
import pandas as pd

num_proc = 8
num_proc_load_dataset = num_proc
enc = tiktoken.get_encoding("gpt2")

if __name__ == '__main__':
    dataset = load_dataset("millawell/wikipedia_field_of_science", num_proc=num_proc_load_dataset)

    def filter_psychology(example):
        return example['category'] == 'Psychology'
    psych_dataset = dataset['train'].filter(filter_psychology)

    split_dataset = psych_dataset.train_test_split(test_size=0.003, seed=1234, shuffle=True)
    split_dataset['val'] = split_dataset.pop('test')

    def process(example):
        ids = enc.encode_ordinary(example['text'])
        ids.append(enc.eot_token)
        out = {'ids': ids, 'len': len(ids)}
        return out

    tokenized = split_dataset.map(
        process,
        remove_columns=['text'],
        desc="tokenizing the splits",
        num_proc=num_proc,
    )

    for split, dset in tokenized.items():
        arr_len = np.sum(dset['len'], dtype=np.uint64)
        filename = os.path.join(os.path.dirname(__file__), f'{split}.bin')
        dtype = np.uint16
        arr = np.memmap(filename, dtype=dtype, mode='w+', shape=(arr_len,))
        total_batches = min(1024, len(dset))

        idx = 0
        for batch_idx in tqdm(range(total_batches), desc=f'writing {filename}'):
            batch = dset.shard(num_shards=total_batches, index=batch_idx, contiguous=True).with_format('numpy')
            arr_batch = np.concatenate(batch['ids'])
            arr[idx : idx + len(arr_batch)] = arr_batch
            idx += len(arr_batch)
        arr.flush()
