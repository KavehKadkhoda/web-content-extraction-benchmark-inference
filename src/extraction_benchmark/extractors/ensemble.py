# Copyright 2023 Janek Bevendorff
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from collections import defaultdict
import json
import os
import pickle
import re

import click
from resiliparse.extract.html2text import extract_plain_text
from resiliparse.parse.html import HTMLTree

DATASET_ROOT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'dataset')
MODEL_ANSWER_PATH = os.path.join(DATASET_ROOT_PATH, 'json_format', 'model_extracted_output')
GROUND_TRUTH_PATH = os.path.join(DATASET_ROOT_PATH, 'json_format', 'groundtruth')
TRAINED_MODEL_PATH = os.path.join(DATASET_ROOT_PATH, 'ensemble_models')


_MODEL_ANSWERS = defaultdict(dict)
_GROUND_TRUTH = {}
_ENSEMBLE_MODELS = {}

TOKEN_RE = re.compile(r'\s+', flags=re.UNICODE | re.MULTILINE)
WS_RE = TOKEN_RE


def normalize_text(text):
    return ' '.join(TOKEN_RE.split(text.strip()))


def _load_model_answers(input_models):
    for m in input_models:
        if m in _MODEL_ANSWERS:
            continue
        for ds in os.listdir(MODEL_ANSWER_PATH):
            in_file = os.path.join(MODEL_ANSWER_PATH, ds, m, m + '.json')
            if not os.path.isfile(in_file):
                continue
            answers = json.load(open(in_file, 'r'))
            for k in answers:
                _MODEL_ANSWERS[m][k] = normalize_text(answers[k]['articleBody'] or '')


def _load_ground_truth():
    if _GROUND_TRUTH:
        return

    for ds in os.listdir(GROUND_TRUTH_PATH):
        in_file = os.path.join(GROUND_TRUTH_PATH, ds, ds + '.json')
        if not os.path.isfile(in_file):
            continue
        truth = json.load(open(in_file, 'r'))
        for k in truth:
            _GROUND_TRUTH[k] = normalize_text(truth[k]['articleBody'] or '')


def _load_ensemble_model(model_name):
    if model_name in _ENSEMBLE_MODELS:
        return

    path = os.path.join(TRAINED_MODEL_PATH, f'ensemble_{model_name}.pkl')
    if not os.path.isfile(path):
        raise click.UsageError(f'Ensemble model "{model_name}" not yet trained.')
    with open(path, 'rb') as f:
        _ENSEMBLE_MODELS[model_name] = pickle.load(f)


def pad_str_zero(s, n):
    return ('\0 ' * n) + s + (' \0' * n)


def pad_str_space(s):
    return ' ' + s + ' '


def extract_majority_vote(html, page_id, input_models, model_weights, vote_threshold, ngram_size=5):
    _load_model_answers(input_models)

    tree = HTMLTree.parse(html)
    text = pad_str_zero(extract_plain_text(
        tree, main_content=False, preserve_formatting=False, list_bullets=False,
        links=False, alt_texts=False, noscript=False, form_fields=False), ngram_size - 1)
    tokens = TOKEN_RE.split(text.strip())
    token_votes = [0] * len(tokens)

    for ti in range(ngram_size - 1, len(tokens) - ngram_size + 1):
        ngram_str_l = pad_str_space(' '.join(tokens[ti - ngram_size + 1:ti + 1]))
        ngram_str_r = pad_str_space(' '.join(tokens[ti:ti + ngram_size]))

        for m, w in zip(input_models, model_weights):
            answer = pad_str_zero(_MODEL_ANSWERS[m].get(page_id, ''), ngram_size)
            if ngram_str_l in answer or ngram_str_r in answer:
                token_votes[ti] += 1 * w
            if token_votes[ti] >= vote_threshold:
                break

    # Strip padding (matters only if vote_threshold == 0, but still...)
    tokens = tokens[ngram_size - 1:len(tokens) - ngram_size + 1]
    token_votes = token_votes[ngram_size - 1:len(token_votes) - ngram_size + 1]

    return ' '.join(t for t, v in zip(tokens, token_votes) if v >= vote_threshold)
