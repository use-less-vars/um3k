# Build the compiled FIT kernel:
#
#     cmake -S src -B build/cpp -DCMAKE_BUILD_TYPE=Release
#     cmake --build build/cpp -j
#     PYTHONPATH=build/cpp python3 -m pytest tests/test_cpp_parity.py -q
#
# -O3 with NO -ffast-math / -fassociative-math: the kernel claims bit-identical
# agreement with the Python reference, and reassociation would break that
# promise while every test still "passed" to 1e-12.
cmake_minimum_required(VERSION 3.18)
project(emfit_core LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(pybind11 CONFIG REQUIRED)
find_package(OpenMP REQUIRED COMPONENTS CXX)

pybind11_add_module(emfit_core
    bindings.cpp
    emfit_core.cpp
)
target_include_directories(emfit_core PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_options(emfit_core PRIVATE -O3 -fopenmp)
target_link_libraries(emfit_core PRIVATE OpenMP::OpenMP_CXX)
