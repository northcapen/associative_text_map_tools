import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from evernote_backup.note_exporter_util import SafePath
from evernote_backup.note_formatter import NoteFormatter
from prefect import flow, serve, task
from prefect_shell import ShellOperation
from tqdm import tqdm

from evernote2md.notes_service import NoteTO, mostly_articles_notebooks
from evernote2md.prepared.note_classifier import categorise_notebooks
from evernote2md.tasks.source import (
    convert_db_to_pickle,
    convert_notebooks_db_to_csv,
    read_notes_dataframe,
    read_pickled_notes,
    write_links_dataframe,
    write_notes_dataframe,
)
from evernote2md.tasks.transforms import clean_articles, enrich_data, fix_links

ENEX_FOLDER = "enex2"
IN_DB = "en_backup.db"


def ALL_EXCEPT_ARTICLES_FILTER(nb):
    return nb.name not in mostly_articles_notebooks


def ALL_NOTES(nb):
    return True


def TEXT_MAPS(nb):
    return nb.stack in ["Core", "Maps"]


def specific_notebook(name: str):
    return lambda n: n.notebook.name == name


logger = logging.getLogger("evernote2md")
logger.setLevel(logging.INFO)
handler = logging.FileHandler("application.log")
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)


ENEX_HEAD = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE en-export SYSTEM "http://xml.evernote.com/pub/evernote-export4.dtd">
"""
ENEX_TAIL = "</en-export>\n"


def _write_export_file(file_path: Path, notebook_name: str, notes, note_formatter: NoteFormatter):
    """Write notes to an ENEX file without requiring storage for tasks."""
    with file_path.open("w", encoding="utf-8") as f:
        f.write(ENEX_HEAD)
        f.write('<en-export application="Evernote" version="10.134.4">\n')

        for note in notes:
            # Pass empty list for note_tasks since we don't have storage
            f.write(note_formatter.format_note(note, notebook_name, []))

        f.write(ENEX_TAIL)


@task
def export_enex2(notes: list[NoteTO], context_dir: str, target_dir: str, single_notes=False):
    safe_paths = SafePath(Path(context_dir), overwrite=True)
    note_formatter = NoteFormatter(add_guid=False, add_metadata=False)

    print(context_dir)
    # Use dict to store unique notebooks by guid (Notebook objects are not hashable)
    notebooks_dict = {note.notebook.guid: note.notebook for note in notes}
    notebooks = list(notebooks_dict.values())
    for nb in tqdm(notebooks):
        logger.info(f"Exporting notebook {nb.name}")
        current_notes = [note.note for note in notes if note.notebook.name == nb.name]
        pathes = target_dir.split("/")
        if nb.stack:
            pathes.append(nb.stack)
        notebook_path = safe_paths.get_file(*pathes, f"{nb.name}.enex")
        _write_export_file(notebook_path, nb.name, current_notes, note_formatter)


@task
def read_stacks(context_dir, source_folder, p=lambda x: True):
    original_dir = os.getcwd()  # Save the original working directory

    os.chdir(context_dir)
    x = [stack for stack in os.listdir(source_folder) if os.path.isdir(os.path.join(source_folder, stack)) and p(stack)]
    os.chdir(original_dir)  # Change back to the original working directory
    return x


@task
def yarle(context_dir, root_source, source, target, root_target="md", stream_output=False):
    print(f"Processing stack {source}")

    # Step 2: Open the config.json file in read mode
    with open("evernote2md/yarle/config.json") as file:
        data = json.load(file)

    folder_source = root_source + "/" + source
    logger.info(f"Processing {len(os.listdir(context_dir + '/' + folder_source))} notes")

    data["enexSources"] = [folder_source]
    data["templateFile"] = os.path.abspath("evernote2md/yarle/noteTemplate.tmpl")

    # Step 5: Open the config.json file in write mode
    with open(f"{context_dir}/config.json", "w") as file:
        # Step 6: Dump the updated JSON data back into the file
        json.dump(data, file, indent=4)

    # Get absolute path to yarle from project root's node_modules
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    yarle_script = os.path.join(project_root, "node_modules", "yarle-evernote-to-md", "dist", "dropTheRope.js")

    # Call node directly (shebang with args doesn't work on Linux)
    command = f"node --max-old-space-size=1024 {yarle_script} --configFile config.json"
    logger.info(f"Running: {command}")

    # Use subprocess with real-time output
    process = subprocess.Popen(
        command, shell=True, cwd=context_dir, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )

    for line in process.stdout:
        print(line, end="", flush=True)
        sys.stdout.flush()

    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"yarle failed with return code {return_code}")
    # source_enex = source[:-len('.enex')]
    ShellOperation(
        commands=[
            # replace ![[ to [[ (cross-platform: try GNU sed first, then BSD sed)
            "find md_temp -type f -name '*.md' -exec sed -i 's/!\\[\\[/\\[\\[/g' {} + 2>/dev/null || find md_temp -type f -name '*.md' -exec sed -i '' 's/!\\[\\[/\\[\\[/g' {} +",
            f'rm -rf "{root_target}/{target}"',
            f'mkdir -p "{root_target}/{target}"',
            f'mv md_temp/notes/* "{root_target}/{target}"',
        ],
        working_dir=context_dir,
    ).run()


@flow
def evernote_to_obsidian_flow(
    context_dir,
):
    notes = read_pickled_notes(context_dir, predicate=None)

    notes_cleaned = clean_articles(notes)
    write_notes_dataframe(context_dir, notes=notes_cleaned)

    raw_notes_all = read_notes_dataframe(context_dir)
    notes_w_fixed_links, links = fix_links(raw_notes_all, notes_cleaned)
    write_links_dataframe(context_dir, links=links)

    notes_classified = enrich_data(notes_w_fixed_links)

    export_enex2(notes=notes_classified, context_dir=context_dir, target_dir=ENEX_FOLDER)
    categorise_notebooks(context_dir)

    for stack in read_stacks(context_dir, source_folder=ENEX_FOLDER):
        yarle(context_dir, root_source=ENEX_FOLDER, root_target="md", source=stack, target=stack)


@flow
def db_to_pickle_flow(context_dir):
    convert_db_to_pickle(context_dir=context_dir, db=IN_DB, q=ALL_NOTES)
    convert_notebooks_db_to_csv(db=IN_DB, context_dir=context_dir)


if __name__ == "__main__":
    full = evernote_to_obsidian_flow.to_deployment(
        "evernote-to-obsidian-flow", parameters={"context_dir": "../data/full"}
    )
    small = evernote_to_obsidian_flow.to_deployment(
        "evernote-to-obsidian-flow-small", parameters={"context_dir": "../data/small"}
    )
    db_to_pickle = db_to_pickle_flow.to_deployment("db-to-pickle-flow", parameters={"context_dir": "../data/full"})

    serve(full, small, db_to_pickle)
