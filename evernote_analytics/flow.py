
from prefect import flow, task

from prefect_shell import ShellOperation

from notes_service import read_notes
from utils import as_sqllite

OUT_DB = 'data/en_small.db'
OUT_DB_CORR = 'data/en_small_corr.db'

@task
def correct_links(db):
    pass
    # #from link_corrector import process_incorrect_links
    #
    # ShellOperation(commands=[f'cp {db} {OUT_DB_CORR}']).run()
    # process_incorrect_links(as_sqllite(OUT_DB_CORR))

@task
def export_enex(db, folder):
    command = f"evernote-backup export -d {folder}/{db} --overwrite data/export2/"
    ShellOperation(commands=[command]).run()

@task
def yarle(folder, enex):
    command = f" npx -p yarle-evernote-to-md@latest yarle yarle --configFile config.json"
    ShellOperation(commands=[command]).run()
@task
def db_to_parquet(folder):
    df = read_notes(as_sqllite(OUT_DB))
    df.to_parquet(f'{folder}/data/raw_notes')

@flow
def evernote_to_obsidian_flow():
    folder = '.'
    #correct_links(db=OUT_DB)
    export_enex(OUT_DB, folder)
    yarle(folder, enex=None)
    db_to_parquet(folder)

if __name__ == '__main__':
    evernote_to_obsidian_flow.serve('evernote-to-obsidian-flow')