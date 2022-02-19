"""Check that ICD codes found in mondo-edit.obo are valid ICD codes.
# Advice
- Kevin (Monarch slack): recommended g.load() instead of g.parse()

# Resources
- Pronto: loads ontologies
  - https://pypi.org/project/pronto/
  - https://pronto.readthedocs.io/en/stable/

# Code Snippets
- RDFLib walking
for subj, pred, obj in g:
    print(subj, pred, obj)
"""
import os
import pickle
import subprocess
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import List

# from ontobio import OntologyFactory
from rdflib import Graph
from rdflib.query import Result
from rdflib.plugins.sparql import prepareQuery


# VARS
# # CONSTANTS
PROJECT_DIR = os.path.join(os.path.dirname(__file__), '..')
DATA_DIR = os.path.join(PROJECT_DIR, 'data')
CACHE_DIR = os.path.join(PROJECT_DIR, 'cache')
SPARQL_DIR = os.path.join(PROJECT_DIR, 'sparql')
OUTPUT_DIR = os.path.join(PROJECT_DIR, 'output')
ICD10CM_PATH = os.path.join(DATA_DIR, 'icd10cm', 'bioportal', 'icd10cm.ttl')
MONDO_PATH = os.path.join(DATA_DIR, 'mondo', 'source', 'mondo.json')
# # CONFIG
USE_CACHE = True
PATH_MAP = {
    'mondo': MONDO_PATH,
    'icd10cm': ICD10CM_PATH
}


# Funcs
def _save_csv(df: pd.DataFrame, filename: str):
    """Saves dataframe as CSV using filename."""
    python_filename = os.path.basename(os.path.realpath(__file__)).replace('.py', '')
    output_dir2 = os.path.join(OUTPUT_DIR, python_filename)
    if not os.path.exists(output_dir2):
        os.mkdir(output_dir2)
    date_label = datetime.now().strftime('%Y-%m-%d')
    output_dir3 = os.path.join(output_dir2, date_label)
    if not os.path.exists(output_dir3):
        os.mkdir(output_dir3)
    save_path = os.path.join(output_dir3, filename)
    df.to_csv(save_path, index=False)


def load_onto(onto_name, use_cache=USE_CACHE) -> Graph:
    """Loads ontology"""
    onto_path = PATH_MAP[onto_name]
    pickle_file = Path(CACHE_DIR, os.path.basename(onto_path).replace('.', '-') + '.pickle')
    if pickle_file.is_file() and use_cache:
        return pickle.load(open(pickle_file, 'rb'))

    # Option A: RDF lib
    g = Graph()
    g.parse(ICD10CM_PATH)

    # Option B: Pronto
    # https://pypi.org/project/pronto/

    # Option C: Ontobio
    # ont_factory = OntologyFactory
    # with open(MONDO_PATH, 'r') as f:
    #     mondo_ont = ont_factory.create(str(f))

    with open(pickle_file, 'wb') as handle:
        pickle.dump(g, handle, protocol=pickle.HIGHEST_PROTOCOL)
    return g


def sparql_file_query__via_python(onto: Graph, query_filename) -> List:
    """Query ontology using SPARQL query file."""
    query_filename = query_filename if query_filename.endswith('.sparql') else query_filename + '.sparql'
    with open(os.path.join(SPARQL_DIR, query_filename), 'r') as f:
        query_str = f.read()
    query = prepareQuery(query_str)
    results: Result = onto.query(query)
    result_list: List = [r for r in results]
    return result_list


def sparql_file_query__via_robot(path_in_data_dir, query_filename, use_cache=USE_CACHE) -> pd.DataFrame:
    """Query ontology using SPARQL query file. path_in_data_dir: ex: mondo/source/mondo-edit.obo"""
    query_filename = query_filename if query_filename.endswith('.sparql') else query_filename + '.sparql'
    query_path = os.path.join(SPARQL_DIR, query_filename)
    onto_path = os.path.join(DATA_DIR, path_in_data_dir)
    results_dirname = path_in_data_dir.replace('/', '-').replace('.', '-') + \
        '__' + query_filename.replace('.', '-')
    results_dirpath = os.path.join(CACHE_DIR, 'robot', results_dirname)
    results_filename = 'results.csv'
    command_save_filename = 'command.sh'
    results_path = os.path.join(results_dirpath, results_filename)
    command_save_path = os.path.join(results_dirpath, command_save_filename)
    command_str = f'robot query --input {onto_path} --query {query_path} {results_path}'

    if not os.path.exists(results_dirpath):
        os.mkdir(results_dirpath)
    if not (os.path.exists(results_path) and use_cache):
        with open(command_save_path, 'w') as f:
            f.write(command_str)
        subprocess.run(command_str.split())

    try:
        df = pd.read_csv(results_path)
    except pd.errors.EmptyDataError as err:
        os.remove(results_path)
        raise err

    return df


