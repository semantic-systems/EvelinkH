# Copyright (c) Facebook, Inc. and its affiliates.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.
#
import torch
import sys

import numpy as np
from tqdm import tqdm
import blink.biencoder.data_process as data
from blink.common.params import ENT_START_TAG, ENT_END_TAG


def prepare_crossencoder_mentions(
        tokenizer,
        samples,
        max_context_length=256,
        mention_key="mention",
        context_key="context",
        ent_start_token=ENT_START_TAG,
        ent_end_token=ENT_END_TAG,
):
    context_input_list = []  # samples X 128

    for sample in tqdm(samples):
        context_tokens = data.get_context_representation(
            sample,
            tokenizer,
            max_context_length,
            mention_key,
            context_key,
            ent_start_token,
            ent_end_token,
        )
        tokens_ids = context_tokens["ids"]
        context_input_list.append(tokens_ids)

    context_input_list = np.asarray(context_input_list)
    return context_input_list


def prepare_crossencoder_candidates(
        tokenizer, labels, nns, id2title, id2text, id2hyper, id2subevent, id2subsection, id2date, max_cand_length=256,
        topk=200
):
    START_TOKEN = tokenizer.cls_token
    END_TOKEN = tokenizer.sep_token

    candidate_input_list = []  # samples X topk=10 X 128
    label_input_list = []  # samples
    idx = 0
    for label, nn in zip(labels, nns):
        candidates = []

        label_id = -1
        for jdx, candidate_id in enumerate(nn[:topk]):

            if label == candidate_id:
                label_id = jdx
            # print(id2text.keys())
            sub_events = []
            sub_section = []
            year = None

            # if f'{candidate_id}' in id2subevent:
            #     sub_events = id2subevent[f'{candidate_id}']
            # if f'{candidate_id}' in id2subsection:
            #     sub_section = id2subsection[f'{candidate_id}']
            # if f'{candidate_id}' in id2date:
            #     year = id2date[f'{candidate_id}']

            # print(candidate_id, type(candidate_id))
            # print(sub_events, sub_section, year)

            if candidate_id in id2hyper:
                rep = data.get_candidate_representation(
                    id2text[candidate_id],
                    tokenizer,
                    max_cand_length,
                    sub_events,
                    sub_section,
                    year,
                    id2title[candidate_id],
                    hyperlinks=id2hyper[candidate_id]
                )
            else:
                rep = data.get_candidate_representation(
                    id2text[candidate_id],
                    tokenizer,
                    max_cand_length,
                    sub_events,
                    sub_section,
                    year,
                    id2title[candidate_id],
                    hyperlinks=None
                )
            tokens_ids = rep["ids"]
            assert len(tokens_ids) == max_cand_length
            candidates.append(tokens_ids)

        label_input_list.append(label_id)
        candidate_input_list.append(candidates)

        idx += 1
        # print(f"{idx}/{len(labels)}")
        sys.stdout.write("{}/{} \r".format(idx, len(labels)))
        sys.stdout.flush()

    label_input_list = np.asarray(label_input_list)
    candidate_input_list = np.asarray(candidate_input_list)

    return label_input_list, candidate_input_list


def filter_crossencoder_tensor_input(
        context_input_list, label_input_list, candidate_input_list
):
    # remove the - 1 : examples for which gold is not among the candidates
    context_input_list_filtered = [
        x
        for x, y, z in zip(context_input_list, candidate_input_list, label_input_list)
        if z != -1
    ]
    label_input_list_filtered = [
        z
        for x, y, z in zip(context_input_list, candidate_input_list, label_input_list)
        if z != -1
    ]
    candidate_input_list_filtered = [
        y
        for x, y, z in zip(context_input_list, candidate_input_list, label_input_list)
        if z != -1
    ]
    return (
        context_input_list_filtered,
        label_input_list_filtered,
        candidate_input_list_filtered,
    )


def prepare_crossencoder_data(
        tokenizer, samples, labels, nns, id2title, id2text, id2hyper, id2subevent, id2subsection, id2date,
        keep_all=False, args=None
):
    # encode mentions
    context_input_list = prepare_crossencoder_mentions(tokenizer, samples,
                                                       max_context_length=args["max_context_length"])

    # encode candidates (output of biencoder)
    label_input_list, candidate_input_list = prepare_crossencoder_candidates(
        tokenizer, labels, nns, id2title, id2text, id2hyper, id2subevent, id2subsection, id2date,
        max_cand_length=args["max_cand_length"]
    )

    if not keep_all:
        # remove examples where the gold entity is not among the candidates
        (
            context_input_list,
            label_input_list,
            candidate_input_list,
        ) = filter_crossencoder_tensor_input(
            context_input_list, label_input_list, candidate_input_list
        )
    else:
        label_input_list = [0] * len(label_input_list)
    context_input = torch.LongTensor(context_input_list)
    label_input = torch.LongTensor(label_input_list)
    candidate_input = torch.LongTensor(candidate_input_list)

    return (
        context_input,
        candidate_input,
        label_input,
    )
