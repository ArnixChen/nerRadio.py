# nerRadio.py
Script for downloading radio programs of National Education Radio of TAIWAN (www.ner.gov.tw).

## Installation
### Create virtual environment
```bash
python3 -m venv ~/.local/venv_nerRadio
```
### Upgrade pip
```bash
pip install --upgrade pip
```
### Install requirements
```bash
pip install -r requirements.txt
```
### Copy nerRadio.py to your local bin folder
```bash
cp nerRadio.py ~/.local/bin
chmod u+x ~/.local/bin/nerRadio.py
```
## Examples of NER. radio program downloading.
### Get program media by program-name and date.
```bash
syntax: nerRadio.py -n <PROGRAM-NAME> -d <DATE> -g
nerRadio.py -n 麻吉同學會 -d 2024.02.14 -g -o ./
```
