docker run --name notes_analytics2 -it -p 10020:8888 -v "${PWD}":/home/jovyan/work quay.io/jupyter/datascience-notebook:2024-03-14 start-notebook.py --PasswordIdentityProvider.hashed_password='argon2:$argon2id$v=19$m=10240,t=10,p=8$JdAN3fe9J45NvK/EPuGCvA$O/tbxglbwRpOFuBNTYrymAEH6370Q2z+eS1eF4GM6Do'