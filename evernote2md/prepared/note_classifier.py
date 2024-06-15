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
    nb_df['shortTerm'] = np.where(shortTerm, 'short', 'long')

    articles = nb_df.name.str.contains('Articles')
    nb_df['articles'] = np.where(articles, 'other', 'me')

    pro_keywords = ['Segmento', 'Panda', 'Rainbow', 'Openway', 'HolyJS', 'Demand']
    pattern = '|'.join(pro_keywords)
    # Check if 'stack' is 'Professional'
    pro = nb_df['stack'] == 'Professional'

    # Check if any keyword is in 'name'
    pro2 = nb_df['name'].str.contains(pattern)
    nb_df['it-specific'] = np.where(pro | pro2, 'true', 'false')

    # Combine conditions
    more_external = nb_df.name.str.contains('LJ') | objective
    nb_df['more_external'] = np.where(more_external, 'more-external', 'less-external')


if __name__ == '__main__':
    notebook_classifier('data/full')
