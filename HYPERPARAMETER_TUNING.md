# SINDI Hyperparameter Tuning Guide

Complete guide for tuning search-time hyperparameters (beta, gamma) to achieve target recall levels.

## Prerequisites

Before running these scripts, ensure you have:

1. **Built indices** using `build_sindi_indices.py`
2. **Generated ground truth** using `generate_ground_truth.py`
3. **Ground truth file** exists: `msmarco_v1_gt.bin`

## Quick Start

```bash
cd /home/ec2-user/Code/vsag

# Run fast tuning (recommended)
python tune_recall_targets.py --mode fast
```

This will find optimal configurations for 91%, 93%, 95%, 97%, and 99% recall in ~5-10 minutes.

---

## Script 1: tune_recall_targets.py

Main script for finding optimal hyperparameters to achieve target recall levels.

### Usage

#### Fast Mode (Recommended)

Strategic search that tests key beta values and finds optimal gamma:

```bash
python tune_recall_targets.py --mode fast
```

**What it does:**
- Tests 4 strategic beta values: 0.5, 0.7, 0.9, 1.0
- Uses binary search to find optimal gamma for each target recall
- Finds configurations for: 91%, 93%, 95%, 97%, 99% recall
- Recommends best configuration (highest QPS) for each target
- **Time:** ~5-10 minutes

#### Comprehensive Mode

Exhaustive grid search across all parameter combinations:

```bash
python tune_recall_targets.py --mode comprehensive
```

**What it does:**
- Tests 8 beta values: 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0
- Tests 11 gamma values: 50, 100, 150, 200, 300, 400, 500, 700, 1000, 1500, 2000
- Total: 88 configurations
- Saves all results to `recall_tuning_results.txt`
- **Time:** ~30-60 minutes

### Command-Line Options

```bash
# Use different index file
python tune_recall_targets.py --index msmarco_v1_sindi_alpha_0.3.index

# Use different queries file
python tune_recall_targets.py --queries /path/to/queries.csr

# Use different ground truth file
python tune_recall_targets.py --gt /path/to/gt.bin

# Reduce output verbosity
python tune_recall_targets.py --mode fast --quiet

# Full example with all options
python tune_recall_targets.py \
    --mode fast \
    --index msmarco_v1_sindi_alpha_0.3.index \
    --queries /home/ec2-user/sparse_datasets/msmarco_v1_cocondenser/queries.csr \
    --gt msmarco_v1_gt.bin
```

### Output Format

The script provides clear recommendations for each target recall:

```
==================================================================
Target Recall: 95.0%
==================================================================

⭐ RECOMMENDED (Best QPS):
  Beta: 0.7
  Gamma: 600
  Achieved Recall: 95.2%
  QPS: 1234.5

  Command:
  ./build-release/sparse/scripts/sindi_index_search \
      msmarco_v1_sindi_no_prune.index \
      /home/ec2-user/sparse_datasets/msmarco_v1_cocondenser/queries.csr \
      msmarco_v1_gt.bin 0.7 600 10 4

  Alternatives:
    1. beta=0.9, gamma=400, recall=95.3%, qps=1150.2
    2. beta=0.5, gamma=800, recall=95.1%, qps=1100.8
```

### Understanding the Results

- **Beta (query_prune_ratio):** Controls query pruning
  - Higher = better recall, slower search
  - Range: 0.0 to 1.0

- **Gamma (reorder_size):** Number of candidates to rerank
  - Higher = better recall, slower search
  - Range: 50 to 2000+

- **QPS (Queries Per Second):** Search throughput
  - Higher is better for performance

- **Recall:** Accuracy compared to ground truth
  - Higher is better for quality

### Files Generated

**Fast mode:**
- Console output with recommendations only

**Comprehensive mode:**
- `recall_tuning_results.txt` - Detailed results for all tested configurations

---

## Script 2: test_single_config.py

Quick utility for testing specific beta/gamma combinations.

### Usage

```bash
python test_single_config.py <beta> <gamma> [index_path]
```

### Examples

```bash
# Test moderate settings
python test_single_config.py 0.5 200

# Test higher recall settings
python test_single_config.py 0.7 800

# Test maximum recall settings
python test_single_config.py 1.0 1500

# Test with different index file
python test_single_config.py 0.7 600 msmarco_v1_sindi_alpha_0.3.index
```

### Output Format

```
============================================================
Testing Configuration
============================================================
Index: msmarco_v1_sindi_no_prune.index
Beta: 0.7
Gamma: 600
Top-K: 10
Threads: 4

Command: ./build-release/sparse/scripts/sindi_index_search ...
============================================================

[Search output...]

============================================================
RESULTS SUMMARY
============================================================
Recall: 95.23%
QPS: 1234.56
============================================================
```

### When to Use

- **Quick validation** of recommended configurations
- **Fine-tuning** around a known good configuration
- **A/B testing** between two similar configurations
- **Debugging** specific parameter combinations

---

## Complete Workflow Example

### Step 1: Run Fast Tuning

```bash
cd /home/ec2-user/Code/vsag
python tune_recall_targets.py --mode fast
```

Wait ~5-10 minutes for results.

### Step 2: Review Recommendations

The script will output recommended configurations for each target recall. Example:

```
Target Recall: 95.0%
⭐ RECOMMENDED: beta=0.7, gamma=600, recall=95.2%, qps=1234.5
```

### Step 3: Test Recommended Configuration

```bash
python test_single_config.py 0.7 600
```

### Step 4: Fine-Tune if Needed

If you want slightly better recall:
```bash
python test_single_config.py 0.7 650  # Increase gamma
python test_single_config.py 0.8 600  # Increase beta
```

If you want better QPS:
```bash
python test_single_config.py 0.7 550  # Decrease gamma
python test_single_config.py 0.6 600  # Decrease beta
```

