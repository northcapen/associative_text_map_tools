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


def classify_notebook(nb_df: DataFrame):
    objective = (nb_df.stack == 'Techs') | (nb_df.name.str.contains('Ztk'))
    nb_df['objective'] = np.where(objective, 'objective', 'subjective')

    shortTerm = (nb_df.stack == 'Operations') | (nb_df.stack == 'Simple')
    nb_df['longetivity'] = np.where(shortTerm, 'short', 'long')
    nb_df['authorship'] = np.where(nb_df.name.str.contains('Articles'), 'other', 'me')

    pro_keywords = ['Segmento', 'Panda', 'Rainbow', 'Openway', 'HolyJS', 'Demand']
    pattern = '|'.join(pro_keywords)
    pro = nb_df['stack'] == 'Professional'
    pro2 = nb_df['name'].str.contains(pattern)
    nb_df['it-specific'] = np.where(pro | pro2, 'true', 'false')

    # Combine conditions
    more_external = nb_df.name.str.contains('LJ') | objective
    nb_df['externality'] = np.where(more_external, 'more', 'less')


if __name__ == '__main__':
    notebook_classifier('data/full')
