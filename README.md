# CXL Fabric Congestion Simulator

A high-fidelity discrete-event simulator for studying congestion, QoS, and routing in CXL memory fabric architectures.

## Architecture

```
src/
├── core/           # Event loop, packet models, base classes
├── topology/       # Fabric layouts (tree, mesh, custom)
├── routing/        # Routing algorithms (shortest-path, ECMP)
├── workload/       # Traffic generators, trace replay
└── analysis/       # Metrics collection, visualization
```

## Quick Start

```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run simple example
python examples/simple_fabric.py

# Run tests
pytest tests/
```

## License

MIT License - See LICENSE file
