if [ ! -d "env" ]; then
    python3 -m venv env
    source env/bin/activate
    pip install -r requirements.txt
else
    source env/bin/activate
    pip freeze | grep -q -f requirements.txt || pip install -r requirements.txt
fi
python3 book-manager.py
