from prefect import flow, task, serve

from prefect_shell import ShellOperation

from notes_service import read_notes
from utils import as_sqllite

OUT_DB = 'en_backup.db'
OUT_DB_CORR = 'en_small_corr.db'

@task
def correct_links(db):
    pass
    # #from link_corrector import process_incorrect_links
    #
    # ShellOperation(commands=[f'cp {db} {OUT_DB_CORR}']).run()
    # process_incorrect_links(as_sqllite(OUT_DB_CORR))

@task
def export_enex(db, context_dir):
    command = f"cd {context_dir} && evernote-backup export -d {db} --overwrite export/"
    print(command)
    ShellOperation(commands=[command]).run()

@task
def yarle(context_dir, enex):
    command = f"cd {context_dir} && npx -p yarle-evernote-to-md@latest yarle yarle --configFile ../config.json"
    print(command)
    ShellOperation(commands=[command]).run()
@task
def db_to_parquet(context_dir):
    df = read_notes(as_sqllite(context_dir + '/'+ OUT_DB))
    df.to_parquet(f'{context_dir}/raw_notes')

@flow
def evernote_to_obsidian_flow(context_dir):
    #correct_links(db=OUT_DB)
    export_enex(OUT_DB, context_dir)
    yarle(context_dir, enex=None)
    db_to_parquet(context_dir)

if __name__ == '__main__':
    full = evernote_to_obsidian_flow.to_deployment(
        'evernote-to-obsidian-flow', parameters={'context_dir' : 'full'}
    )
    small = evernote_to_obsidian_flow.to_deployment(
        'evernote-to-obsidian-flow-small', parameters={'context_dir' : 'small'}
    )
    serve(full, small)