import logging
import sys

from evernote2md.flow import evernote_to_obsidian_flow
from graph.flow import build_cosma

logging.getLogger('evernote_backup').setLevel(logging.DEBUG)

ci_dir = sys.argv[1] if len(sys.argv) > 1 else 'full'

build_cosma(context_dir='data/' + ci_dir)
