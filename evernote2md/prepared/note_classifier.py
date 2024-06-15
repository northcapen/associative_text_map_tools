from typing import Optional

import pandas as pd
from evernote.edam.type.ttypes import Notebook
from prefect import task

from evernote2md.prepared.link_corrector import NoteTransformer
from evernote2md.notes_service import NoteTO


class NoteClassifier(NoteTransformer):

    def transform(self, note: NoteTO) -> Optional[NoteTO]:
        pass

def notebook_classifier(context_dir):
    notebooks_df = pd.read_parquet(context_dir + '/notebooks')
    notebooks_df['tags'] = ''
    for i, r in enumerate(notebooks_df.to_dict(orient='records')):
        tags = classify_notebook(Notebook(guid=r['guid'], name=r['name'], stack=r['stack']))
        notebooks_df.loc[i, 'tags'] = ','.join(tags)

    notebooks_df['tags'].str.split(',', expand=True)


def classify_notebook(notebook: Notebook):
    tagNames = []

    objective = notebook.stack == 'Techs' or 'Ztk' in notebook.name
    tagNames.append('objective' if objective else 'subjective')

    shortTerm = notebook.stack in ['Operations', 'Simple']
    tagNames.append('short-term' if shortTerm else 'long-term')

    articles = 'Articles' in notebook.name
    tagNames.append('authored_by_other' if articles else 'authored_by_me')

    pro = notebook.stack == 'Professional'
    pro_keywords = ['Segmento', 'Panda', 'Rainbow', 'Openway', 'HolyJS', 'Demand']
    pro2 = any(keyword in notebook.name for keyword in pro_keywords)
    tagNames.append('it-specific' if pro or pro2 else 'not-it-specific')

    more_external = 'LJ' in notebook.name or objective
    tagNames.append('more-external' if more_external else 'less-external')
    return tagNames


if __name__ == '__main__':
    notebook_classifier('data/full')