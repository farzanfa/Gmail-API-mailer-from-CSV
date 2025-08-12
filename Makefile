VENV=.venv
PY=$(VENV)/bin/python

install:
	python -m venv $(VENV)
	$(PY) -m pip install -U pip
	$(PY) -m pip install -r requirements.txt

auth:
	$(PY) mail_from_csv.py --csv recipients.csv --subject @subject.txt --html @body.html --dry_run

dryrun:
	$(PY) mail_from_csv.py --csv recipients.csv --subject @subject.txt --html @body.html --dry_run

send:
	$(PY) mail_from_csv.py --csv recipients.csv --subject @subject.txt --html @body.html
