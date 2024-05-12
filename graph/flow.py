import os

from prefect import flow

from evernote2md.tasks.source import read_notes_dataframe, read_links_dataframe


@flow
def build_cosma(context_dir):
    notes = read_notes_dataframe(context_dir)
    links = read_links_dataframe(context_dir)
    links.index.name = 'id'
    links = links.rename(columns={'from_guid' : 'source', 'to_guid' : 'target'}).reset_index()
    target = context_dir + '/cosma/'
    os.makedirs(target, exist_ok=True)
    notes.to_csv(target + 'notes.csv', index=False)
    links.to_csv(target + 'links.csv', index=False)
