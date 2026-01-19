# SINDI Experiment Guide for MSMarco Dataset

## Quick Start

Navigate to the vsag directory:
```bash
cd /home/ec2-user/Code/vsag
```

### 1. Build Index for MSMarco v1
```bash
./build-release/sparse/scripts/sindi_index_build \
    /home/ec2-user/sparse_datasets/msmarco_v1_cocondenser/docs.csr \
    1000 0.8 msmarco_v1_sindi.index
```

**Parameters:**
- `1000` = lambda (window_size): Controls cache locality vs random access tradeoff
- `0.8` = alpha (doc_prune_ratio): Document pruning ratio (0.0-1.0)

### 2. Generate Ground Truth
```bash
./build-release/sparse/scripts/generate_gt \
    /home/ec2-user/sparse_datasets/msmarco_v1_cocondenser/docs.csr \
    /home/ec2-user/sparse_datasets/msmarco_v1_cocondenser/queries.csr \
    msmarco_v1_gt.bin 100
```

**Parameters:**
- `100` = topk: Number of nearest neighbors to retrieve

### 3. Search and Evaluate
```bash
./build-release/sparse/scripts/sindi_index_search \
    msmarco_v1_sindi.index \
    /home/ec2-user/sparse_datasets/msmarco_v1_cocondenser/queries.csr \
    msmarco_v1_gt.bin 0.5 200 10 4
```

**Parameters:**
- `0.5` = beta (query_prune_ratio): Query pruning ratio (0.0-1.0)
- `200` = gamma (reorder_size): Candidate pool size for reranking
- `10` = topk: Number of results to return
- `4` = num_threads: Number of parallel threads

**Output:** The script will print `qps` (queries per second) and `recall` metrics.

---

## Data Preprocessing

Your dataset is already in CSR (Compressed Sparse Row) format - **no preprocessing needed**. The dataset includes:
- `docs.csr` - base vectors (documents)
- `queries.csr` - query vectors
- Ground truth files and pruning masks (optional)

---

## Tunable Hyperparameters for Recall Optimization

### Index Build Parameters

#### lambda (window_size)
Controls how many vector IDs are processed per cache-local segment.
- **Smaller values (100-500)**: Fewer random accesses, more window switches
- **Larger values (1000-5000)**: Better posting list locality, more random writes
- **Recommended starting point**: 1000
- **Impact**: Affects build time and index structure, minimal impact on recall

#### alpha (doc_prune_ratio)
Retains minimal set of high-value non-zero entries whose cumulative mass ≥ alpha × (total vector mass).
- **Higher values (0.8-1.0)**: Better recall, slower QPS, larger index
- **Lower values (0.1-0.5)**: Faster QPS, lower recall, smaller index
- **Recommended starting point**: 0.8
- **Impact**: Direct impact on recall and index size

### Search Parameters

#### beta (query_prune_ratio)
Keeps minimal set of high-value query entries covering beta × (total query mass).
- **Lower values (0.1-0.3)**: Faster coarse search, may reduce recall
- **Higher values (0.5-1.0)**: Better recall, slower search
- **Recommended starting point**: 0.5
- **Impact**: Affects recall and search speed

#### gamma (reorder_size)
Number of coarse-stage candidates reranked with exact inner product.
- **Smaller values (50-200)**: Faster, lower recall
- **Larger values (500-2000)**: Better recall, slower
- **Rule of thumb**: gamma = topk × (5 to 50)
- **Recommended starting point**: 200
- **Impact**: Direct impact on recall and search latency

---

## Data Type / Quantization

The current SINDI implementation uses **float32** as the data type (hardcoded in scripts). The vsag codebase supports:
- `float32` - default for sparse vectors (current implementation)
- `int8` - available for dense vector indexes like HNSW

To experiment with different data types, you would need to modify the `dtype` field in:
- `sparse/scripts/sindi_index_build.cpp` (line 81)
- `sparse/scripts/sindi_index_search.cpp` (line 136)

---

## Measuring Performance Metrics

### Index Build Time
```bash
time ./build-release/sparse/scripts/sindi_index_build \
    /home/ec2-user/sparse_datasets/msmarco_v1_cocondenser/docs.csr \
    1000 0.8 msmarco_v1_sindi.index
```

### RAM Usage During Build
```bash
/usr/bin/time -v ./build-release/sparse/scripts/sindi_index_build \
    /home/ec2-user/sparse_datasets/msmarco_v1_cocondenser/docs.csr \
    1000 0.8 msmarco_v1_sindi.index 2>&1 | grep "Maximum resident set size"
```

