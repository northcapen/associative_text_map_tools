from typing import Optional

import numpy as np
import pandas as pd
from pandas import DataFrame

from evernote2md.prepared.link_corrector import NoteTransformer
from evernote2md.notes_service import NoteTO


class NoteClassifier(NoteTransformer):

    def transform(self, note: NoteTO) -> Optional[NoteTO]:
        pass


def notebook_classifier(context_dir):
    notebooks_df = pd.read_parquet(context_dir + '/notebooks')
    classify_notebook(notebooks_df)

    notebooks_df.to_csv('notebooks2.csv')


def classify_notebook(notebooks: DataFrame):
    objective = (notebooks.stack == 'Techs') | (notebooks.name.str.contains('Ztk'))
    notebooks['objective'] = np.where(objective, 'objective', 'subjective')

    shortTerm = (notebooks.stack == 'Operations') | (notebooks.stack == 'Simple')
    notebooks['longetivity'] = np.where(shortTerm, 'short', 'long')
    notebooks['authorship'] = np.where(notebooks.name.str.contains('Articles'), 'other', 'me')

    pro_keywords = ['Segmento', 'Panda', 'Rainbow', 'Openway', 'HolyJS', 'Demand']
    pattern = '|'.join(pro_keywords)
    pro = notebooks['stack'] == 'Professional'
    pro2 = notebooks['name'].str.contains(pattern)
    notebooks['it-specific'] = np.where(pro | pro2, 'true', 'false')

    # Combine conditions
    more_external = notebooks.name.str.contains('LJ') | objective
    notebooks['externality'] = np.where(more_external, 'more', 'less')


if __name__ == '__main__':
    notebook_classifier('data/full')
