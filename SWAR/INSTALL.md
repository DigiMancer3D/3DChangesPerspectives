# Installing SWAR

## Kubuntu 24+ / Ubuntu 24+

```bash
chmod +x install_kubuntu.sh launch_reader.sh launch_standard.sh run_selftests.sh install_desktop_entries.sh
./install_kubuntu.sh
./run_selftests.sh
./launch_standard.sh examples/example.script
```

`install_kubuntu.sh` creates a local `venv/` in the SWAR folder and installs the dependencies from `requirements.txt`.

## Arch Linux

Install Python and Qt runtime support first if needed:

```bash
sudo pacman -S python python-pip
```

Then from the SWAR folder:

```bash
python -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
./run_selftests.sh
./launch_standard.sh examples/example.script
```

## Generic Linux

Use Python 3.10+.

```bash
python3 -m venv venv
source venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 -m pytest -q
python3 swar.py --standard examples/example.script
```

## Windows / macOS notes

The Python code is intended to stay cross-platform, but the bundled launcher scripts are Linux shell scripts. On Windows or macOS, create a Python virtual environment, install `requirements.txt`, then run:

```bash
python swar.py --standard examples/example.script
python swar.py --reader examples/example.script
```

Desktop-entry installation is Linux-specific.