### Step 5: Document Your Results

Save the configurations that work best for your use case:

```bash
# For 95% recall target
beta=0.7, gamma=600, recall=95.2%, qps=1234.5

# For 97% recall target
beta=0.9, gamma=800, recall=97.1%, qps=890.3
```

---

## Tuning for Multiple Indices

If you built indices with different alpha values, tune each one:

### Index without pruning (alpha=1.0)

```bash
python tune_recall_targets.py \
    --mode fast \
    --index msmarco_v1_sindi_no_prune.index
```

### Index with pruning (alpha=0.3)

```bash
python tune_recall_targets.py \
    --mode fast \
    --index msmarco_v1_sindi_alpha_0.3.index
```

### Compare Results

The pruned index (alpha=0.3) will typically:
- Require higher beta/gamma to achieve same recall
- Have faster QPS due to smaller index size
- Use less memory

---

## Troubleshooting

### Cannot Achieve Target Recall

If the script cannot find configurations for high recall targets (97%, 99%):

1. **Try comprehensive mode** to explore more combinations:
   ```bash
   python tune_recall_targets.py --mode comprehensive
   ```

2. **Rebuild index with higher alpha**:
   ```bash
   ./build-release/sparse/scripts/sindi_index_build \
       /home/ec2-user/sparse_datasets/msmarco_v1_cocondenser/docs.csr \
       1000 0.9 msmarco_v1_sindi_alpha_0.9.index
   ```

3. **Test with maximum parameters manually**:
   ```bash
   python test_single_config.py 1.0 2000
   ```

### QPS Too Low

If recommended configurations have unacceptably low QPS:

1. **Accept slightly lower recall** (e.g., 93% instead of 95%)
2. **Use pruned index** (alpha=0.3) for faster search
3. **Increase thread count** in the search command
4. **Test lower gamma values**:
   ```bash
   python test_single_config.py 0.7 400  # Instead of 600
   ```

### Script Takes Too Long

If tuning is taking too long:

1. **Use fast mode** instead of comprehensive
2. **Use --quiet flag** to reduce output overhead
3. **Reduce thread count** if system is overloaded
4. **Test fewer configurations manually**

### Search Command Fails

If the underlying search command fails:

1. **Verify files exist**:
   ```bash
   ls -lh msmarco_v1_sindi_no_prune.index
   ls -lh msmarco_v1_gt.bin
   ls -lh /home/ec2-user/sparse_datasets/msmarco_v1_cocondenser/queries.csr
   ```

2. **Test search binary directly**:
   ```bash
   ./build-release/sparse/scripts/sindi_index_search \
       msmarco_v1_sindi_no_prune.index \
       /home/ec2-user/sparse_datasets/msmarco_v1_cocondenser/queries.csr \
       msmarco_v1_gt.bin 0.5 200 10 4
   ```

3. **Check binary exists**:
   ```bash
   ls -lh /home/ec2-user/Code/vsag/build-release/sparse/scripts/sindi_index_search
   ```

---

## Advanced Usage

### Custom Target Recalls

To tune for different recall targets, edit `tune_recall_targets.py`:

```python
# Change this line (around line 17)
TARGET_RECALLS = [0.91, 0.93, 0.95, 0.97, 0.99]

# To your custom targets, e.g.:
TARGET_RECALLS = [0.90, 0.92, 0.94, 0.96, 0.98]
```

### Custom Search Space

To test different beta/gamma ranges, edit `tune_recall_targets.py`:

```python
# Change these lines (around lines 20-21)
BETA_VALUES = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
GAMMA_VALUES = [50, 100, 150, 200, 300, 400, 500, 700, 1000, 1500, 2000]

# To your custom ranges, e.g.:
BETA_VALUES = [0.5, 0.6, 0.7, 0.8, 0.9]
GAMMA_VALUES = [100, 200, 400, 800, 1600]
```

### Batch Testing Multiple Indices

Create a shell script to test all your indices:

```bash
#!/bin/bash
# test_all_indices.sh

for index in msmarco_v1_sindi_*.index; do
    echo "Tuning $index..."
    python tune_recall_targets.py --mode fast --index "$index"
    echo "---"
done
```

---

## Performance Tips

1. **Start with fast mode** - It's usually sufficient
2. **Use comprehensive mode** only if you need complete data
3. **Test single configs** for quick validation
4. **Run during off-peak hours** if sharing resources
5. **Use --quiet flag** for batch processing
6. **Save results** to compare different indices

---

## Expected Results

Typical configurations for MSMarco v1 with alpha=0.8:

| Target Recall | Beta Range | Gamma Range | Expected QPS |
|---------------|------------|-------------|--------------|
| 91%           | 0.4-0.6    | 150-300     | High         |
| 93%           | 0.5-0.7    | 250-450     | Medium-High  |
| 95%           | 0.6-0.8    | 400-700     | Medium       |
| 97%           | 0.7-0.9    | 700-1200    | Medium-Low   |
| 99%           | 0.9-1.0    | 1200-2000   | Low          |

Actual values will vary based on:
- Index alpha value
- Dataset characteristics
- Hardware specifications
- Thread count

---

## Next Steps

After finding optimal configurations:

1. **Document your results** for future reference
2. **Test with production queries** to validate performance
3. **Benchmark different thread counts** for throughput optimization
4. **Consider building multiple indices** with different alpha values
5. **Set up monitoring** for recall and QPS in production
6. **Create deployment configs** with your chosen parameters

---

## Related Files

- `build_sindi_indices.py` - Build indices with different alpha values
- `generate_ground_truth.py` - Generate ground truth files
- `run_experiments.md` - General experiment guide
- `TUNING_GUIDE.md` - Conceptual tuning guide
