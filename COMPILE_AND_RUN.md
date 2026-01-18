# Quick Reference: Compile and Run SINDI Index Build

## Step 1: Compile (After Making Changes)

```bash
cd Code/vsag
cmake --build build-release --target sindi_index_build --parallel 6
```

**Compilation time:** ~10-30 seconds (only rebuilds changed files)

## Step 2: Run the Program

### Basic Usage (Single Thread - Default)
```bash
./build-release/sparse/scripts/sindi_index_build data.csr 100 0.5 output.index
```

### With Custom Thread Count
```bash
# Use 4 threads
./build-release/sparse/scripts/sindi_index_build data.csr 100 0.5 output.index 4

# Use 8 threads
./build-release/sparse/scripts/sindi_index_build data.csr 100 0.5 output.index 8

# Use all available CPU threads
./build-release/sparse/scripts/sindi_index_build data.csr 100 0.5 output.index 0
```

## Parameters Explained

| Parameter | Description | Example |
|-----------|-------------|---------|
| `basefile` | Path to CSR format sparse vectors | `data.csr` |
| `lambda` | Window size parameter | `100` |
| `alpha` | Pruning parameter (0.0-1.0) | `0.5` |
| `index_path` | Output index file path | `output.index` |
| `num_threads` | (Optional) Thread count (default: 1, use 0 for max) | `4` or `0` |

## What You'll See

The program will output:
1. Input parameters confirmation
2. Build progress
3. **Detailed memory statistics** including:
   - Posting list (inverted index) size and statistics
   - Forward index size and statistics
   - Total memory breakdown
   - Build time

## Example Output

```
basefile: data.csr
lambda: 100
alpha: 0.5
index_path: output.index
num_threads: 4

Start building sindi index with 4 thread(s)
Build completed successfully
Number of vectors indexed: 100000

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

## Troubleshooting

### If compilation fails:
```bash
# Clean and rebuild
cd Code/vsag
make clean-release
make release
```

### Check available CPU threads:
```bash
nproc  # or lscpu | grep "^CPU(s):"
```

### If you get "file not found" errors:
Make sure you're running from the correct directory or use the full path:
```bash
/path/to/Code/vsag/build-release/sparse/scripts/sindi_index_build ...
```
