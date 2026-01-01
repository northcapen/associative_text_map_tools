import os

import numpy as np
import pandas as pd
from pandas import DataFrame
from prefect import task

from evernote2md.notes_service import NoteTO
from evernote2md.prepared.link_corrector import NoteTransformer
from evernote2md.tasks.source import NOTEBOOK_CSV


class NoteClassifier(NoteTransformer):
    def transform(self, note: NoteTO) -> NoteTO | None:
        return note


@task
def categorise_notebooks(context_dir: str):
    secret_notebooks = os.environ.get("SECRET_NOTEBOOKS", None)
    if secret_notebooks:
        secret_notebooks = secret_notebooks.split(",")
    else:
        secret_notebooks = []

    print(secret_notebooks)
    notebooks_df = pd.read_csv(f"{context_dir}/{NOTEBOOK_CSV}")
    categorise_notebooks0(notebooks_df, secret_notebooks)
    notebooks_df.to_csv(f"{context_dir}/notebooks2.csv", index=False)


def categorise_notebooks0(notebooks: DataFrame, secret_notebooks: list[str] = None):
    articles = notebooks["name"].str.contains("Articles")
    notebooks["authorship"] = np.where(articles, "other", "me")

    techs = notebooks["stack"] == "Techs"
    objective = (techs) | (notebooks["name"].str.contains("Ztk")) | articles
    notebooks["objective"] = np.where(objective, "objective", "subjective")

    short_term = (notebooks["stack"] == "Operations") | (notebooks["stack"] == "Simple")
    notebooks["longetivity"] = np.where(short_term, "short", "long")

    ex_work_projects = ["Segmento", "Panda", "Rainbow", "Openway", "HolyJS", "Demand", "Veil", "Alter"]
    pro = notebooks["stack"] == "Professional"
    pro_ex = notebooks["name"].str.contains("|".join(ex_work_projects))
    pro_current = notebooks["stack"] == "Rubbles"
    notebooks["it-specific"] = np.where(pro | pro_ex | pro_current | techs, "yes", "no")

    # Combine conditions
    more_external = notebooks["name"].str.contains("LJ") | objective
    notebooks["externality"] = np.where(more_external, "more", "less")
    journals = notebooks["name"] == "Dailys"
    notebooks["journals"] = np.where(journals, "yes", "no")

    private = journals | (
        notebooks["name"].isin(
            [
                "Self",
                "Romance",
                "Medical",
                "Documents",
                "Psychotherapy",
                "Security Codes",
                "Sensual",
                "Dreams and long terms",
                "Relations",
                "Personal Finance",
            ]
        )
    )
    confidential = pro_ex | pro_current
    public = objective
    concepts = notebooks["name"].isin(["Concepts", "Concept placeholders"])
    lm = notebooks["stack"] == "LM Stack"
    personal_projects = notebooks["stack"] == "Personal Projects"
    protected = concepts | lm | pro | personal_projects
    secret = notebooks["name"].isin(secret_notebooks)

    notebooks["sensitivity"] = "sensitive"
    notebooks.loc[public, "sensitivity"] = "public"
    notebooks.loc[protected, "sensitivity"] = "protected"
    notebooks.loc[confidential, "sensitivity"] = "confidential"
    notebooks.loc[private, "sensitivity"] = "private"
    notebooks.loc[secret, "sensitivity"] = "secret"


if __name__ == "__main__":
    categorise_notebooks("data/full")
