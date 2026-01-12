# CXL Fabric Congestion Simulator

A high-fidelity discrete-event simulator for studying congestion, QoS, and routing in CXL memory fabric architectures.

## Project Goals

1. **Model realistic CXL switch fabrics** with multi-tier topologies
2. **Simulate congestion scenarios** under memory-disaggregation workloads
3. **Evaluate QoS policies** for fair bandwidth allocation
4. **Enable reproducible research** with open-source tooling

## Timeline (5 Weeks)

- **Week 1**: Core simulation engine, packet/switch models
- **Week 2**: Multi-switch topologies, routing algorithms
- **Week 3**: Realistic workload generation and traces
- **Week 4**: Congestion control schemes, evaluation
- **Week 5**: Paper writing, open-source release

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

## Target Publications

- **HotNets'25** (Aug deadline) - 6 pages
- **HotOS'25** (Jan deadline) - 5 pages  
- **NSDI'26** / **SIGCOMM'26** (full papers)

## License

MIT License - See LICENSE file
