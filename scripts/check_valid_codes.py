"""Check that ICD codes found in mondo-edit.obo are valid ICD codes.
TODO: load w/ ontobio or rdflib?
"""
import os
import pickle
from pathlib import Path

from ontobio import OntologyFactory
from rdflib import Graph


PROJECT_DIR = os.path.join(os.path.dirname(__file__), '..')
DATA_DIR = os.path.join(PROJECT_DIR, 'data')
CACHE_DIR = os.path.join(PROJECT_DIR, 'cache')
ICD10_PATH = os.path.join(DATA_DIR, 'icd10cm', 'bioportal', 'icd10cm.ttl')
# TODO: Consider alternative options
#  - https://obofoundry.org/ontology/mondo.html (DL JSON version & open w/ ontobio)
#  - Update my grep to save the codes as well (not just the prefixes)
MONDO_PATH = os.path.join(DATA_DIR, 'mondo', 'mondo-edit.obo')


# Option A: RDF lib
# TODO: refactor this pickle code
pickle_file = Path(CACHE_DIR, os.path.basename(ICD10_PATH).replace('.', '-') + '.pickle')
use_cache = True
if pickle_file.is_file() and use_cache:
    icd_graph = pickle.load(open(pickle_file, 'rb'))
else:
    icd_graph = Graph()
    icd_graph.parse(ICD10_PATH)
    with open(pickle_file, 'wb') as handle:
        pickle.dump(icd_graph, handle, protocol=pickle.HIGHEST_PROTOCOL)

# TODO: What's best way to check if ICD codes are properly in this graph?
for subj, pred, obj in icd_graph:
    print(subj, pred, obj)

# Option C: Pronto
# https://pypi.org/project/pronto/
# TODO: Try opening OBO file with this

# Option B: Ontobio
ont_factory = OntologyFactory
# mondo_ont = ont_factory.create('obo:Mondo')
# with open(MONDO_PATH, 'r') as f:xx
#     mondo_ont = ont_factory.create(str(f))
#     mondo_ont = ont_factory.create(f)x
with open(ICD10_PATH, 'r') as f:
    # Err: "Virtuoso 37000 Error SP030: SPARQL compiler
    # icd10_ont = ont_factory.create(str(f))
    icd10_ont = ''

print()
