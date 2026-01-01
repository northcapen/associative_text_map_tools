import logging
import sys

from graph.flow import build_graph_stuff

logging.getLogger("evernote_backup").setLevel(logging.DEBUG)

ci_dir = sys.argv[1] if len(sys.argv) > 1 else "full"

build_graph_stuff(context_dir="data/" + ci_dir)
