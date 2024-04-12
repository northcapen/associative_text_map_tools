import json
import os
from pathlib import Path
from typing import List

from evernote_backup.note_exporter import NoteExporter

from prefect import flow, task, serve
from prefect_shell import ShellOperation
from tqdm import tqdm

from evernote2md.cat_service import CatService
from evernote2md.processors import clean_articles, fix_links, enrich_data
from evernote_backup.note_storage import NoteStorage
from notes_service import read_notes, mostly_articles_notebooks, read_notebooks, NoteTO
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
def export_enex(db, context_dir, target_dir, single_notes=False):
    command = f"evernote-backup export -d {db} --overwrite {target_dir}/"
    if single_notes:
        command += ' --single-notes'
    ShellOperation(commands=[command], working_dir=context_dir).run()


@task
def export_enex2(notes: List[NoteTO], context_dir: str, target_dir: str, single_notes=False):
    note_exporter = NoteExporter(storage=None, target_dir=Path(context_dir),
                                 single_notes=single_notes, export_trash=False,
                                 no_export_date=False, overwrite=True)
    print(context_dir)
    notebooks = set(note.notebook for note in notes)
    for nb in tqdm(notebooks):
        current_notes = [note.note for note in notes if note.notebook.name == nb.name]
        note_exporter._output_notebook(target_dir.split('/') + [nb.stack], nb.name, current_notes)


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
    with open('evernote2md/config.json', 'r') as file:
        data = json.load(file)

    data['enexSources'] = ['enex/' + source]
    data['templateFile'] = os.path.abspath('evernote2md/noteTemplate.tmpl')

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

        # orig_db = process_notes(
        #      db=IN_DB, out_db_name=OUT_DB, context_dir=context_dir,
        #      q=q
        # )

    notes_cleaned = clean_articles(context_dir, IN_DB, q)
    links_fixed = fix_links(context_dir, notes_cleaned)
    notes_classified = enrich_data(links_fixed)

    out_db = store_to_db(context_dir, OUT_DB_CORR, notes_classified)

    enex = 'enex2'
    export_enex2(notes=notes_classified, context_dir=context_dir, target_dir=enex)

    for stack in read_stacks(context_dir):
         yarle(context_dir, source=stack, target=stack)


@task
def store_to_db(context_dir, db, notes):
    ShellOperation(commands=[f'cd {context_dir} && cp {IN_DB} {db}']).run()

    out_db = as_sqllite(context_dir + '/' + db)
    out_db.execute('delete from notes')
    out_storage = NoteStorage(out_db)
    for note in tqdm(notes):
        out_storage.add_note(note.note)

    return db


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