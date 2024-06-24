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

import os
import logging
import click
from extraction_benchmark.globals import *
from extraction_benchmark.util import *


@click.command()
@click.option('-m', '--model', type=click.Choice(['all', *MODELS_ALL]), default=['all'],
              help='Extraction models ("all" does not include ensembles)', multiple=True)
@click.option('--run-ensembles', is_flag=True, help='Run ensembles')
@click.option('-u','--url', help='Run selected models on a single URL (ignores --dataset)', default=None)
@click.option('-f','--filename', help='Read list of urls from selected file (ignores --dataset)', default=None)
@click.option('-p', '--pages', is_flag=True, help='Run selected models on HTML files (ignores --dataset)', default=False)
@click.option('-e', '--exclude-model', type=click.Choice(MODELS_ALL), default=['web2text'], show_default=True,
              help='Exclude models if "all" are selected.', multiple=True)
@click.option('-d', '--dataset', type=click.Choice(['all', *DATASETS]), default=['all'], multiple=True)
@click.option('-x', '--exclude-dataset', type=click.Choice(DATASETS), default=[],
              help='Exclude datasets if "all" are selected.', multiple=True)
@click.option('-s', '--skip-existing', is_flag=True, help='Load existing answer and extract only new')
@click.option('-p', '--parallelism', help='Number of threads to use', default=os.cpu_count())
@click.option('-v', '--verbose', help='Verbose output', is_flag=True)
def extract(model, run_ensembles, url, filename, pages, exclude_model, dataset, exclude_dataset, skip_existing, parallelism, verbose):
    """
    Run main content extractors on the datasets.
    """
    
    chosen_models = []
    if 'all' not in model:
        chosen_models = model

    if run_ensembles:
        if chosen_models:
            model = sorted(m for m in MODELS_ALL if m.startswith('ensemble_majority') and m not in exclude_model)
        else:
            model = sorted(m for m in MODELS_ALL if m.startswith('ensemble_') and m not in exclude_model)
    elif 'all' in model:
        model = sorted(m for m in MODELS if m not in exclude_model)
        click.confirm('This will run ALL models. Continue?', abort=True)

    if not os.path.isdir(MODEL_OUTPUTS_PATH):
        for m in model:
            if m.startswith('ensemble_'):
                raise click.UsageError('Model outputs need to be generated before ensemble can be run.')

    if pages:
        if not os.path.exists(CUSTOM_HTML_RAW_PATH):
            click.echo('HTML file not found.\n'
                       'Make sure that file is in /datasets/custom/html/raw under current working directory', err = True)
        process_html_files(CUSTOM_HTML_RAW_PATH, CUSTOM_HTML_PROCESSED_PATH)

    if url:
        #Extract html page and put in custom folder in combined datasets
        #Then set dataset variable to 'custom'
        if not extract_html_from_urls([url], CUSTOM_HTML_PATH):
            click.echo('Failed to extract url', err = True)

    if filename:
        if not os.path.exists(os.path.join(CUSTOM_PATH,filename)):
            click.echo('File not found.\n'
                       'Make sure that file is in /datasets/custom under current working directory', err = True)
        #Extract all html's and put in custom folder in combined datasets
        #Then set dataset variable to 'custom'
        urls = extract_urls_from_file(os.path.join(CUSTOM_PATH,filename))
        if not extract_html_from_urls(urls, CUSTOM_HTML_PATH):
            click.echo('Failed to extract urls in file', err = True)

    if pages or url or filename:
        dataset = ['custom']
    elif not os.path.isdir(DATASET_COMBINED_PATH):
        raise click.UsageError('Combined dataset not found. '
                               'Please create the converted dataset first using the "convert-datasets" command.')
    
    if 'all' in dataset:
        dataset = sorted(d for d in DATASETS if d not in exclude_dataset)

    if not dataset:
        click.echo('No input datasets found.\n'
                   'Make sure that all datasets have been extracted correctly to a folder "datasets/raw" '
                   'under the current working directory.', err=True)
        return

    if parallelism > 1 and ('web2text' in model or 'boilernet' in model):
        click.echo('WARNING: Deep neural models selected. If you run into GPU memory issues, '
                   'try running with --parallelism=1.', err=True)

    print(dataset)
    from extraction_benchmark import extract
    extract.extract(model, chosen_models, dataset, skip_existing, parallelism, verbose)


@click.command()
@click.option('-d', '--dataset', type=click.Choice(['all', *DATASETS]), default=['all'], multiple=True)
@click.option('-x', '--exclude-dataset', type=click.Choice(DATASETS), default=[], multiple=True)
def convert_datasets(dataset, exclude_dataset):
    """
    Combine raw datasets and convert them to a line-delimieted JSON format.
    """

    if not os.path.isdir(DATASET_RAW_PATH):
        raise click.UsageError('Raw datasets not found. '
                               'Make sure that all datasets have been extracted correctly to a folder "datasets/raw" '
                               'under the current working directory.')

    if 'all' in dataset:
        dataset = sorted(d for d in DATASETS if d not in exclude_dataset)

    from extraction_benchmark import extract
    page_ids = extract.extract_ground_truth(dataset)
    extract.extract_raw_html(dataset, page_ids)


