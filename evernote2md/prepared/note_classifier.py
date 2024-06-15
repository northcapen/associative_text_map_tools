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
    techs = notebooks.stack == 'Techs'
    objective = (techs) | (notebooks.name.str.contains('Ztk'))
    notebooks['objective'] = np.where(objective, 'objective', 'subjective')

    shortTerm = (notebooks.stack == 'Operations') | (notebooks.stack == 'Simple')
    notebooks['longetivity'] = np.where(shortTerm, 'short', 'long')
    notebooks['authorship'] = np.where(notebooks.name.str.contains('Articles'), 'other', 'me')

    ex_work_projects = ['Segmento', 'Panda', 'Rainbow', 'Openway', 'HolyJS', 'Demand']
    pro = notebooks['stack'] == 'Professional'
    pro_ex = notebooks['name'].str.contains('|'.join(ex_work_projects))
    pro_rubbles = notebooks['name'].str.contains('|'.join(ex_work_projects))
    notebooks['it-specific'] = np.where(pro | pro_ex | pro_rubbles | techs, 'yes', 'no')

    # Combine conditions
    more_external = notebooks.name.str.contains('LJ') | objective
    notebooks['externality'] = np.where(more_external, 'more', 'less')
    journals = notebooks.name == 'Dailys'
    notebooks['journals'] = np.where(journals, 'yes', 'no')

    private = journals | (notebooks.name == 'Romance')
    confidential = pro_ex | pro_rubbles
    public = objective

    notebooks['sensitivity'] = np.where(private, 'private', np.where(confidential, 'confidential',
                                                                     np.where(public, public,
                                                                              'sensitive')))


if __name__ == '__main__':
    notebook_classifier('data/full')
