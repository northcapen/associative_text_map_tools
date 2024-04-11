from typing import Callable, Iterator, Dict, Any

import json

import os

import pandas as pd
from evernote.edam.type.ttypes import Note
from tqdm import tqdm

from evernote_backup.note_storage import NoteStorage
from prefect import flow, task, serve
from prefect_shell import ShellOperation

from evernote2md.cat_service import CatService
from evernote2md.note_classifier import NoteClassifier
from link_corrector import LinkFixer, ArticleCleaner
from notes_service import read_notes, mostly_articles_notebooks, read_notebooks, \
    deep_notes_iterator
from utils import as_sqllite

IN_DB = 'en_backup.db'
OUT_DB = 'en_backup_nocorr.db'
OUT_DB_CORR = 'en_backup_corr.db'

ALL_EXCEPT_ARTICLES_FILTER = lambda nb: nb.name not in mostly_articles_notebooks
ALL_NOTES = lambda nb: True
TEXT_MAPS = lambda nb: nb.stack in ['Core', 'Maps']

class IdentityProcessor:
    def __init__(self):
        self.buffer = []

    def transform(self, note):
        return note

@task
def process_notes(db: str, context_dir: str, out_db_name: str, q: Callable, processor):
    from link_corrector import traverse_notes

    ShellOperation(commands=[f'cd {context_dir} && cp {db} {out_db_name}']).run()

    indb = as_sqllite(context_dir + '/' + db)

    notes = {note.guid: note for note in (deep_notes_iterator(indb, q))}
    result = traverse_notes(list(notes.values()), processor)

    out_db = as_sqllite(context_dir + '/' + out_db_name)
    out_db.execute('delete from notes')
    out_storage = NoteStorage(out_db)
    for note in tqdm(result):
        out_storage.add_note(note.note)

    #pd.DataFrame(link_fixer.buffer).to_csv(f'{context_dir}/links.csv')
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
def yarle(context_dir, source, target, root_dir='md'):
    print(f'Processing stack {source}')

    # Step 2: Open the config.json file in read mode
    with open('config.json', 'r') as file:
        data = json.load(file)

    data['enexSources'] = ['enex/' + source]
    data['templateFile'] = os.path.abspath('noteTemplate.tmpl')

    # Step 5: Open the config.json file in write mode
    with open(f'{context_dir}/config.json', 'w') as file:
        # Step 6: Dump the updated JSON data back into the file
        json.dump(data, file, indent=4)

    command = f"npx -p yarle-evernote-to-md@latest yarle yarle --configFile config.json"
    print(command)
    ShellOperation(commands=[command], working_dir=context_dir).run()
    #source_enex = source[:-len('.enex')]
    ShellOperation(
        commands=[
            f'rm -rf "{root_dir}/{target}"',
            f'mkdir -p "{root_dir}/{target}"',
            f'mv md_temp/notes/* "{root_dir}/{target}"'
        ],
        working_dir=context_dir
    ).run()


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

        orig_db = process_notes(
             db=IN_DB, out_db_name=OUT_DB, context_dir=context_dir,
             q=q
        )

    corr_db = process_notes(
        db=IN_DB,
        out_db_name=OUT_DB_CORR,
        context_dir=context_dir,
        q=q,
        processor=ArticleCleaner()
    )

    notes_p = note_metadata(context_dir, active=True)
    notes_trash = note_metadata(context_dir, active=True)
    link_fixer = LinkFixer(notes_p, notes_trash)

    links_fixed = process_notes(
        db=corr_db,
        out_db_name='out_link_fixed.db',
        context_dir=context_dir,
        corr=True,
        q=q,
        processor=link_fixer
    )

    notes_classified = process_notes(
        db=links_fixed,
        out_db_name='notes_classified.db',
        context_dir=context_dir,
        corr=True,
        q=q,
        processor=NoteClassifier()
    )


    enex = 'enex'
    export_enex(db=notes_classified, context_dir=context_dir, target_dir=enex)

    for stack in read_stacks(context_dir, lambda stack: stack == 'Core'):
         yarle(context_dir, source=stack, target=stack)


def note_metadata(context_dir, active=True) -> Dict[Any, Note]:
    notes_parquet = pd.read_parquet(f'{context_dir}/raw_notes').query('active == @active')
    print(notes_parquet.columns)
    buff = {}
    for note in notes_parquet.itertuples():
         # noinspection PyUnresolvedReferences
         buff[note.id] = Note(guid=note.id, title=note.title)

    return buff


@flow
def adhoc_flow(context_dir):
    # enex = 'enex_single_notes'
    # export_enex(db=OUT_DB, context_dir=context_dir, target_dir=enex, single_notes=True)


    for stack in read_stacks(context_dir, p=lambda stack: stack == 'Core'):
        yarle(context_dir, stack, CatService().get_cat2(cat3=stack) + '/' + stack, root_dir='mdx')

if __name__ == '__main__':
    full = evernote_to_obsidian_flow.to_deployment(
        'evernote-to-obsidian-flow', parameters={'context_dir' : '../data/full'}
    )
    small = evernote_to_obsidian_flow.to_deployment(
        'evernote-to-obsidian-flow-small', parameters={'context_dir' : '../data/small'}
    )
    adhoc_flow_full = adhoc_flow.to_deployment('adhoc-flow', parameters={'context_dir' : '../data/full'})

    serve(full, small, adhoc_flow_full)