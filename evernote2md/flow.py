import json
import logging
import os
from pathlib import Path
from typing import List

import pandas as pd

from evernote2md.tasks.source import write_notes_dataframe, convert_db_to_pickle, \
    read_pickled_notes, read_notes_dataframe, write_links_dataframe
from evernote_backup.note_exporter import NoteExporter

from prefect import flow, task, serve
from prefect_shell import ShellOperation
from tqdm import tqdm

from evernote2md.tasks.transforms import clean_articles, fix_links, enrich_data
from evernote2md.notes_service import mostly_articles_notebooks, NoteTO

ENEX_FOLDER = 'enex2'

IN_DB = 'en_backup.db'

ALL_EXCEPT_ARTICLES_FILTER = lambda nb: nb.name not in mostly_articles_notebooks
ALL_NOTES = lambda nb: True
TEXT_MAPS = lambda nb: nb.stack in ['Core', 'Maps']

def specific_notebook(name: str):
    return lambda n: n.notebook.name == name

logger = logging.getLogger('evernote2md')
logger.setLevel(logging.INFO)
handler = logging.FileHandler('application.log')
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


@task
def export_enex2(notes: List[NoteTO], context_dir: str, target_dir: str, single_notes=False):
    note_exporter = NoteExporter(storage=None, target_dir=Path(context_dir),
                                 single_notes=single_notes, export_trash=False,
                                 no_export_date=True, overwrite=True)
    print(context_dir)
    notebooks = set(note.notebook for note in notes)
    for nb in tqdm(notebooks):
        logger.info(f'Exporting notebook {nb.name}')
        current_notes = [note.note for note in notes if note.notebook.name == nb.name]
        pathes = target_dir.split('/')
        if nb.stack:
            pathes.append(nb.stack)
        note_exporter._output_notebook(pathes, nb.name, current_notes)


@task
def read_stacks(context_dir, p=lambda x: True):
    original_dir = os.getcwd()  # Save the original working directory

    os.chdir(context_dir)
    x = [
        stack for stack in os.listdir(ENEX_FOLDER)
        if os.path.isdir(os.path.join(ENEX_FOLDER, stack)) and p(stack)
    ]
    os.chdir(original_dir)  # Change back to the original working directory
    return x


@task
def yarle(context_dir, source, target, root_dir='md', stream_output=False):
    if on_ci(context_dir):
        return

    print(f'Processing stack {source}')

    # Step 2: Open the config.json file in read mode
    with open('evernote2md/yarle/config.json', 'r') as file:
        data = json.load(file)

    folder_source = ENEX_FOLDER + '/' + source
    logger.info(f"Processing {len(os.listdir(context_dir + '/' + folder_source))} notes")

    data['enexSources'] = [folder_source]
    data['templateFile'] = os.path.abspath('evernote2md/yarle/noteTemplate.tmpl')

    # Step 5: Open the config.json file in write mode
    with open(f'{context_dir}/config.json', 'w') as file:
        # Step 6: Dump the updated JSON data back into the file
        json.dump(data, file, indent=4)

    command = f"npx -p yarle-evernote-to-md@latest yarle yarle --configFile config.json"
    logger.debug(command)
    ShellOperation(commands=[command], working_dir=context_dir, stream_output=stream_output).run()
    #source_enex = source[:-len('.enex')]
    ShellOperation(
        commands=[
            # replace ![[ to [[
            "find md_temp -type f -name '*.md' -exec sed -i '' 's/!\[\[/\[\[/g' {} +",
            f'rm -rf "{root_dir}/{target}"',
            f'mkdir -p "{root_dir}/{target}"',
            f'mv md_temp/notes/* "{root_dir}/{target}"'
        ],
        working_dir=context_dir
    ).run()


def on_ci(context_dir):
    return '_ci' in context_dir


@flow
def evernote_to_obsidian_flow(context_dir,):
    notes = read_pickled_notes(context_dir, predicate=None)

    notes_cleaned = clean_articles(notes)
    write_notes_dataframe(context_dir, notes=notes_cleaned)

    raw_notes_all = read_notes_dataframe(context_dir)
    notes_w_fixed_links, links = fix_links(raw_notes_all, notes_cleaned)
    write_links_dataframe(context_dir, links=links)

    notes_classified = enrich_data(notes_w_fixed_links)

    enex = 'enex2'
    export_enex2(notes=notes_classified, context_dir=context_dir, target_dir=enex)

    for stack in read_stacks(context_dir):
         yarle(context_dir, source=stack, target=stack)


@flow
def db_to_pickle_flow(context_dir):
    convert_db_to_pickle(context_dir, db=IN_DB, q=ALL_NOTES)


if __name__ == '__main__':
    full = evernote_to_obsidian_flow.to_deployment(
        'evernote-to-obsidian-flow', parameters={'context_dir' : '../data/full'}
    )
    small = evernote_to_obsidian_flow.to_deployment(
        'evernote-to-obsidian-flow-small', parameters={'context_dir' : '../data/small'}
    )
    db_to_pickle = db_to_pickle_flow.to_deployment('db-to-pickle-flow', parameters={'context_dir' : '../data/full'})

    serve(full, small, db_to_pickle)