def icd_xrefs_mondo__get() -> pd.DataFrame:
    """Get a dataframe of ICD cross-references from Mondo."""
    df = sparql_file_query__via_robot(
        'mondo/source/mondo-edit.obo', 'xrefs_icd_all.sparql')
    df = df.rename(columns={'xref': 'codes'})
    return df


def icd_classes_icd__get() -> pd.DataFrame:
    """Get a dataframe of ICD classes from ICD10CM."""
    df = sparql_file_query__via_robot(
        'icd10cm/bioportal/icd10cm.ttl', 'classes_icd_all.sparql')
    df = df.rename(columns={'cls': 'codes'})
    # This returns <PREFIX>:<CODE>, assuming all entries follow this pattern:
    # ...http://purl.bioontology.org/ontology/<PREFIX>/<CODE>
    df['codes'] = df['codes'].apply(lambda code: ':'.join(code.split('/')[4:6]))
    return df


def analysis_common_codes__get(
    named_dataframes: List[tuple[str, pd.DataFrame]],
    common_field='codes', save=True
) -> pd.DataFrame:
    """Save and return a dataframe of common codes
    Params:
        - named_dataframes: Each entry in this list should be a length 2 tuple
        with 1st entry as the representative name of the dataframe and 2nd entry
        as the dataframe.
        - common_field: The name of a column that is shared between all dataframes
        in `nested_dataframes`. It's expected that all values in this field be
        namespaced codes, in the form of <PREFIX>:<CODE>.
    """
    d = {}
    for name, df in named_dataframes:
        for prefixed_code in df[common_field]:
            ontology_inclusion_field = f'in_{name}'
            prefix, code = prefixed_code.split(':')
            prefix_assumed = prefix.replace('-', '').upper()
            if prefix_assumed in ['ICD9', 'ICD10', 'ICD11']:
                prefix_assumed = f'{prefix_assumed}CM'
            prefixed_code_assumed = f'{prefix_assumed}:{code}'
            if prefixed_code_assumed not in d:
                d[prefixed_code_assumed] = {
                    'prefixAssumed:code': prefixed_code_assumed,
                    'prefixAssumed': prefix_assumed,
                    'prefixOriginal:code': prefixed_code,
                    'prefixOriginal': prefix,
                    'code': code
                }
            d[prefixed_code_assumed][ontology_inclusion_field] = True
    df = pd.DataFrame(d.values())
    # fillna: normally should do on specific cols only; but in OK this case since structure known
    df = df.fillna(False)

    if save:
        _save_csv(df, 'results.csv')
    return df


def analysis_common_codes_stats__get(df, save=True) -> pd.DataFrame:
    """From previous analysis of common codes, get some statistics.
    # noinspection PyPep8: Supposed to suppress Pycharm warning for E712 '=='
    vs 'is', which doesn't apply to Pandas, which overrides these operators."""
    unique_prefixes = df['prefixAssumed'].unique()
    onto_fields = [col for col in df.columns if col.startswith('in_')]
    d = {}
    for p in unique_prefixes:
        for onto_fld in onto_fields:
            # noinspection PyPep8
            subset = df[(df[onto_fld] == True) & (df['prefixAssumed'] == p)]
            ontology = onto_fld.replace('in_', '')
            d[f'{ontology} x {p}'] = {
                'ontology': ontology,
                'prefixAssumed': p,
                'count': len(subset)
            }
    for p in unique_prefixes:
        # noinspection PyPep8
        subset = df[(df[onto_fields[0]] == True) & (df[onto_fields[1]] == True) & (df['prefixAssumed'] == p)]
        ontologies = '; '.join([x.replace('in_', '') for x in onto_fields])
        d[f'{ontologies} x {p}'] = {
            'ontology': ontologies,
            'prefixAssumed': p,
            'count': len(subset)
        }
    stats_df = pd.DataFrame(d.values())
    stats_df = stats_df.sort_values(['ontology', 'prefixAssumed'])
    if save:
        _save_csv(df, 'stats.csv')
    return stats_df


# Execution
icd_xrefs_mondo: pd.DataFrame = icd_xrefs_mondo__get()
icd_classes_icd: pd.DataFrame = icd_classes_icd__get()
common_codes: pd.DataFrame = analysis_common_codes__get([
    ('Mondo', icd_xrefs_mondo),
    ('ICD10CM', icd_classes_icd)])
common_codes_stats: pd.DataFrame = analysis_common_codes_stats__get(common_codes)
print()
