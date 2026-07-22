#!/bin/bash
set -e

echo "--------------------------------------------------------"
echo "  OctaOS Enterprise Local Node Daemon Installer        "
echo "--------------------------------------------------------"

OCTAOS_HOME="$HOME/.octaos"
mkdir -p "$OCTAOS_HOME"
mkdir -p "$OCTAOS_HOME/skills"
mkdir -p "$OCTAOS_HOME/bin"

echo "1. Initializing local virtual environment under $OCTAOS_HOME..."
if [ ! -d "$OCTAOS_HOME/venv" ]; then
    python3 -m venv "$OCTAOS_HOME/venv"
fi

source "$OCTAOS_HOME/venv/bin/activate"

echo "2. Installing runtime dependencies..."
pip install --quiet pyyaml requests sqlalchemy httpx pydantic

echo "3. Creating local octaos CLI executable binary..."
CLI_BIN="$OCTAOS_HOME/bin/octaos"
cat << 'EOF' > "$CLI_BIN"
#!/bin/bash
OCTAOS_HOME="$HOME/.octaos"
source "$OCTAOS_HOME/venv/bin/activate"
PYTHONPATH="/Users/sayantande/OctaOsautomation" python3 -m app.node.octaos_node "$@"
EOF

chmod +x "$CLI_BIN"

echo "--------------------------------------------------------"
echo " SUCCESS! OctaOS Node installed successfully."
echo " Binary Location: $CLI_BIN"
echo " Run '$CLI_BIN --mode SEMI_AUTONOMOUS' to start the daemon."
echo "--------------------------------------------------------"
