# SINDI Index Build - Usage Guide

## Overview
The `sindi_index_build` program now supports configurable thread numbers and automatically outputs detailed memory statistics after building the index.

## Prerequisites and Compilation

### 1. Compile the Program

Since you modified `sindi_index_build.cpp`, you need to recompile it. You have several options:

#### Option A: Rebuild Only the Changed Target (Fastest)
```bash
cd Code/vsag
cmake --build build-release --target sindi_index_build --parallel 6
```

#### Option B: Full Release Build
```bash
cd Code/vsag
make release
```

#### Option C: Manual CMake Build
```bash
cd Code/vsag
cmake -DCMAKE_BUILD_TYPE=Release -DENABLE_TESTS=1 -B./build-release -S.
cmake --build build-release --parallel 6
```

### 2. Verify the Executable
After compilation, the executable will be located at:
```bash
Code/vsag/build-release/sparse/scripts/sindi_index_build
```

Check it exists:
```bash
ls -lh Code/vsag/build-release/sparse/scripts/sindi_index_build
```

## Command Line Usage

```bash
./sindi_index_build <basefile> <lambda> <alpha> <index_path> [num_threads]
```

### Parameters:
- `basefile`: Path to the CSR format sparse vector file
- `lambda`: Window size parameter for SINDI
- `alpha`: Pruning parameter for SINDI
- `index_path`: Output path for the serialized index
- `num_threads`: (Optional) Number of threads to use for building
  - Default: 1 (single-threaded)
  - Use 0 to automatically use all available CPU threads
  - Use any positive integer to specify exact thread count

### Examples:

```bash
# Single-threaded build (default)
./sindi_index_build data.csr 100 0.5 index.bin

# Use 4 threads
./sindi_index_build data.csr 100 0.5 index.bin 4

# Use all available threads
./sindi_index_build data.csr 100 0.5 index.bin 0

# Use 8 threads
./sindi_index_build data.csr 100 0.5 index.bin 8
```

## Output Statistics

After building the index, the program automatically outputs:

### 1. **Posting List (Inverted Index) Statistics:**
   - Total memory usage (MB and bytes)
   - Number of non-empty posting lists
   - Total non-zero entries
   - Average entries per non-empty list
   - Average entries per document

### 2. **Forward Index Statistics:**
   - Total memory usage (MB and bytes)
   - Total non-zero entries
   - Average entries per document

### 3. **Overall Statistics:**
   - Header size
   - Memory breakdown by component (posting lists vs forward index)
   - Total index size
   - Build time

### Sample Output:
```
======================================================================
SINDI INDEX BUILD STATISTICS
======================================================================

Index Parameters:
  Total documents: 100000
  Vocabulary size: 30000
  Lambda (window size): 100
  Sigma (num windows): 1000
  Build time: 45.23 seconds

----------------------------------------------------------------------
POSTING LIST (Inverted Index) MEMORY
----------------------------------------------------------------------
  Memory: 123.45 MB (129456789 bytes)
  Non-empty lists: 25000 / 30000 (83.3%)
  Total non-zeros: 5000000
  Avg per non-empty list: 200.00
  Avg per document: 50.00

----------------------------------------------------------------------
FORWARD INDEX MEMORY
----------------------------------------------------------------------
  Memory: 98.76 MB (103567890 bytes)
  Total non-zeros: 5000000
  Avg per document: 50.00

----------------------------------------------------------------------
TOTAL MEMORY
----------------------------------------------------------------------
  Header: 0.02 KB
  Posting lists: 123.45 MB (54.3%)
  Forward index: 98.76 MB (45.7%)
  Total: 222.21 MB (233024679 bytes)
======================================================================
```

## Notes

- The memory statistics are calculated by parsing the serialized index file
- Build time is measured from the start to completion of the Build() operation
- Thread count affects build performance but not the final index structure
- Using more threads generally speeds up the build process for large datasets
