
.PHONY: sync publish
sync:
	pushd ~/Documents/LM && evernote-backup sync && popd
	cp ~/Documents/LM/en_backup.db data/full/

main_flow_small:
	source .env.local && PYTHONPATH=. .venv/bin/python evernote2md/runner.py small db_to_pickle

main_flow_full:
	source .env.local && PYTHONPATH=. .venv/bin/python evernote2md/runner.py full skip

main_flow_full_refresh:
	source .env.local && PYTHONPATH=. .venv/bin/python evernote2md/runner.py full db_to_pickle


publish_ga_docs:
	mkdir -p ~/IdeaProjects/GADocs/demand_wiki/
	cp -R data/demand_ztk/md ~/IdeaProjects/GADocs/demand_wiki/

lint:
	source .venv/bin/activate && ruff check .

lint-fix:
	source .venv/bin/activate && ruff check --fix .

format:
	source .venv/bin/activate && ruff format .

format-check:
	source .venv/bin/activate && ruff format --check .