### Index Size on Disk
```bash
ls -lh msmarco_v1_sindi.index
```

### Search Performance
The search script automatically outputs:
- **QPS** (queries per second): Search throughput
- **Recall**: Accuracy compared to ground truth

---

## Parameter Sweep for Recall Tuning

### Experiment 1: Vary alpha (Index Quality)
```bash
for alpha in 0.3 0.5 0.7 0.8 0.9 1.0; do
    echo "Building index with alpha=$alpha"
    ./build-release/sparse/scripts/sindi_index_build \
        /home/ec2-user/sparse_datasets/msmarco_v1_cocondenser/docs.csr \
        1000 $alpha index_alpha_${alpha}.index
    
    echo "Testing index with alpha=$alpha"
    ./build-release/sparse/scripts/sindi_index_search \
        index_alpha_${alpha}.index \
        /home/ec2-user/sparse_datasets/msmarco_v1_cocondenser/queries.csr \
        msmarco_v1_gt.bin 0.5 200 10 4
    echo "---"
done
```

### Experiment 2: Vary beta and gamma (Search Parameters)
```bash
for beta in 0.3 0.5 0.7 1.0; do
    for gamma in 100 200 500 1000; do
        echo "Testing beta=$beta, gamma=$gamma"
        ./build-release/sparse/scripts/sindi_index_search \
            msmarco_v1_sindi.index \
            /home/ec2-user/sparse_datasets/msmarco_v1_cocondenser/queries.csr \
            msmarco_v1_gt.bin $beta $gamma 10 4
        echo "---"
    done
done
```

### Experiment 3: Vary Number of Threads
```bash
for threads in 1 2 4 8 16; do
    echo "Testing with $threads threads"
    ./build-release/sparse/scripts/sindi_index_search \
        msmarco_v1_sindi.index \
        /home/ec2-user/sparse_datasets/msmarco_v1_cocondenser/queries.csr \
        msmarco_v1_gt.bin 0.5 200 10 $threads
    echo "---"
done
```

---

## Expected Results

Typical recall/QPS tradeoffs:
- **High recall (>0.95)**: alpha=1.0, beta=1.0, gamma=1000+ → Lower QPS
- **Balanced (0.85-0.95)**: alpha=0.8, beta=0.5, gamma=200-500 → Moderate QPS
- **High speed (<0.85)**: alpha=0.5, beta=0.3, gamma=100 → Higher QPS

Adjust parameters based on your application's recall requirements and latency constraints.

---

## Automated Recall Tuning Scripts

### Quick Test Single Configuration
Test a specific beta/gamma combination:
```bash
./test_config.sh <beta> <gamma>

# Example:
./test_config.sh 0.5 200
```

### Fast Targeted Tuning (Recommended)
Quickly find configurations for target recalls (91%, 93%, 95%, 97%, 99%):
```bash
./tune_recall_fast.sh
```

This script:
- Tests strategic beta values (0.5, 0.7, 1.0)
- Uses smart gamma search for each target recall
- Recommends best configuration (highest QPS) for each target
- Completes in ~5-10 minutes

### Comprehensive Grid Search
Exhaustive search across all parameter combinations:
```bash
./tune_recall.sh
```

This script:
- Tests beta: 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0
- Tests gamma: 50, 100, 150, 200, 300, 400, 500, 700, 1000, 1500, 2000
- Saves all results to `recall_tuning_results.txt`
- Analyzes results and recommends configurations
- Takes longer (~30-60 minutes) but provides complete data

### Manual Tuning Guidelines

If automated scripts don't achieve your target recall:

1. **For 91-93% recall**: Start with beta=0.5, gamma=200-400
2. **For 93-95% recall**: Try beta=0.6-0.7, gamma=400-800
3. **For 95-97% recall**: Use beta=0.7-0.9, gamma=800-1200
4. **For 97-99% recall**: Use beta=0.9-1.0, gamma=1200-2000
5. **For 99%+ recall**: May need to rebuild index with higher alpha (0.9-1.0)

**Iterative approach:**
```bash
# Start with moderate settings
./test_config.sh 0.5 200

# If recall too low, increase gamma first
./test_config.sh 0.5 400
./test_config.sh 0.5 800

# If still too low, increase beta
./test_config.sh 0.7 400
./test_config.sh 0.7 800

# For highest recall, maximize both
./test_config.sh 1.0 1500
./test_config.sh 1.0 2000
```
