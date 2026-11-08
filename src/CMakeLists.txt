# Build the compiled FIT kernel.
#
#   standalone, from the repository root:
#     cmake -S src -B build/cpp -DCMAKE_BUILD_TYPE=Release
#     cmake --build build/cpp -j
#     PYTHONPATH=build/cpp python3 -m pytest tests/test_cpp_parity.py -q
#
#   as part of `pip install -e .` / `pip install .`: scikit-build-core drives
#   this same file, and the install() rule at the bottom puts the extension at
#   the root of the wheel, i.e. the top-level module `emfit_core`.
#
# pybind11 is OPTIONAL on purpose.  emfit.evolve.step_explicit is the reference;
# this kernel is the fast twin whose parity is not yet established.  A machine
# without pybind11 must still get a working pure-Python install, so when
# pybind11 is missing this file says so loudly and returns: the build stays
# green and the only consequence is that tests/test_cpp_parity.py skips instead
# of comparing.
#
# -O3 with NO -ffast-math / -fassociative-math: the kernel claims bit-identical
# agreement with the Python reference, and reassociation would break that
# promise while every test still "passed" to 1e-12.
cmake_minimum_required(VERSION 3.18)
project(emfit_core LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(pybind11 CONFIG QUIET)
if(NOT pybind11_FOUND)
    message(WARNING
        "pybind11 not found (find_package(pybind11 CONFIG) failed): the compiled "
        "FIT kernel `emfit_core` is NOT being built. Nothing else changes -- "
        "emfit.evolve.step_explicit is the reference and stays authoritative, "
        "and tests/test_cpp_parity.py will skip rather than compare. To build "
        "it: `python3 -m pip install pybind11`, then re-run this configure (or "
        "`pip install -e .` from the repository root).")
    return()
endif()

find_package(OpenMP REQUIRED COMPONENTS CXX)

pybind11_add_module(emfit_core
    bindings.cpp
    emfit_core.cpp
)
target_include_directories(emfit_core PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_options(emfit_core PRIVATE -O3 -fopenmp)
target_link_libraries(emfit_core PRIVATE OpenMP::OpenMP_CXX)

# Destination "." is the root of the wheel, which is what makes the extension
# importable as the top-level module `emfit_core`.  Inert in the standalone
# build: it only takes effect under `cmake --install`.
install(TARGETS emfit_core LIBRARY DESTINATION . RUNTIME DESTINATION .)
