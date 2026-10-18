# Legacy factory-only solvers

The first versions of the solvers and checker, written for factories only. They were replaced by the
domain-agnostic core (`engine/core/`) and the factory adapter (`engine/adapters/factory.py`), which give
the same results (see `tests/test_core.py::TestFactoryParity`). Kept for reference; nothing imports them.
