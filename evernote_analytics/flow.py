from prefect import flow, task, serve

from prefect_shell import ShellOperation

from notes_service import read_notes, mostly_articles_notebooks
from utils import as_sqllite

OUT_DB = 'en_backup.db'
OUT_DB_CORR = 'en_backup_corr.db'

@task
def correct_links(db: str, context_dir: str):
    from link_corrector import process_incorrect_links

    inclusive_filter = lambda nb: nb.name not in mostly_articles_notebooks
    exclusive_filter = lambda nb: nb.stack in ['Core', 'Maps']
    #exclusive_filter = lambda nb: nb.name in ['Self']


    ShellOperation(commands=[f'cd {context_dir} && cp {db} {OUT_DB_CORR}']).run()

    out_db = as_sqllite(context_dir + '/' + OUT_DB_CORR)
    out_db.execute('delete from notes')

    process_incorrect_links(as_sqllite(context_dir + '/' + db), out_db, exclusive_filter)
    return OUT_DB_CORR

@task
def export_enex(db, context_dir, target_dir):
    command = f"cd {context_dir} && evernote-backup export -d {db} --overwrite {target_dir}/"
    print(command)
    ShellOperation(commands=[command]).run()

@task
def yarle(context_dir, enex):
    ShellOperation(commands=[f'cp config.json {context_dir}/']).run()
    command = f"cd {context_dir} && npx -p yarle-evernote-to-md@latest yarle yarle --configFile config.json"
    print(command)
    ShellOperation(commands=[command]).run()
@task
def db_to_parquet(context_dir):
    df = read_notes(as_sqllite(context_dir + '/'+ OUT_DB))
    df.to_parquet(f'{context_dir}/raw_notes')

@flow
def evernote_to_obsidian_flow(context_dir):
    #corr_db = correct_links(db=OUT_DB, context_dir=context_dir)

    enex = 'enex'
    #export_enex(db=corr_db, context_dir=context_dir, target_dir=enex)
    yarle(context_dir, enex=enex)
    #db_to_parquet(context_dir)

if __name__ == '__main__':
    full = evernote_to_obsidian_flow.to_deployment(
        'evernote-to-obsidian-flow', parameters={'context_dir' : 'full'}
    )
    small = evernote_to_obsidian_flow.to_deployment(
        'evernote-to-obsidian-flow-small', parameters={'context_dir' : 'small'}
    )
    serve(full, small)