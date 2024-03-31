from typing import Callable

import json

import os

import pandas as pd
from prefect import flow, task, serve
from prefect_shell import ShellOperation

from link_corrector import LinkFixer
from notes_service import read_notes, mostly_articles_notebooks, read_notebooks
from utils import as_sqllite

IN_DB = 'en_backup.db'
OUT_DB = 'en_backup_nocorr.db'
OUT_DB_CORR = 'en_backup_corr.db'

ALL_EXCEPT_ARTICLES_FILTER = lambda nb: nb.name not in mostly_articles_notebooks
ALL_NOTES = lambda nb: True
TEXT_MAPS = lambda nb: nb.stack in ['Core', 'Maps']

class DummyProcessor:
    def __init__(self):
        self.notes = None
        self.buffer = []

    def transform(self, note):
        return note

@task
def correct_links(db: str, context_dir: str, out_db_name: str, q: Callable, corr=False):
    from link_corrector import traverse_notes

    ShellOperation(commands=[f'cd {context_dir} && cp {db} {out_db_name}']).run()

    out_db = as_sqllite(context_dir + '/' + out_db_name)
    out_db.execute('delete from notes')
    traverser = LinkFixer() if corr else DummyProcessor()
    traverse_notes(as_sqllite(context_dir + '/' + db), out_db, q, traverser)
    pd.DataFrame(traverser.buffer).to_csv(f'{context_dir}/links.csv')
    return out_db_name

@task
def export_enex(db, context_dir, target_dir, single_notes=False):
    command = f"evernote-backup export -d {db} --overwrite {target_dir}/"
    if single_notes:
        command += ' --single-notes'
    ShellOperation(commands=[command], working_dir=context_dir).run()

@task
def read_stacks(context_dir, p=lambda x: True):
    original_dir = os.getcwd()  # Save the original working directory

    os.chdir(context_dir)
    x = [
        stack for stack in os.listdir('enex')
        if os.path.isdir(os.path.join('enex', stack)) and p(stack)
    ]
    os.chdir(original_dir)  # Change back to the original working directory
    return x


@task
def yarle(context_dir, source):
    print(f'Processing stack {source}')

    # Step 2: Open the config.json file in read mode
    with open('config.json', 'r') as file:
        data = json.load(file)

    data['enexSources'] = ['enex/' + source]

    # Step 5: Open the config.json file in write mode
    with open(f'{context_dir}/config.json', 'w') as file:
        # Step 6: Dump the updated JSON data back into the file
        json.dump(data, file, indent=4)

    command = f"npx -p yarle-evernote-to-md@latest yarle yarle --configFile config.json"
    print(command)
    ShellOperation(commands=[command], working_dir=context_dir).run()
    #source_enex = source[:-len('.enex')]
    ShellOperation(commands=[
        f'rm -rf "md/{source}"',
        f'mkdir -p "md/{source}"',
        f'mv md_temp/notes/* '
        f'"md/{source}"'],
        working_dir=context_dir).run()


@task
def db_to_parquet(context_dir):
    db = as_sqllite(context_dir + '/' + IN_DB)

    df = read_notes(db)
    df.to_parquet(f'{context_dir}/raw_notes')

    df = read_notebooks(db)
    df.to_parquet(f'{context_dir}/notebooks')

@flow
def evernote_to_obsidian_flow(context_dir, aux=False):
    # exclusive_filter = lambda nb: nb.name in ['Self']
    q = ALL_NOTES
    if aux:
        db_to_parquet(context_dir)

        enex = 'enex_single_notes'
        export_enex(db=OUT_DB, context_dir=context_dir, target_dir=enex, single_notes=True)

        orig_db = correct_links(
             db=IN_DB, out_db_name=OUT_DB, context_dir=context_dir,
             q=q
        )

    corr_db = correct_links(db=IN_DB, out_db_name=OUT_DB_CORR, context_dir=context_dir, corr=True, q=q)
    corr_db = OUT_DB_CORR

    enex = 'enex'
    export_enex(db=corr_db, context_dir=context_dir, target_dir=enex)

    for stack in read_stacks(context_dir):
         yarle(context_dir, stack)

@flow
def adhoc_flow(context_dir):
    # enex = 'enex_single_notes'
    # export_enex(db=OUT_DB, context_dir=context_dir, target_dir=enex, single_notes=True)

    for stack in read_stacks(context_dir, p=lambda stack: stack == 'Core'):
        yarle(context_dir, stack)

if __name__ == '__main__':
    full = evernote_to_obsidian_flow.to_deployment(
        'evernote-to-obsidian-flow', parameters={'context_dir' : '../data/full'}
    )
    small = evernote_to_obsidian_flow.to_deployment(
        'evernote-to-obsidian-flow-small', parameters={'context_dir' : '../data/small'}
    )
    adhoc_flow_full = adhoc_flow.to_deployment('adhoc-flow', parameters={'context_dir' : '../data/full'})

    serve(full, small, adhoc_flow_full)